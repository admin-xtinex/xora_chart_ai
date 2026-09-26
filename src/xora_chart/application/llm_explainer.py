"""Optional, read-only LLM explanations with Groq -> Gemini failover.

This module is deliberately isolated from validation, decision, and execution.
An LLM response can explain an existing deterministic opportunity, but it can
never approve a setup, change trade levels, or open a position.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import httpx
from pydantic import BaseModel, Field, ValidationError

from xora_chart.domain.models import LLMExplanation, Opportunity

log = logging.getLogger(__name__)

PROMPT_VERSION = "v1"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class _ExplanationContent(BaseModel):
    summary: str
    evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_confirmations: list[str] = Field(default_factory=list)
    educational_note: str


_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "missing_confirmations": {"type": "array", "items": {"type": "string"}},
        "educational_note": {"type": "string"},
    },
    "required": ["summary", "evidence", "risks", "missing_confirmations", "educational_note"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """You explain XORA chart-pattern opportunities using only the supplied facts.
The deterministic engines remain authoritative. Never create or change a trade decision, entry,
stop, target, confidence, or execution instruction. Do not claim certainty or profitability.
If evidence is missing or weak, say so plainly. Keep the explanation concise and educational.
Return only JSON matching the supplied schema."""


@dataclass(frozen=True)
class _ProviderResult:
    content: _ExplanationContent
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class ProviderError(RuntimeError):
    def __init__(
        self,
        provider: str,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retry_after = retry_after


_cache: dict[str, tuple[float, LLMExplanation]] = {}
_requests: dict[str, deque[float]] = defaultdict(deque)
_provider_cooldowns: dict[str, float] = {}


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _provider_order() -> list[str]:
    raw = os.getenv("XORA_LLM_PROVIDERS", "groq,gemini")
    allowed = {"groq", "gemini"}
    return [item for item in (part.strip().lower() for part in raw.split(",")) if item in allowed]


def status() -> dict[str, Any]:
    configured = []
    if os.getenv("GROQ_API_KEY"):
        configured.append("groq")
    if os.getenv("GEMINI_API_KEY"):
        configured.append("gemini")
    enabled = _truthy(os.getenv("XORA_LLM_ENABLED", "false"))
    ordered = [provider for provider in _provider_order() if provider in configured]
    return {
        "enabled": enabled,
        "ready": enabled and bool(ordered),
        "providers": ordered,
        "prompt_version": PROMPT_VERSION,
    }


def _opportunity_facts(opp: Opportunity) -> dict[str, Any]:
    match = opp.best_match
    analysis = opp.market_analysis
    decision = opp.decision
    trade = opp.trade
    return {
        "opportunity_id": opp.id,
        "symbol": opp.symbol,
        "interval": opp.interval,
        "status": opp.status.value,
        "last_price": opp.last_price,
        "pattern": None if not match else {
            "name": match.pattern_name,
            "direction": match.direction.value,
            "structural_similarity": match.similarity,
            "reference_similarity": match.reference_similarity,
            "reference_verified": match.reference_verified,
            "matched_example": match.matched_example,
            "score_breakdown": match.score_breakdown,
        },
        "market_analysis": None if not analysis else {
            "score": analysis.score,
            "bias": analysis.bias.value,
            "regime": analysis.regime.value,
            "signals": [
                {"name": signal.name, "score": signal.score, "status": signal.status.value, "note": signal.note}
                for signal in analysis.signals
            ],
        },
        "decision": None if not decision else {
            "action": decision.action.value,
            "reason": decision.reason,
            "confirmations": [
                {"name": item.name, "required": item.required, "met": item.met, "note": item.note}
                for item in decision.confirmations
            ],
        },
        "trade_plan": None if not trade else {
            "side": trade.side.value,
            "entry": trade.entry,
            "stop_loss": trade.stop_loss,
            "take_profit_1": trade.take_profit_1,
            "take_profit_2": trade.take_profit_2,
            "take_profit_3": trade.take_profit_3,
            "risk_reward": trade.risk_reward,
            "confidence": trade.confidence,
        },
    }


def _cache_key(facts: dict[str, Any]) -> str:
    configured_models = {
        "groq": os.getenv("XORA_GROQ_MODEL", "openai/gpt-oss-20b"),
        "gemini": os.getenv("XORA_GEMINI_MODEL", "gemini-2.5-flash-lite"),
    }
    payload = json.dumps(
        {"prompt": PROMPT_VERSION, "providers": _provider_order(), "models": configured_models, "facts": facts},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _check_rate_limit(client_key: str) -> None:
    limit = max(1, int(os.getenv("XORA_LLM_REQUESTS_PER_MINUTE", "5")))
    now = time.monotonic()
    bucket = _requests[client_key or "unknown"]
    while bucket and now - bucket[0] >= 60:
        bucket.popleft()
    if len(bucket) >= limit:
        raise RuntimeError(f"AI explanation limit reached ({limit}/minute). Try again shortly.")
    bucket.append(now)


def _parse_content(raw: str, provider: str) -> _ExplanationContent:
    try:
        return _ExplanationContent.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ProviderError(provider, f"{provider} returned an invalid explanation") from exc


async def _call_groq(facts: dict[str, Any], client: httpx.AsyncClient) -> _ProviderResult:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ProviderError("groq", "GROQ_API_KEY is not configured")
    model = os.getenv("XORA_GROQ_MODEL", "openai/gpt-oss-20b")
    response = await client.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.1,
            "max_completion_tokens": 900,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(facts, sort_keys=True, default=str)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "xora_opportunity_explanation", "strict": True, "schema": _OUTPUT_SCHEMA},
            },
        },
    )
    if response.status_code >= 400:
        retry_after = response.headers.get("retry-after")
        raise ProviderError(
            "groq",
            f"Groq HTTP {response.status_code}",
            status_code=response.status_code,
            retry_after=float(retry_after) if retry_after and retry_after.isdigit() else None,
        )
    data = response.json()
    try:
        raw = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("groq", "Groq response did not contain output") from exc
    usage = data.get("usage") or {}
    return _ProviderResult(
        content=_parse_content(raw, "groq"),
        provider="groq",
        model=model,
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
    )


async def _call_gemini(facts: dict[str, Any], client: httpx.AsyncClient) -> _ProviderResult:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ProviderError("gemini", "GEMINI_API_KEY is not configured")
    model = os.getenv("XORA_GEMINI_MODEL", "gemini-2.5-flash-lite")
    response = await client.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={
            "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(facts, sort_keys=True, default=str)}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 900,
                "responseMimeType": "application/json",
                "responseJsonSchema": _OUTPUT_SCHEMA,
            },
        },
    )
    if response.status_code >= 400:
        retry_after = response.headers.get("retry-after")
        raise ProviderError(
            "gemini",
            f"Gemini HTTP {response.status_code}",
            status_code=response.status_code,
            retry_after=float(retry_after) if retry_after and retry_after.isdigit() else None,
        )
    data = response.json()
    try:
        raw = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("gemini", "Gemini response did not contain output") from exc
    usage = data.get("usageMetadata") or {}
    return _ProviderResult(
        content=_parse_content(raw, "gemini"),
        provider="gemini",
        model=model,
        input_tokens=usage.get("promptTokenCount"),
        output_tokens=usage.get("candidatesTokenCount"),
    )


_CALLERS: dict[str, Callable[[dict[str, Any], httpx.AsyncClient], Awaitable[_ProviderResult]]] = {
    "groq": _call_groq,
    "gemini": _call_gemini,
}


async def explain_opportunity(opp: Opportunity, *, client_key: str = "unknown") -> LLMExplanation:
    current = status()
    if not current["enabled"]:
        raise RuntimeError("AI explanations are disabled. Set XORA_LLM_ENABLED=true to enable them.")
    providers = list(current["providers"])
    if not providers:
        raise RuntimeError("AI explanations need GROQ_API_KEY or GEMINI_API_KEY on the backend.")

    facts = _opportunity_facts(opp)
    key = _cache_key(facts)
    ttl = max(30, int(os.getenv("XORA_LLM_CACHE_TTL_SECONDS", "900")))
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < ttl:
        return cached[1].model_copy(update={"cached": True})

    _check_rate_limit(client_key)
    timeout = max(3.0, float(os.getenv("XORA_LLM_TIMEOUT_SECONDS", "20")))
    failures: list[str] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        for provider in providers:
            cooldown_until = _provider_cooldowns.get(provider, 0.0)
            if cooldown_until > time.monotonic():
                failures.append(f"{provider}: temporarily cooling down after rate limit")
                continue
            try:
                result = await _CALLERS[provider](facts, client)
                explanation = LLMExplanation(
                    **result.content.model_dump(),
                    provider=result.provider,
                    model=result.model,
                    prompt_version=PROMPT_VERSION,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    generated_at=datetime.now(timezone.utc),
                )
                _cache[key] = (time.monotonic(), explanation)
                if len(_cache) > 256:
                    oldest = min(_cache, key=lambda item: _cache[item][0])
                    _cache.pop(oldest, None)
                return explanation
            except ProviderError as exc:
                if exc.status_code == 429:
                    fallback_cooldown = max(5.0, float(os.getenv("XORA_LLM_PROVIDER_COOLDOWN_SECONDS", "60")))
                    _provider_cooldowns[provider] = time.monotonic() + (exc.retry_after or fallback_cooldown)
                failures.append(f"{provider}: {exc}")
                log.warning("LLM provider %s failed; trying next provider: %s", provider, exc)
            except (httpx.HTTPError, ValueError) as exc:
                failures.append(f"{provider}: {exc}")
                log.warning("LLM provider %s failed; trying next provider: %s", provider, exc)

    raise RuntimeError("AI explanation providers are unavailable: " + " | ".join(failures))


def clear_runtime_state() -> None:
    """Clear volatile cache/rate state; primarily useful for tests."""
    _cache.clear()
    _requests.clear()
    _provider_cooldowns.clear()

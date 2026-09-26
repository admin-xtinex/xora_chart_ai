from __future__ import annotations

import asyncio
import json

import httpx

from xora_chart.application import llm_explainer
from xora_chart.domain.models import Opportunity


def content(summary: str = "Grounded summary") -> llm_explainer._ExplanationContent:
    return llm_explainer._ExplanationContent(
        summary=summary,
        evidence=["The supplied evidence says X"],
        risks=["The supplied evidence is incomplete"],
        missing_confirmations=["volume_support"],
        educational_note="This is educational and does not change the engine decision.",
    )


def test_groq_failure_falls_back_to_gemini(monkeypatch) -> None:
    llm_explainer.clear_runtime_state()
    monkeypatch.setenv("XORA_LLM_ENABLED", "true")
    monkeypatch.setenv("XORA_LLM_PROVIDERS", "groq,gemini")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")

    groq_calls = 0

    async def fail_groq(facts, client):
        nonlocal groq_calls
        groq_calls += 1
        raise llm_explainer.ProviderError("groq", "rate limited", status_code=429)

    async def pass_gemini(facts, client):
        return llm_explainer._ProviderResult(content(), "gemini", "test-model", 10, 20)

    monkeypatch.setitem(llm_explainer._CALLERS, "groq", fail_groq)
    monkeypatch.setitem(llm_explainer._CALLERS, "gemini", pass_gemini)

    result = asyncio.run(llm_explainer.explain_opportunity(Opportunity(symbol="BTCUSDT"), client_key="test"))

    assert result.provider == "gemini"
    assert result.model == "test-model"
    assert result.input_tokens == 10
    assert result.output_tokens == 20

    second = asyncio.run(llm_explainer.explain_opportunity(Opportunity(symbol="ETHUSDT"), client_key="test"))
    assert second.provider == "gemini"
    assert groq_calls == 1


def test_cached_explanation_does_not_call_provider_twice(monkeypatch) -> None:
    llm_explainer.clear_runtime_state()
    monkeypatch.setenv("XORA_LLM_ENABLED", "true")
    monkeypatch.setenv("XORA_LLM_PROVIDERS", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    calls = 0

    async def pass_groq(facts, client):
        nonlocal calls
        calls += 1
        return llm_explainer._ProviderResult(content(), "groq", "test-model")

    monkeypatch.setitem(llm_explainer._CALLERS, "groq", pass_groq)
    opp = Opportunity(symbol="ETHUSDT")

    first = asyncio.run(llm_explainer.explain_opportunity(opp, client_key="test"))
    second = asyncio.run(llm_explainer.explain_opportunity(opp, client_key="test"))

    assert first.cached is False
    assert second.cached is True
    assert calls == 1


def test_llm_is_disabled_by_default(monkeypatch) -> None:
    llm_explainer.clear_runtime_state()
    monkeypatch.delenv("XORA_LLM_ENABLED", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")

    try:
        asyncio.run(llm_explainer.explain_opportunity(Opportunity(symbol="SOLUSDT")))
    except RuntimeError as exc:
        assert "disabled" in str(exc).lower()
    else:
        raise AssertionError("Expected disabled LLM explanations to fail closed")


def test_prompt_facts_exclude_raw_candles() -> None:
    facts = llm_explainer._opportunity_facts(Opportunity(symbol="BTCUSDT"))

    assert "candles" not in facts
    assert facts["symbol"] == "BTCUSDT"


def test_groq_uses_strict_json_schema(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-groq"
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content().model_dump_json()}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 12},
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await llm_explainer._call_groq({"symbol": "BTCUSDT"}, client)

    result = asyncio.run(run())
    assert result.provider == "groq"
    assert result.input_tokens == 11


def test_gemini_uses_response_json_schema(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["x-goog-api-key"] == "test-gemini"
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["responseJsonSchema"]["additionalProperties"] is False
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": content().model_dump_json()}]}}],
                "usageMetadata": {"promptTokenCount": 13, "candidatesTokenCount": 14},
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await llm_explainer._call_gemini({"symbol": "ETHUSDT"}, client)

    result = asyncio.run(run())
    assert result.provider == "gemini"
    assert result.output_tokens == 14

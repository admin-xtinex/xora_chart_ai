from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from xora_chart.domain.models import Pattern

# data/patterns.json lives at repo root relative to this package when installed,
# but we also support running from source.
_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "data" / "patterns.json",
    Path(__file__).resolve().parents[3] / "data" / "patterns.json",
    Path.cwd() / "data" / "patterns.json",
]


def _find_catalog_path() -> Path:
    for p in _CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Could not locate data/patterns.json. Run from repo root or install the package."
    )


@lru_cache(maxsize=1)
def load_patterns() -> list[Pattern]:
    path = _find_catalog_path()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Pattern.model_validate(item) for item in raw["patterns"]]


def get_pattern(key: str) -> Pattern | None:
    for p in load_patterns():
        if p.key == key:
            return p
    return None


def list_patterns(
    direction: str | None = None,
    pattern_type: str | None = None,
) -> list[Pattern]:
    items = load_patterns()
    if direction:
        items = [p for p in items if p.direction.value == direction.lower()]
    if pattern_type:
        items = [p for p in items if p.type.value == pattern_type.lower()]
    return items

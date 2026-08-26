from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "config" / "default.yaml",
    Path(__file__).resolve().parents[3] / "config" / "default.yaml",
    Path.cwd() / "config" / "default.yaml",
]


def _find(path_suffix: str) -> Path:
    for base in [
        Path(__file__).resolve().parents[2],
        Path(__file__).resolve().parents[3],
        Path.cwd(),
    ]:
        p = base / path_suffix
        if p.exists():
            return p
    raise FileNotFoundError(f"Could not locate {path_suffix}")


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    path = _find("config/default.yaml")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_pattern_registry() -> list[dict[str, Any]]:
    path = _find("config/patterns.yaml")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return [p for p in data.get("patterns", []) if p.get("enabled", True)]

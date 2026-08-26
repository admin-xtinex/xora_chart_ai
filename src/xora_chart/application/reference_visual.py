"""Visual reference-chart comparison gate.

The reference PNGs in ``chart_reference/`` are the authoritative examples for
XORA. A live candle window is rendered into a normalized chart image and
compared with every uploaded reference using edge/shape signatures. The
structural pattern matcher can propose a pattern, but a trade decision is not
APPROVE unless this independent visual comparison also passes.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from xora_chart.domain.models import CandleWindow


def reference_dir() -> Path:
    configured = os.getenv("XORA_REFERENCE_DIR")
    if configured:
        return Path(configured)
    return Path.cwd() / "chart_reference"


def reference_files() -> list[Path]:
    root = reference_dir()
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})


def library_status() -> dict:
    files = reference_files()
    return {
        "directory": str(reference_dir()),
        "count": len(files),
        "ready": len(files) > 0,
        "files": [p.name for p in files],
    }


def _normalized(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _render_window(window: CandleWindow, width: int = 384, height: int = 240) -> Image.Image:
    image = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(image)
    candles = window.candles[-100:]
    if not candles:
        return image

    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    lo, hi = min(lows), max(highs)
    span = max(hi - lo, 1e-12)
    pad_x, pad_y = 10, 10
    usable_w = width - pad_x * 2
    usable_h = height - pad_y * 2
    step = usable_w / max(len(candles), 1)
    body_w = max(1, int(step * 0.55))

    def y(price: float) -> int:
        return int(pad_y + (hi - price) / span * usable_h)

    for i, c in enumerate(candles):
        x = int(pad_x + (i + 0.5) * step)
        yh, yl = y(c.high), y(c.low)
        yo, yc = y(c.open), y(c.close)
        draw.line((x, yh, x, yl), fill=255, width=1)
        top, bottom = sorted((yo, yc))
        if bottom == top:
            draw.line((x - body_w // 2, top, x + body_w // 2, top), fill=255, width=1)
        else:
            draw.rectangle((x - body_w // 2, top, x + body_w // 2, bottom), outline=255, fill=160)
    return image


def _crop_chart_area(image: Image.Image) -> Image.Image:
    w, h = image.size
    # Remove common title/header/axis regions while retaining the chart body.
    left = int(w * 0.06)
    right = int(w * 0.94)
    top = int(h * 0.14)
    bottom = int(h * 0.88)
    if right <= left or bottom <= top:
        return image
    return image.crop((left, top, right, bottom))


def _signature(image: Image.Image) -> tuple[tuple[float, ...], tuple[float, ...]]:
    img = ImageOps.grayscale(image)
    img = _crop_chart_area(img)
    img = ImageOps.autocontrast(img)
    img = img.resize((96, 64), Image.Resampling.BILINEAR)
    img = ImageOps.autocontrast(img.filter(ImageFilter.FIND_EDGES))
    px = img.load()
    w, h = img.size

    centers: list[float] = []
    density: list[float] = []
    for x in range(w):
        weights = [float(px[x, y]) / 255.0 for y in range(h)]
        total = sum(weights)
        if total <= 1e-9:
            centers.append(0.5)
            density.append(0.0)
        else:
            centers.append(sum((y / max(h - 1, 1)) * weights[y] for y in range(h)) / total)
            density.append(total / h)

    return tuple(centers), tuple(_normalized(density))


@lru_cache(maxsize=64)
def _reference_signature(path_str: str, mtime_ns: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    del mtime_ns  # cache-busting key only
    with Image.open(path_str) as image:
        return _signature(image.copy())


def _similarity(a: tuple[tuple[float, ...], tuple[float, ...]], b: tuple[tuple[float, ...], tuple[float, ...]]) -> float:
    ac, ad = a
    bc, bd = b
    n = min(len(ac), len(bc))
    if n == 0:
        return 0.0
    center_mae = sum(abs(ac[i] - bc[i]) for i in range(n)) / n
    density_mae = sum(abs(ad[i] - bd[i]) for i in range(n)) / n
    center_score = max(0.0, 1.0 - center_mae)
    density_score = max(0.0, 1.0 - density_mae)
    return round(100.0 * (0.75 * center_score + 0.25 * density_score), 2)


def compare_window_to_references(window: CandleWindow) -> dict:
    files = reference_files()
    if not files or not window.candles:
        return {"similarity": 0.0, "image": None, "reference_count": len(files)}

    live_sig = _signature(_render_window(window))
    best_score = -1.0
    best_file: Path | None = None
    for path in files:
        try:
            stat = path.stat()
            ref_sig = _reference_signature(str(path), stat.st_mtime_ns)
            score = _similarity(live_sig, ref_sig)
        except Exception:
            continue
        if score > best_score:
            best_score = score
            best_file = path

    return {
        "similarity": max(0.0, round(best_score, 2)),
        "image": best_file.name if best_file else None,
        "reference_count": len(files),
    }

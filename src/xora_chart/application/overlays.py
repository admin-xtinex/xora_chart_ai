"""Build chart overlay geometry for the matched pattern (levels, lines, markers)."""

from __future__ import annotations

from xora_chart.domain.models import Candle, CandleWindow


def _ts(c: Candle) -> int:
    return int((c.open_time or c.close_time or 0) // 1000)


def _extrema(vals: list[float], order: int = 3) -> tuple[list[int], list[int]]:
    peaks, troughs = [], []
    for i in range(order, len(vals) - order):
        w = vals[i - order : i + order + 1]
        if vals[i] == max(w) and vals[i] > vals[i - 1] and vals[i] > vals[i + 1]:
            peaks.append(i)
        if vals[i] == min(w) and vals[i] < vals[i - 1] and vals[i] < vals[i + 1]:
            troughs.append(i)
    return peaks, troughs


def _level(price: float, title: str, color: str = "rgba(167,139,250,0.85)") -> dict:
    return {"price": float(price), "title": title, "color": color}


def _marker(c: Candle, label: str, color: str = "#c4b5fd", position: str = "aboveBar") -> dict:
    return {
        "time": _ts(c),
        "price": float(c.high if position == "aboveBar" else c.low),
        "label": label,
        "color": color,
        "position": position,
    }


def _line(points: list[tuple[Candle, float]], title: str, color: str = "rgba(167,139,250,0.45)") -> dict | None:
    if len(points) < 2:
        return None
    return {
        "title": title,
        "color": color,
        "points": [{"time": _ts(c), "value": float(v)} for c, v in points],
    }


def _hs(candles: list[Candle]) -> dict:
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    peaks, _ = _extrema(highs, 3)
    levels, markers, lines = [], [], []
    if len(peaks) >= 3:
        l, h, r = peaks[-3], peaks[-2], peaks[-1]
        left_t = min(lows[l : h + 1]) if h > l else lows[l]
        right_t = min(lows[h : r + 1]) if r > h else lows[r]
        neck = (left_t + right_t) / 2
        levels.append(_level(neck, "Neckline", "rgba(244,114,182,0.75)"))
        markers.extend(
            [
                _marker(candles[l], "LS", "#a78bfa", "aboveBar"),
                _marker(candles[h], "Head", "#f472b6", "aboveBar"),
                _marker(candles[r], "RS", "#a78bfa", "aboveBar"),
            ]
        )
        ln = _line(
            [(candles[l], highs[l]), (candles[h], highs[h]), (candles[r], highs[r])],
            "H&S peaks",
            "rgba(167,139,250,0.4)",
        )
        if ln:
            lines.append(ln)
        # neckline horizontal segment across shoulders
        neck_line = _line(
            [(candles[l], neck), (candles[r], neck)],
            "Neckline",
            "rgba(244,114,182,0.35)",
        )
        if neck_line:
            lines.append(neck_line)
    return {"levels": levels, "markers": markers, "lines": lines}


def _double_top(candles: list[Candle]) -> dict:
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    peaks, _ = _extrema(highs, 4)
    levels, markers, lines = [], [], []
    if len(peaks) >= 2:
        p1, p2 = peaks[-2], peaks[-1]
        neck = min(lows[p1 : p2 + 1]) if p2 > p1 else lows[p2]
        levels.append(_level(neck, "Neckline", "rgba(244,114,182,0.75)"))
        levels.append(_level((highs[p1] + highs[p2]) / 2, "Tops", "rgba(167,139,250,0.55)"))
        markers.extend(
            [
                _marker(candles[p1], "T1", "#a78bfa", "aboveBar"),
                _marker(candles[p2], "T2", "#a78bfa", "aboveBar"),
            ]
        )
        ln = _line(
            [(candles[p1], highs[p1]), (candles[p2], highs[p2])],
            "Double top",
            "rgba(167,139,250,0.4)",
        )
        if ln:
            lines.append(ln)
        nl = _line([(candles[p1], neck), (candles[p2], neck)], "Neckline", "rgba(244,114,182,0.35)")
        if nl:
            lines.append(nl)
    return {"levels": levels, "markers": markers, "lines": lines}


def _double_bottom(candles: list[Candle]) -> dict:
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    _, troughs = _extrema(lows, 4)
    levels, markers, lines = [], [], []
    if len(troughs) >= 2:
        t1, t2 = troughs[-2], troughs[-1]
        neck = max(highs[t1 : t2 + 1]) if t2 > t1 else highs[t2]
        levels.append(_level(neck, "Neckline", "rgba(52,211,153,0.75)"))
        levels.append(_level((lows[t1] + lows[t2]) / 2, "Bottoms", "rgba(167,139,250,0.55)"))
        markers.extend(
            [
                _marker(candles[t1], "B1", "#34d399", "belowBar"),
                _marker(candles[t2], "B2", "#34d399", "belowBar"),
            ]
        )
        ln = _line(
            [(candles[t1], lows[t1]), (candles[t2], lows[t2])],
            "Double bottom",
            "rgba(52,211,153,0.4)",
        )
        if ln:
            lines.append(ln)
        nl = _line([(candles[t1], neck), (candles[t2], neck)], "Neckline", "rgba(52,211,153,0.35)")
        if nl:
            lines.append(nl)
    return {"levels": levels, "markers": markers, "lines": lines}


def _flag(candles: list[Candle], bullish: bool) -> dict:
    n = len(candles)
    mid = n // 2
    zone = candles[mid:]
    if not zone:
        return {"levels": [], "markers": [], "lines": []}
    hi = max(c.high for c in zone)
    lo = min(c.low for c in zone)
    color_hi = "rgba(52,211,153,0.55)" if bullish else "rgba(248,113,113,0.55)"
    color_lo = "rgba(248,113,113,0.55)" if bullish else "rgba(52,211,153,0.55)"
    levels = [
        _level(hi, "Flag high", color_hi),
        _level(lo, "Flag low", color_lo),
    ]
    # soft channel box via two lines across second half
    lines = []
    top = _line([(zone[0], hi), (zone[-1], hi)], "Flag high", "rgba(167,139,250,0.35)")
    bot = _line([(zone[0], lo), (zone[-1], lo)], "Flag low", "rgba(167,139,250,0.35)")
    if top:
        lines.append(top)
    if bot:
        lines.append(bot)
    markers = [
        _marker(zone[0], "Flag start", "#a78bfa", "aboveBar" if bullish else "belowBar"),
    ]
    return {"levels": levels, "markers": markers, "lines": lines}


def _breakout_retest(candles: list[Candle]) -> dict:
    highs = [c.high for c in candles]
    cut = int(len(candles) * 0.6)
    resistance = max(highs[:cut]) if cut else max(highs)
    levels = [_level(resistance, "Break level", "rgba(96,165,250,0.75)")]
    # mark first bar that closed above
    markers = []
    for c in candles[cut:]:
        if c.close > resistance:
            markers.append(_marker(c, "Break", "#60a5fa", "aboveBar"))
            break
    lines = []
    if cut > 0:
        ln = _line(
            [(candles[0], resistance), (candles[-1], resistance)],
            "Resistance",
            "rgba(96,165,250,0.3)",
        )
        if ln:
            lines.append(ln)
    return {"levels": levels, "markers": markers, "lines": lines}


def _breakdown_retest(candles: list[Candle]) -> dict:
    lows = [c.low for c in candles]
    cut = int(len(candles) * 0.6)
    support = min(lows[:cut]) if cut else min(lows)
    levels = [_level(support, "Break level", "rgba(248,113,113,0.75)")]
    markers = []
    for c in candles[cut:]:
        if c.close < support:
            markers.append(_marker(c, "Break", "#f87171", "belowBar"))
            break
    lines = []
    if cut > 0:
        ln = _line(
            [(candles[0], support), (candles[-1], support)],
            "Support",
            "rgba(248,113,113,0.3)",
        )
        if ln:
            lines.append(ln)
    return {"levels": levels, "markers": markers, "lines": lines}


def _cup_handle(candles: list[Candle]) -> dict:
    closes = [c.close for c in candles]
    n = len(candles)
    if n < 30:
        return {"levels": [], "markers": [], "lines": []}
    left_hi = max(closes[: n // 4])
    mid_lo = min(closes[n // 4 : 3 * n // 4])
    handle = candles[int(n * 0.85) :]
    levels = [
        _level(left_hi, "Rim", "rgba(52,211,153,0.7)"),
        _level(mid_lo, "Cup low", "rgba(167,139,250,0.55)"),
    ]
    markers, lines = [], []
    # approximate cup curve with 3 points
    i0, i1, i2 = 0, n // 2, int(n * 0.8)
    cup = _line(
        [
            (candles[i0], closes[i0]),
            (candles[i1], mid_lo),
            (candles[min(i2, n - 1)], closes[min(i2, n - 1)]),
        ],
        "Cup",
        "rgba(167,139,250,0.35)",
    )
    if cup:
        lines.append(cup)
    if handle:
        h_hi = max(c.high for c in handle)
        h_lo = min(c.low for c in handle)
        levels.append(_level(h_hi, "Handle high", "rgba(52,211,153,0.45)"))
        levels.append(_level(h_lo, "Handle low", "rgba(248,113,113,0.45)"))
        markers.append(_marker(handle[0], "Handle", "#a78bfa", "aboveBar"))
    return {"levels": levels, "markers": markers, "lines": lines}


def build_overlays(window: CandleWindow, pattern_key: str) -> dict:
    candles = window.candles
    if not candles:
        return {"levels": [], "markers": [], "lines": []}

    key = pattern_key
    if key == "head_and_shoulders":
        data = _hs(candles)
    elif key == "double_top":
        data = _double_top(candles)
    elif key == "double_bottom":
        data = _double_bottom(candles)
    elif key in ("bull_flag", "bull_pennant"):
        data = _flag(candles, bullish=True)
    elif key in ("bear_flag", "bear_pennant"):
        data = _flag(candles, bullish=False)
    elif key == "breakout_retest":
        data = _breakout_retest(candles)
    elif key == "breakdown_retest":
        data = _breakdown_retest(candles)
    elif key == "cup_and_handle":
        data = _cup_handle(candles)
    else:
        data = {"levels": [], "markers": [], "lines": []}

    data["pattern_key"] = pattern_key
    return data

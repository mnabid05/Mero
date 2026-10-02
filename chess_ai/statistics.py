"""Conservative paired score intervals for small engine regression matches."""
from __future__ import annotations

import math
from collections.abc import Sequence


def paired_interval(scores: Sequence[float], z: float = 1.96) -> dict[str, object]:
    """Wilson approximation with one effective observation per color pair.

    This deliberately counts pairs rather than treating both colors as independent.
    Repeated openings and time-control calibration still impose systematic error.
    """
    if len(scores) < 2 or len(scores) % 2 or any(s not in (0, 0.5, 1) for s in scores):
        raise ValueError("scores must contain complete win/draw/loss pairs")
    n = len(scores) // 2
    mean = sum(scores) / len(scores)
    denominator = 1 + z * z / n
    center = (mean + z * z / (2 * n)) / denominator
    half = z * math.sqrt(mean * (1 - mean) / n + z * z / (4 * n * n)) / denominator
    low, high = max(0.0, center - half), min(1.0, center + half)

    def elo(p: float) -> int | None:
        return round(400 * math.log10(p / (1 - p))) if 0 < p < 1 else None

    return {"method": "paired-effective-sample Wilson approximation", "pairs": n,
            "confidence_percent": 95, "score_low": low, "score_high": high,
            "elo_low": elo(low), "elo_high": elo(high)}

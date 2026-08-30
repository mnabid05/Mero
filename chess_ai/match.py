"""Deterministic paired UCI matches for engine regression testing."""

from __future__ import annotations

import argparse
import json
import math
import shlex
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from .backtest import OPENINGS, opening_board, repetition_key
from .gauntlet import UCIEngine
from .model import BLACK, GameStatus, WHITE


@dataclass(frozen=True, slots=True)
class MatchGame:
    game: int
    opening: str
    candidate_color: str
    candidate_score: float
    reason: str
    plies: int
    final_fen: str


@dataclass(frozen=True, slots=True)
class MatchReport:
    candidate: str
    baseline: str
    move_time_ms: int
    games: int
    wins: int
    draws: int
    losses: int
    score_percent: float
    elo_difference: int
    records: tuple[MatchGame, ...]

    def as_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def score_to_elo(score: float) -> int:
    """Convert a bounded fractional score into head-to-head Elo."""
    bounded = min(1 - 1e-6, max(1e-6, score))
    return round(400 * math.log10(bounded / (1 - bounded)))


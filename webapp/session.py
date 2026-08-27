"""In-memory game session state."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from chess_ai.board import Board
from chess_ai.model import BLACK, WHITE, opponent


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class PlayedMove:
    ply: int
    color: str
    uci: str
    san: str


@dataclass(slots=True)
class GameSession:
    id: str
    board: Board
    human_color: str
    difficulty: str
    moves: list[PlayedMove] = field(default_factory=list)
    repetitions: Counter[str] = field(default_factory=Counter)
    resigned_color: str | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @property
    def bot_color(self) -> str:
        return opponent(self.human_color)

    @property
    def human_turn(self) -> bool:
        return self.board.turn == self.human_color

    @classmethod
    def new(cls, identifier: str, human_color: str, difficulty: str) -> "GameSession":
        if human_color not in {WHITE, BLACK}:
            raise ValueError("human_color must be w or b")
        session = cls(identifier, Board.starting(), human_color, difficulty)
        session.record_position()
        return session

    def record_position(self) -> None:
        key = " ".join(self.board.to_fen().split()[:4])
        self.repetitions[key] += 1
        self.updated_at = now_iso()

    def threefold_repetition(self) -> bool:
        return any(count >= 3 for count in self.repetitions.values())

"""Position evaluation and computer move search."""

from __future__ import annotations

from dataclasses import dataclass

from .board import Board
from .model import BLACK, PIECE_VALUES, WHITE, piece_color, row_col

MATE_SCORE = 100_000


@dataclass(slots=True)
class ChessAI:
    """A compact chess engine configured by search depth."""

    depth: int = 3

    def __post_init__(self) -> None:
        if self.depth < 1:
            raise ValueError("Search depth must be at least one ply")

    def evaluate(self, board: Board) -> int:
        """Score a position in centipawns from White's perspective."""
        score = 0
        for square, piece in board.pieces():
            color = piece_color(piece)
            value = PIECE_VALUES[piece.lower()]
            value += self._positional_bonus(square, piece)
            score += value if color == WHITE else -value
        return score

    def _positional_bonus(self, square: int, piece: str) -> int:
        row, column = row_col(square)
        piece_type = piece.lower()

        center_distance = abs(3.5 - row) + abs(3.5 - column)
        center_bonus = int((7 - center_distance) * 4)

        if piece_type == "p":
            advancement = (6 - row) if piece.isupper() else (row - 1)
            return advancement * 7 + max(0, center_bonus // 2)
        if piece_type in {"n", "b"}:
            return center_bonus
        if piece_type == "q":
            return center_bonus // 3
        return 0

    def evaluate_for_turn(self, board: Board) -> int:
        """Score the board from the side-to-move's perspective."""
        score = self.evaluate(board)
        return score if board.turn == WHITE else -score

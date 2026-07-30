"""Position evaluation and computer move search."""

from __future__ import annotations

from dataclasses import dataclass, field

from .board import Board
from .model import Move, PIECE_VALUES, WHITE, piece_color, row_col

MATE_SCORE = 100_000


@dataclass(slots=True)
class ChessAI:
    """A compact chess engine configured by search depth."""

    depth: int = 3
    nodes: int = field(default=0, init=False)

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

    def choose_move(self, board: Board) -> Move | None:
        """Choose the strongest move found at the configured depth."""
        moves = board.legal_moves()
        if not moves:
            return None

        self.nodes = 0
        best_score = -MATE_SCORE
        best_move = moves[0]
        for move in moves:
            score = -self._negamax(
                board.after(move),
                depth=self.depth - 1,
                ply=1,
            )
            if score > best_score:
                best_score = score
                best_move = move
        return best_move

    def _negamax(self, board: Board, depth: int, ply: int) -> int:
        self.nodes += 1
        moves = board.legal_moves()
        if not moves:
            return -MATE_SCORE + ply if board.is_in_check() else 0
        if depth == 0:
            return self.evaluate_for_turn(board)

        best_score = -MATE_SCORE
        for move in moves:
            score = -self._negamax(
                board.after(move),
                depth=depth - 1,
                ply=ply + 1,
            )
            best_score = max(best_score, score)
        return best_score

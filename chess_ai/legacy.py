"""Frozen baseline engine used for strength regression matches."""

from __future__ import annotations

from dataclasses import dataclass, field

from .board import Board
from .model import Move, PIECE_VALUES, WHITE, piece_color, row_col

MATE_SCORE = 100_000


@dataclass(slots=True)
class LegacyAI:
    """The original educational depth-limited minimax engine."""

    depth: int = 3
    nodes: int = field(default=0, init=False)
    cutoffs: int = field(default=0, init=False)

    @property
    def name(self) -> str:
        return f"Legacy minimax (depth {self.depth})"

    def evaluate(self, board: Board) -> int:
        score = 0
        for square, piece in board.pieces():
            value = PIECE_VALUES[piece.lower()]
            row, column = row_col(square)
            center = int((7 - abs(3.5 - row) - abs(3.5 - column)) * 4)
            if piece.lower() == "p":
                advance = 6 - row if piece.isupper() else row - 1
                value += advance * 7 + max(0, center // 2)
            elif piece.lower() in {"n", "b"}:
                value += center
            score += value if piece.isupper() else -value
        return score

    def choose_move(self, board: Board) -> Move | None:
        moves = board.legal_moves()
        if not moves:
            return None
        self.nodes = 0
        self.cutoffs = 0
        best_move = moves[0]
        best_score = -MATE_SCORE
        alpha, beta = -MATE_SCORE, MATE_SCORE
        for move in self._ordered(board, moves):
            score = -self._search(board.after(move), self.depth - 1, -beta, -alpha, 1)
            if score > best_score:
                best_score, best_move = score, move
            alpha = max(alpha, score)
        return best_move

    def _search(
        self,
        board: Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
    ) -> int:
        self.nodes += 1
        moves = board.legal_moves()
        if not moves:
            return -MATE_SCORE + ply if board.is_in_check() else 0
        if depth == 0:
            score = self.evaluate(board)
            return score if board.turn == WHITE else -score

        best = -MATE_SCORE
        for move in self._ordered(board, moves):
            score = -self._search(board.after(move), depth - 1, -beta, -alpha, ply + 1)
            best = max(best, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                self.cutoffs += 1
                break
        return best

    def _ordered(self, board: Board, moves: list[Move]) -> list[Move]:
        def priority(move: Move) -> int:
            attacker = board.squares[move.from_sq]
            victim = board.squares[move.to_sq]
            if move.is_en_passant:
                victim = "p"
            score = 0
            if attacker and victim:
                score += 10 * PIECE_VALUES[victim.lower()]
                score -= PIECE_VALUES[attacker.lower()]
            if move.promotion:
                score += PIECE_VALUES[move.promotion] + 800
            return score

        return sorted(moves, key=priority, reverse=True)

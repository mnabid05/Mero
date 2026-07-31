"""Original tapered evaluation for the native engine."""

from __future__ import annotations

from dataclasses import dataclass

from .board import Board
from .model import BLACK, WHITE, piece_color, row_col, to_index

MG_VALUES = {"p": 100, "n": 325, "b": 335, "r": 500, "q": 975, "k": 0}
EG_VALUES = {"p": 125, "n": 310, "b": 330, "r": 525, "q": 950, "k": 0}
PHASE_VALUES = {"p": 0, "n": 1, "b": 1, "r": 2, "q": 4, "k": 0}
MAX_PHASE = 24


@dataclass(frozen=True, slots=True)
class Evaluation:
    """A tapered score and its major components."""

    score: int
    middlegame: int
    endgame: int
    phase: int


class Evaluator:
    """Evaluate material, activity, pawn structure, and king safety."""

    def evaluate(self, board: Board) -> int:
        return self.explain(board).score

    def evaluate_for_turn(self, board: Board) -> int:
        score = self.evaluate(board)
        return score if board.turn == WHITE else -score

    def explain(self, board: Board) -> Evaluation:
        middle = 0
        end = 0
        phase = 0
        bishops = {WHITE: 0, BLACK: 0}

        for square, piece in board.pieces():
            color = piece_color(piece)
            sign = 1 if color == WHITE else -1
            piece_type = piece.lower()
            phase += PHASE_VALUES[piece_type]
            if piece_type == "b":
                bishops[color] += 1

            middle += sign * (
                MG_VALUES[piece_type]
                + self._square_bonus(square, piece_type, color, endgame=False)
            )
            end += sign * (
                EG_VALUES[piece_type]
                + self._square_bonus(square, piece_type, color, endgame=True)
            )

        for color, sign in ((WHITE, 1), (BLACK, -1)):
            pawn_middle, pawn_end = self._pawn_structure(board, color)
            middle += sign * pawn_middle
            end += sign * pawn_end
            middle += sign * self._rook_files(board, color)
            middle += sign * self._king_shelter(board, color)
            if bishops[color] >= 2:
                middle += sign * 35
                end += sign * 50

        white_mobility = len(board.pseudo_legal_moves(WHITE))
        black_mobility = len(board.pseudo_legal_moves(BLACK))
        mobility = white_mobility - black_mobility
        middle += mobility * 3
        end += mobility * 2

        phase = min(phase, MAX_PHASE)
        score = (middle * phase + end * (MAX_PHASE - phase)) // MAX_PHASE
        return Evaluation(score=score, middlegame=middle, endgame=end, phase=phase)

    def _square_bonus(
        self,
        square: int,
        piece_type: str,
        color: str,
        endgame: bool,
    ) -> int:
        row, column = row_col(square)
        relative_rank = 7 - row if color == WHITE else row
        center = 7 - (abs(3.5 - row) + abs(3.5 - column))
        edge = int(column in (0, 7)) + int(row in (0, 7))

        if piece_type == "p":
            return relative_rank * (13 if endgame else 7) + int(center * 2)
        if piece_type == "n":
            return int(center * (9 if endgame else 11)) - edge * 18
        if piece_type == "b":
            return int(center * 6) + relative_rank * 2
        if piece_type == "r":
            return relative_rank * (4 if endgame else 2)
        if piece_type == "q":
            return int(center * (3 if endgame else 1))
        if piece_type == "k":
            if endgame:
                return int(center * 10)
            castled_file_bonus = 24 if column in (1, 2, 6) else 0
            center_penalty = int(center * 12)
            return castled_file_bonus - center_penalty
        return 0

    def _pawn_structure(self, board: Board, color: str) -> tuple[int, int]:
        pawns = [square for square, piece in board.pieces(color) if piece.lower() == "p"]
        enemy_pawns = [
            square
            for square, piece in board.pieces(BLACK if color == WHITE else WHITE)
            if piece.lower() == "p"
        ]
        files: dict[int, list[int]] = {file_index: [] for file_index in range(8)}
        for square in pawns:
            row, column = row_col(square)
            files[column].append(row)

        middle = 0
        end = 0
        for column, rows in files.items():
            if len(rows) > 1:
                middle -= (len(rows) - 1) * 18
                end -= (len(rows) - 1) * 24
            if rows and not (
                (column > 0 and files[column - 1])
                or (column < 7 and files[column + 1])
            ):
                middle -= len(rows) * 14
                end -= len(rows) * 10

        for square in pawns:
            row, column = row_col(square)
            relative_rank = 7 - row if color == WHITE else row
            if self._is_passed(row, column, color, enemy_pawns):
                middle += 10 + relative_rank * relative_rank * 3
                end += 20 + relative_rank * relative_rank * 7

        return middle, end

    def _is_passed(
        self,
        row: int,
        column: int,
        color: str,
        enemy_pawns: list[int],
    ) -> bool:
        for enemy_square in enemy_pawns:
            enemy_row, enemy_column = row_col(enemy_square)
            if abs(enemy_column - column) > 1:
                continue
            if color == WHITE and enemy_row < row:
                return False
            if color == BLACK and enemy_row > row:
                return False
        return True

    def _rook_files(self, board: Board, color: str) -> int:
        friendly_pawn = "P" if color == WHITE else "p"
        enemy_pawn = "p" if color == WHITE else "P"
        bonus = 0
        for square, piece in board.pieces(color):
            if piece.lower() != "r":
                continue
            _, column = row_col(square)
            file_pieces = [board.squares[row * 8 + column] for row in range(8)]
            if friendly_pawn not in file_pieces:
                bonus += 14
                if enemy_pawn not in file_pieces:
                    bonus += 12
        return bonus

    def _king_shelter(self, board: Board, color: str) -> int:
        king_square = board.king_square(color)
        row, column = row_col(king_square)
        direction = -1 if color == WHITE else 1
        pawn = "P" if color == WHITE else "p"
        shield = 0
        for column_delta in (-1, 0, 1):
            square = to_index(row + direction, column + column_delta)
            if square is not None and board.squares[square] == pawn:
                shield += 14
        return shield

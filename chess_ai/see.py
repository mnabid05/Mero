"""Fast static exchange evaluation for capture ordering."""

from __future__ import annotations

from .board import (
    DIAGONAL_DIRECTIONS,
    KING_DIRECTIONS,
    KNIGHT_OFFSETS,
    ORTHOGONAL_DIRECTIONS,
    Board,
)
from .evaluation import MG_VALUES
from .model import Move, opponent, piece_color, row_col, to_index


def _ray_reaches(
    board: Board,
    source: int,
    target: int,
    directions: tuple[tuple[int, int], ...],
) -> bool:
    source_row, source_column = row_col(source)
    for row_delta, column_delta in directions:
        row = source_row + row_delta
        column = source_column + column_delta
        while True:
            square = to_index(row, column)
            if square is None:
                break
            if square == target:
                return True
            if board.squares[square] is not None:
                break
            row += row_delta
            column += column_delta
    return False


def _attacks(board: Board, source: int, target: int) -> bool:
    piece = board.squares[source]
    if piece is None:
        return False
    piece_type = piece.lower()
    source_row, source_column = row_col(source)
    target_row, target_column = row_col(target)
    row_delta = target_row - source_row
    column_delta = target_column - source_column

    if piece_type == "p":
        direction = -1 if piece.isupper() else 1
        return row_delta == direction and abs(column_delta) == 1
    if piece_type == "n":
        return (row_delta, column_delta) in KNIGHT_OFFSETS
    if piece_type == "k":
        return max(abs(row_delta), abs(column_delta)) == 1
    if piece_type == "b":
        return _ray_reaches(board, source, target, DIAGONAL_DIRECTIONS)
    if piece_type == "r":
        return _ray_reaches(board, source, target, ORTHOGONAL_DIRECTIONS)
    if piece_type == "q":
        return _ray_reaches(board, source, target, KING_DIRECTIONS)
    return False


def _least_valuable_attacker(board: Board, target: int, color: str) -> int | None:
    attackers = [
        square
        for square, piece in board.pieces(color)
        if _attacks(board, square, target)
    ]
    if not attackers:
        return None
    return min(
        attackers,
        key=lambda square: MG_VALUES[board.squares[square].lower()],  # type: ignore[union-attr]
    )


def capture_value(board: Board, move: Move) -> int:
    """Return the immediate material captured or gained by promotion."""
    victim = board.squares[move.to_sq]
    if move.is_en_passant:
        victim = "p"
    value = MG_VALUES[victim.lower()] if victim else 0
    if move.promotion:
        value += MG_VALUES[move.promotion] - MG_VALUES["p"]
    return value


def static_exchange_evaluation(board: Board, move: Move) -> int:
    """Estimate the minimax material result of exchanges on the target square.

    This deliberately ignores absolute pins, making it safe as a move-ordering
    heuristic rather than a legal-move oracle.
    """
    moving_piece = board.squares[move.from_sq]
    if moving_piece is None:
        return 0

    gains = [capture_value(board, move)]
    position = board.after(move)
    target = move.to_sq
    side = position.turn

    while True:
        attacker = _least_valuable_attacker(position, target, side)
        if attacker is None:
            break
        captured = position.squares[target]
        if captured is None:
            break
        gains.append(MG_VALUES[captured.lower()] - gains[-1])
        position.squares[target] = position.squares[attacker]
        position.squares[attacker] = None
        position.turn = opponent(side)
        side = position.turn

    for index in range(len(gains) - 1, 0, -1):
        gains[index - 1] = -max(-gains[index - 1], gains[index])
    return gains[0]

"""Human-readable algebraic notation for the web move list."""

from __future__ import annotations

from chess_ai.board import Board
from chess_ai.model import GameStatus, Move, square_name


def move_to_san(board: Board, move: Move) -> str:
    piece = board.piece_at(move.from_sq)
    if piece is None:
        raise ValueError("move source is empty")
    if move.is_castling:
        notation = "O-O" if move.to_sq > move.from_sq else "O-O-O"
    else:
        piece_type = piece.lower()
        capture = board.piece_at(move.to_sq) is not None or move.is_en_passant
        prefix = "" if piece_type == "p" else piece_type.upper()
        if piece_type == "p" and capture:
            prefix = square_name(move.from_sq)[0]
        if piece_type != "p":
            competitors = [
                candidate
                for candidate in board.legal_moves()
                if candidate != move
                and candidate.to_sq == move.to_sq
                and board.piece_at(candidate.from_sq) is not None
                and board.piece_at(candidate.from_sq).lower() == piece_type
            ]
            if competitors:
                source = square_name(move.from_sq)
                same_file = any(
                    square_name(candidate.from_sq)[0] == source[0]
                    for candidate in competitors
                )
                same_rank = any(
                    square_name(candidate.from_sq)[1] == source[1]
                    for candidate in competitors
                )
                prefix += source if same_file and same_rank else (
                    source[1] if same_file else source[0]
                )
        notation = prefix + ("x" if capture else "") + square_name(move.to_sq)
        if move.promotion:
            notation += "=" + move.promotion.upper()
    resulting = board.after(move)
    if resulting.status() == GameStatus.CHECKMATE:
        notation += "#"
    elif resulting.is_in_check():
        notation += "+"
    return notation

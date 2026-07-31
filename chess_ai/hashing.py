"""Deterministic Zobrist hashing for transposition lookup."""

from __future__ import annotations

import random

from .board import Board
from .model import BLACK, row_col

PIECE_ORDER = "PNBRQKpnbrqk"


class ZobristHasher:
    """Map complete chess positions to stable 64-bit keys."""

    def __init__(self, seed: int = 0xC0DE_CAFE_64) -> None:
        random_source = random.Random(seed)
        self.pieces = tuple(
            tuple(random_source.getrandbits(64) for _ in range(64))
            for _ in PIECE_ORDER
        )
        self.castling = {
            right: random_source.getrandbits(64) for right in "KQkq"
        }
        self.en_passant_files = tuple(
            random_source.getrandbits(64) for _ in range(8)
        )
        self.black_to_move = random_source.getrandbits(64)

    def hash(self, board: Board) -> int:
        key = 0
        for square, piece in board.pieces():
            key ^= self.pieces[PIECE_ORDER.index(piece)][square]
        for right in board.castling_rights:
            key ^= self.castling[right]
        if board.en_passant is not None:
            _, file_index = row_col(board.en_passant)
            key ^= self.en_passant_files[file_index]
        if board.turn == BLACK:
            key ^= self.black_to_move
        return key

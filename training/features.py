"""Shared feature ordering for training and integer inference."""
PIECES = "PNBRQKpnbrqk"
FEATURES = len(PIECES) * 64
PADDING = FEATURES

def flip(index: int) -> int:
    piece, square = divmod(index, 64)
    return ((piece + 6) % 12) * 64 + (square ^ 56)

def indices(board):
    return [PIECES.index(piece) * 64 + square for square, piece in board.pieces()]

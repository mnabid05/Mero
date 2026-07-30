"""Shared chess constants and value objects."""

FILES = "abcdefgh"
RANKS = "87654321"

WHITE = "w"
BLACK = "b"
COLORS = (WHITE, BLACK)


def opponent(color: str) -> str:
    """Return the color opposite *color*."""
    if color not in COLORS:
        raise ValueError(f"Unknown color: {color!r}")
    return BLACK if color == WHITE else WHITE


def parse_square(name: str) -> int:
    """Convert algebraic notation such as ``e4`` to a board index."""
    if len(name) != 2 or name[0] not in FILES or name[1] not in RANKS:
        raise ValueError(f"Invalid square: {name!r}")
    row = 8 - int(name[1])
    column = FILES.index(name[0])
    return row * 8 + column


def square_name(index: int) -> str:
    """Convert a board index to algebraic notation."""
    if not 0 <= index < 64:
        raise ValueError(f"Invalid square index: {index}")
    row, column = divmod(index, 8)
    return f"{FILES[column]}{8 - row}"


def row_col(index: int) -> tuple[int, int]:
    """Return the zero-based row and column for a board index."""
    if not 0 <= index < 64:
        raise ValueError(f"Invalid square index: {index}")
    return divmod(index, 8)


def to_index(row: int, column: int) -> int | None:
    """Return an index for in-bounds coordinates, otherwise ``None``."""
    if 0 <= row < 8 and 0 <= column < 8:
        return row * 8 + column
    return None

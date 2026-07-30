"""Shared chess constants and value objects."""

from dataclasses import dataclass
from enum import Enum

FILES = "abcdefgh"
RANKS = "87654321"

WHITE = "w"
BLACK = "b"
COLORS = (WHITE, BLACK)

PIECE_TYPES = "pnbrqk"
PIECE_VALUES = {
    "p": 100,
    "n": 320,
    "b": 330,
    "r": 500,
    "q": 900,
    "k": 0,
}

UNICODE_PIECES = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
    "k": "♚",
    "q": "♛",
    "r": "♜",
    "b": "♝",
    "n": "♞",
    "p": "♟",
}


class GameStatus(str, Enum):
    """Terminal and non-terminal states understood by the game."""

    ACTIVE = "active"
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    DRAW_FIFTY_MOVE = "draw by fifty-move rule"
    DRAW_INSUFFICIENT_MATERIAL = "draw by insufficient material"


def opponent(color: str) -> str:
    """Return the color opposite *color*."""
    if color not in COLORS:
        raise ValueError(f"Unknown color: {color!r}")
    return BLACK if color == WHITE else WHITE


def piece_color(piece: str) -> str:
    """Return the color of a one-character piece symbol."""
    if len(piece) != 1 or piece.lower() not in PIECE_TYPES:
        raise ValueError(f"Invalid piece: {piece!r}")
    return WHITE if piece.isupper() else BLACK


def make_piece(piece_type: str, color: str) -> str:
    """Create a board symbol for a piece type and color."""
    if piece_type.lower() not in PIECE_TYPES or color not in COLORS:
        raise ValueError(f"Invalid piece request: {piece_type!r}, {color!r}")
    return piece_type.upper() if color == WHITE else piece_type.lower()


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


@dataclass(frozen=True, slots=True)
class Move:
    """A chess move expressed as source, destination, and optional metadata."""

    from_sq: int
    to_sq: int
    promotion: str | None = None
    is_en_passant: bool = False
    is_castling: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.from_sq < 64 or not 0 <= self.to_sq < 64:
            raise ValueError("Move squares must be between 0 and 63")
        if self.promotion is not None and self.promotion.lower() not in "qrbn":
            raise ValueError(f"Invalid promotion piece: {self.promotion!r}")

    @property
    def uci(self) -> str:
        """Return long algebraic notation such as ``e2e4`` or ``a7a8q``."""
        suffix = self.promotion.lower() if self.promotion else ""
        return f"{square_name(self.from_sq)}{square_name(self.to_sq)}{suffix}"

    @classmethod
    def from_uci(cls, notation: str) -> "Move":
        """Parse coordinate notation without yet checking board legality."""
        normalized = notation.strip().lower()
        if len(normalized) not in (4, 5):
            raise ValueError("Moves use notation like e2e4 or a7a8q")
        promotion = normalized[4] if len(normalized) == 5 else None
        return cls(
            parse_square(normalized[:2]),
            parse_square(normalized[2:4]),
            promotion=promotion,
        )

    def __str__(self) -> str:
        return self.uci

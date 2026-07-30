"""Board state and chess rule implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import BLACK, FILES, UNICODE_PIECES, WHITE, piece_color

STARTING_BACK_RANK = "rnbqkbnr"


@dataclass(slots=True)
class Board:
    """A complete chess position using a flat 64-square board."""

    squares: list[str | None] = field(default_factory=lambda: [None] * 64)
    turn: str = WHITE
    castling_rights: set[str] = field(default_factory=lambda: set("KQkq"))
    en_passant: int | None = None
    halfmove_clock: int = 0
    fullmove_number: int = 1

    def __post_init__(self) -> None:
        if len(self.squares) != 64:
            raise ValueError("A chess board must contain exactly 64 squares")
        if self.turn not in (WHITE, BLACK):
            raise ValueError(f"Invalid side to move: {self.turn!r}")
        if not self.castling_rights <= set("KQkq"):
            raise ValueError("Castling rights must be drawn from KQkq")

    @classmethod
    def starting(cls) -> "Board":
        """Create the standard initial chess position."""
        squares: list[str | None] = [None] * 64
        squares[0:8] = list(STARTING_BACK_RANK)
        squares[8:16] = ["p"] * 8
        squares[48:56] = ["P"] * 8
        squares[56:64] = list(STARTING_BACK_RANK.upper())
        return cls(squares=squares)

    def copy(self) -> "Board":
        """Return an independent copy suitable for search."""
        return Board(
            squares=self.squares.copy(),
            turn=self.turn,
            castling_rights=self.castling_rights.copy(),
            en_passant=self.en_passant,
            halfmove_clock=self.halfmove_clock,
            fullmove_number=self.fullmove_number,
        )

    def piece_at(self, square: int) -> str | None:
        """Return the piece at *square*, if any."""
        if not 0 <= square < 64:
            raise ValueError(f"Invalid square index: {square}")
        return self.squares[square]

    def king_square(self, color: str) -> int:
        """Return the current location of a color's king."""
        king = "K" if color == WHITE else "k"
        try:
            return self.squares.index(king)
        except ValueError as error:
            raise ValueError(f"Position has no {color} king") from error

    def pieces(self, color: str | None = None):
        """Yield ``(square, piece)`` pairs, optionally filtered by color."""
        for square, piece in enumerate(self.squares):
            if piece is not None and (color is None or piece_color(piece) == color):
                yield square, piece

    def render(self, perspective: str = WHITE, unicode: bool = True) -> str:
        """Render the board with coordinates from either perspective."""
        if perspective not in (WHITE, BLACK):
            raise ValueError(f"Invalid perspective: {perspective!r}")

        rows = range(8) if perspective == WHITE else range(7, -1, -1)
        columns = range(8) if perspective == WHITE else range(7, -1, -1)
        output: list[str] = []

        for row in rows:
            rank = 8 - row
            cells: list[str] = []
            for column in columns:
                piece = self.squares[row * 8 + column]
                if piece is None:
                    cells.append("·")
                elif unicode:
                    cells.append(UNICODE_PIECES[piece])
                else:
                    cells.append(piece)
            output.append(f"{rank}  {' '.join(cells)}")

        ordered_files = FILES if perspective == WHITE else FILES[::-1]
        output.append(f"\n   {' '.join(ordered_files)}")
        return "\n".join(output)

    def __str__(self) -> str:
        return self.render()

"""Board state and chess rule implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import (
    BLACK,
    FILES,
    Move,
    PIECE_TYPES,
    UNICODE_PIECES,
    WHITE,
    make_piece,
    opponent,
    parse_square,
    piece_color,
    row_col,
    square_name,
    to_index,
)

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
KNIGHT_OFFSETS = (
    (-2, -1),
    (-2, 1),
    (-1, -2),
    (-1, 2),
    (1, -2),
    (1, 2),
    (2, -1),
    (2, 1),
)
DIAGONAL_DIRECTIONS = ((-1, -1), (-1, 1), (1, -1), (1, 1))
ORTHOGONAL_DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))
KING_DIRECTIONS = DIAGONAL_DIRECTIONS + ORTHOGONAL_DIRECTIONS


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
        return cls.from_fen(STARTING_FEN)

    @classmethod
    def from_fen(cls, fen: str) -> "Board":
        """Create a board from Forsyth-Edwards Notation."""
        fields = fen.strip().split()
        if len(fields) != 6:
            raise ValueError("FEN must contain six space-separated fields")

        placement, turn, castling, en_passant, halfmove, fullmove = fields
        rows = placement.split("/")
        if len(rows) != 8:
            raise ValueError("FEN placement must contain eight ranks")

        squares: list[str | None] = []
        for row in rows:
            rank: list[str | None] = []
            for token in row:
                if token.isdigit():
                    count = int(token)
                    if not 1 <= count <= 8:
                        raise ValueError("FEN empty-square counts must be 1 through 8")
                    rank.extend([None] * count)
                elif token.lower() in PIECE_TYPES:
                    rank.append(token)
                else:
                    raise ValueError(f"Invalid FEN placement token: {token!r}")
            if len(rank) != 8:
                raise ValueError("Every FEN rank must describe exactly eight squares")
            squares.extend(rank)

        rights = set() if castling == "-" else set(castling)
        target = None if en_passant == "-" else parse_square(en_passant)
        return cls(
            squares=squares,
            turn=turn,
            castling_rights=rights,
            en_passant=target,
            halfmove_clock=int(halfmove),
            fullmove_number=int(fullmove),
        )

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

    def to_fen(self) -> str:
        """Serialize the complete position to Forsyth-Edwards Notation."""
        ranks: list[str] = []
        for row in range(8):
            tokens: list[str] = []
            empty = 0
            for column in range(8):
                piece = self.squares[row * 8 + column]
                if piece is None:
                    empty += 1
                    continue
                if empty:
                    tokens.append(str(empty))
                    empty = 0
                tokens.append(piece)
            if empty:
                tokens.append(str(empty))
            ranks.append("".join(tokens))

        castling = "".join(right for right in "KQkq" if right in self.castling_rights)
        en_passant = square_name(self.en_passant) if self.en_passant is not None else "-"
        return " ".join(
            (
                "/".join(ranks),
                self.turn,
                castling or "-",
                en_passant,
                str(self.halfmove_clock),
                str(self.fullmove_number),
            )
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

    def push(self, move: Move) -> None:
        """Apply a move in place and advance the game clock."""
        piece = self.squares[move.from_sq]
        if piece is None:
            raise ValueError(f"No piece on {square_name(move.from_sq)}")
        moving_color = piece_color(piece)
        if moving_color != self.turn:
            raise ValueError("The selected piece does not belong to the side to move")

        captured = self.squares[move.to_sq]
        self.squares[move.from_sq] = None
        self.squares[move.to_sq] = (
            make_piece(move.promotion, moving_color) if move.promotion else piece
        )

        if piece.lower() == "p" or captured is not None:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        from_row, _ = row_col(move.from_sq)
        to_row, _ = row_col(move.to_sq)
        if piece.lower() == "p" and abs(to_row - from_row) == 2:
            self.en_passant = (move.from_sq + move.to_sq) // 2
        else:
            self.en_passant = None

        if moving_color == BLACK:
            self.fullmove_number += 1
        self.turn = opponent(moving_color)

    def after(self, move: Move) -> "Board":
        """Return a copied position with *move* applied."""
        position = self.copy()
        position.push(move)
        return position

    def pseudo_legal_moves(self, color: str | None = None) -> list[Move]:
        """Generate moves without checking whether the king is exposed."""
        moving_color = color or self.turn
        moves: list[Move] = []
        for square, piece in self.pieces(moving_color):
            if piece.lower() == "p":
                moves.extend(self._pawn_moves(square, moving_color))
            elif piece.lower() == "n":
                moves.extend(self._knight_moves(square, moving_color))
            elif piece.lower() == "b":
                moves.extend(
                    self._sliding_moves(square, moving_color, DIAGONAL_DIRECTIONS)
                )
            elif piece.lower() == "r":
                moves.extend(
                    self._sliding_moves(square, moving_color, ORTHOGONAL_DIRECTIONS)
                )
            elif piece.lower() == "q":
                moves.extend(
                    self._sliding_moves(
                        square,
                        moving_color,
                        KING_DIRECTIONS,
                    )
                )
            elif piece.lower() == "k":
                moves.extend(self._king_moves(square, moving_color))
        return moves

    def _pawn_moves(self, square: int, color: str) -> list[Move]:
        row, column = row_col(square)
        direction = -1 if color == WHITE else 1
        start_row = 6 if color == WHITE else 1
        promotion_row = 0 if color == WHITE else 7
        moves: list[Move] = []

        one_step = to_index(row + direction, column)
        if one_step is not None and self.squares[one_step] is None:
            self._add_pawn_move(moves, square, one_step, promotion_row)
            two_step = to_index(row + 2 * direction, column)
            if row == start_row and two_step is not None and self.squares[two_step] is None:
                moves.append(Move(square, two_step))

        for column_delta in (-1, 1):
            target = to_index(row + direction, column + column_delta)
            if target is None:
                continue
            occupant = self.squares[target]
            if occupant is not None and piece_color(occupant) != color:
                self._add_pawn_move(moves, square, target, promotion_row)

        return moves

    def _add_pawn_move(
        self,
        moves: list[Move],
        from_sq: int,
        to_sq: int,
        promotion_row: int,
    ) -> None:
        target_row, _ = row_col(to_sq)
        if target_row == promotion_row:
            for piece_type in "qrbn":
                moves.append(Move(from_sq, to_sq, promotion=piece_type))
        else:
            moves.append(Move(from_sq, to_sq))

    def _knight_moves(self, square: int, color: str) -> list[Move]:
        row, column = row_col(square)
        moves: list[Move] = []
        for row_delta, column_delta in KNIGHT_OFFSETS:
            target = to_index(row + row_delta, column + column_delta)
            if target is None:
                continue
            occupant = self.squares[target]
            if occupant is None or piece_color(occupant) != color:
                moves.append(Move(square, target))
        return moves

    def _sliding_moves(
        self,
        square: int,
        color: str,
        directions: tuple[tuple[int, int], ...],
    ) -> list[Move]:
        row, column = row_col(square)
        moves: list[Move] = []
        for row_delta, column_delta in directions:
            distance = 1
            while True:
                target = to_index(
                    row + row_delta * distance,
                    column + column_delta * distance,
                )
                if target is None:
                    break
                occupant = self.squares[target]
                if occupant is None:
                    moves.append(Move(square, target))
                else:
                    if piece_color(occupant) != color:
                        moves.append(Move(square, target))
                    break
                distance += 1
        return moves

    def _king_moves(self, square: int, color: str) -> list[Move]:
        row, column = row_col(square)
        moves: list[Move] = []
        for row_delta, column_delta in KING_DIRECTIONS:
            target = to_index(row + row_delta, column + column_delta)
            if target is None:
                continue
            occupant = self.squares[target]
            if occupant is None or piece_color(occupant) != color:
                moves.append(Move(square, target))
        return moves

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

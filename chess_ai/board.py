"""Board state and chess rule implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import (
    BLACK,
    FILES,
    GameStatus,
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
        captured_square = move.to_sq
        if move.is_en_passant:
            captured_square = move.to_sq + (8 if moving_color == WHITE else -8)
            captured = self.squares[captured_square]
            self.squares[captured_square] = None

        self.squares[move.from_sq] = None
        self.squares[move.to_sq] = (
            make_piece(move.promotion, moving_color) if move.promotion else piece
        )

        if move.is_castling:
            rook_from, rook_to = {
                parse_square("g1"): (parse_square("h1"), parse_square("f1")),
                parse_square("c1"): (parse_square("a1"), parse_square("d1")),
                parse_square("g8"): (parse_square("h8"), parse_square("f8")),
                parse_square("c8"): (parse_square("a8"), parse_square("d8")),
            }[move.to_sq]
            self.squares[rook_to] = self.squares[rook_from]
            self.squares[rook_from] = None

        if piece.lower() == "k":
            if moving_color == WHITE:
                self.castling_rights.difference_update("KQ")
            else:
                self.castling_rights.difference_update("kq")

        rook_rights = {
            parse_square("h1"): "K",
            parse_square("a1"): "Q",
            parse_square("h8"): "k",
            parse_square("a8"): "q",
        }
        moved_rook_right = rook_rights.get(move.from_sq)
        captured_rook_right = rook_rights.get(captured_square)
        if piece.lower() == "r" and moved_rook_right:
            self.castling_rights.discard(moved_rook_right)
        if captured is not None and captured.lower() == "r" and captured_rook_right:
            self.castling_rights.discard(captured_rook_right)

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

    def is_square_attacked(self, square: int, by_color: str) -> bool:
        """Return whether *square* is attacked by *by_color*."""
        row, column = row_col(square)

        pawn_source_row = row + (1 if by_color == WHITE else -1)
        pawn = make_piece("p", by_color)
        for column_delta in (-1, 1):
            source = to_index(pawn_source_row, column + column_delta)
            if source is not None and self.squares[source] == pawn:
                return True

        knight = make_piece("n", by_color)
        for row_delta, column_delta in KNIGHT_OFFSETS:
            source = to_index(row + row_delta, column + column_delta)
            if source is not None and self.squares[source] == knight:
                return True

        king = make_piece("k", by_color)
        for row_delta, column_delta in KING_DIRECTIONS:
            source = to_index(row + row_delta, column + column_delta)
            if source is not None and self.squares[source] == king:
                return True

        if self._ray_attacked(
            row,
            column,
            by_color,
            DIAGONAL_DIRECTIONS,
            attackers={"b", "q"},
        ):
            return True
        return self._ray_attacked(
            row,
            column,
            by_color,
            ORTHOGONAL_DIRECTIONS,
            attackers={"r", "q"},
        )

    def _ray_attacked(
        self,
        row: int,
        column: int,
        by_color: str,
        directions: tuple[tuple[int, int], ...],
        attackers: set[str],
    ) -> bool:
        for row_delta, column_delta in directions:
            distance = 1
            while True:
                source = to_index(
                    row + row_delta * distance,
                    column + column_delta * distance,
                )
                if source is None:
                    break
                piece = self.squares[source]
                if piece is not None:
                    if piece_color(piece) == by_color and piece.lower() in attackers:
                        return True
                    break
                distance += 1
        return False

    def is_in_check(self, color: str | None = None) -> bool:
        """Return whether a color's king is currently attacked."""
        checked_color = color or self.turn
        return self.is_square_attacked(
            self.king_square(checked_color),
            opponent(checked_color),
        )

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

    def legal_moves(self, color: str | None = None) -> list[Move]:
        """Generate moves that leave the moving side's king safe."""
        moving_color = color or self.turn
        legal: list[Move] = []
        for move in self.pseudo_legal_moves(moving_color):
            candidate = self.copy()
            candidate.turn = moving_color
            candidate.push(move)
            if not candidate.is_in_check(moving_color):
                legal.append(move)
        return legal

    def is_legal(self, move: Move) -> bool:
        """Return whether *move* is legal in the current position."""
        return move in self.legal_moves()

    def find_legal_move(self, notation: str) -> Move:
        """Resolve UCI notation to the fully annotated legal move."""
        requested = Move.from_uci(notation)
        for move in self.legal_moves():
            if move.uci == requested.uci:
                return move
        raise ValueError(f"Illegal move: {notation!r}")

    def play_uci(self, notation: str) -> Move:
        """Validate and play a UCI move, returning the applied move."""
        move = self.find_legal_move(notation)
        self.push(move)
        return move

    def status(self) -> GameStatus:
        """Return the current game status."""
        moves = self.legal_moves()
        if not moves:
            return GameStatus.CHECKMATE if self.is_in_check() else GameStatus.STALEMATE
        if self.halfmove_clock >= 100:
            return GameStatus.DRAW_FIFTY_MOVE
        if self._has_insufficient_material():
            return GameStatus.DRAW_INSUFFICIENT_MATERIAL
        return GameStatus.ACTIVE

    def _has_insufficient_material(self) -> bool:
        non_kings = [
            (square, piece)
            for square, piece in self.pieces()
            if piece.lower() != "k"
        ]
        if not non_kings:
            return True
        if len(non_kings) == 1 and non_kings[0][1].lower() in {"b", "n"}:
            return True
        if non_kings and all(piece.lower() == "b" for _, piece in non_kings):
            square_colors = {(sum(row_col(square)) % 2) for square, _ in non_kings}
            return len(square_colors) == 1
        return False

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
            elif target == self.en_passant:
                captured_square = target + (8 if color == WHITE else -8)
                if self.squares[captured_square] == make_piece("p", opponent(color)):
                    moves.append(Move(square, target, is_en_passant=True))

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
        moves.extend(self._castling_moves(square, color))
        return moves

    def _castling_moves(self, square: int, color: str) -> list[Move]:
        enemy = opponent(color)
        plans = (
            (
                WHITE,
                "K",
                "e1",
                "h1",
                ("f1", "g1"),
                ("e1", "f1", "g1"),
                "g1",
            ),
            (
                WHITE,
                "Q",
                "e1",
                "a1",
                ("b1", "c1", "d1"),
                ("e1", "d1", "c1"),
                "c1",
            ),
            (
                BLACK,
                "k",
                "e8",
                "h8",
                ("f8", "g8"),
                ("e8", "f8", "g8"),
                "g8",
            ),
            (
                BLACK,
                "q",
                "e8",
                "a8",
                ("b8", "c8", "d8"),
                ("e8", "d8", "c8"),
                "c8",
            ),
        )
        moves: list[Move] = []
        for (
            plan_color,
            right,
            king_name,
            rook_name,
            empty_names,
            safe_names,
            target_name,
        ) in plans:
            if color != plan_color or right not in self.castling_rights:
                continue
            king_square = parse_square(king_name)
            rook_square = parse_square(rook_name)
            if square != king_square:
                continue
            if self.squares[rook_square] != make_piece("r", color):
                continue
            if any(self.squares[parse_square(name)] is not None for name in empty_names):
                continue
            if any(
                self.is_square_attacked(parse_square(name), enemy)
                for name in safe_names
            ):
                continue
            moves.append(
                Move(
                    square,
                    parse_square(target_name),
                    is_castling=True,
                )
            )
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

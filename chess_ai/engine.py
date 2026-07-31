"""Advanced original search engine."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from .board import Board
from .evaluation import Evaluator, MG_VALUES
from .hashing import ZobristHasher
from .model import BLACK, Move, WHITE, opponent, piece_color

INFINITY = 1_000_000
MATE_SCORE = 100_000
MATE_THRESHOLD = 90_000
MAX_QUIESCENCE_DEPTH = 10


class Bound(str, Enum):
    EXACT = "exact"
    LOWER = "lower"
    UPPER = "upper"


@dataclass(frozen=True, slots=True)
class TTEntry:
    depth: int
    score: int
    bound: Bound
    best_move: Move | None


@dataclass(frozen=True, slots=True)
class SearchResult:
    move: Move | None
    score: int
    depth: int
    nodes: int
    qnodes: int
    tt_hits: int
    cutoffs: int
    elapsed_ms: int
    principal_variation: tuple[Move, ...]


class SearchTimeout(Exception):
    """Internal control flow used to stop at the time limit."""


@dataclass(slots=True)
class ChessAI:
    """Original engine with modern alpha-beta search techniques."""

    depth: int = 6
    movetime_ms: int = 1000
    table_capacity: int = 250_000
    evaluator: Evaluator = field(default_factory=Evaluator)
    hasher: ZobristHasher = field(default_factory=ZobristHasher)
    nodes: int = field(default=0, init=False)
    qnodes: int = field(default=0, init=False)
    tt_hits: int = field(default=0, init=False)
    cutoffs: int = field(default=0, init=False)
    depth_reached: int = field(default=0, init=False)
    elapsed_ms: int = field(default=0, init=False)
    score: int = field(default=0, init=False)
    principal_variation: tuple[Move, ...] = field(default=(), init=False)
    _table: dict[int, TTEntry] = field(default_factory=dict, init=False, repr=False)
    _killers: dict[int, list[Move]] = field(default_factory=dict, init=False, repr=False)
    _history: dict[tuple[str, int], int] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _deadline: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.depth < 1:
            raise ValueError("Search depth must be at least one")
        if self.movetime_ms < 10:
            raise ValueError("Move time must be at least 10 ms")
        if self.table_capacity < 1_000:
            raise ValueError("Transposition table capacity must be at least 1,000")

    @property
    def name(self) -> str:
        return f"Mwahaha native engine (depth {self.depth})"

    @property
    def last_result(self) -> SearchResult:
        move = self.principal_variation[0] if self.principal_variation else None
        return SearchResult(
            move=move,
            score=self.score,
            depth=self.depth_reached,
            nodes=self.nodes,
            qnodes=self.qnodes,
            tt_hits=self.tt_hits,
            cutoffs=self.cutoffs,
            elapsed_ms=self.elapsed_ms,
            principal_variation=self.principal_variation,
        )

    def reset(self, clear_table: bool = False) -> None:
        self.nodes = 0
        self.qnodes = 0
        self.tt_hits = 0
        self.cutoffs = 0
        self.depth_reached = 0
        self.elapsed_ms = 0
        self.score = 0
        self.principal_variation = ()
        self._killers.clear()
        self._history.clear()
        if clear_table:
            self._table.clear()

    def close(self) -> None:
        """Match the engine lifecycle interface."""

    def evaluate(self, board: Board) -> int:
        return self.evaluator.evaluate(board)

    def choose_move(self, board: Board) -> Move | None:
        legal = board.legal_moves()
        if not legal:
            return None

        self.reset()
        if len(self._table) > self.table_capacity:
            self._table.clear()

        started = time.perf_counter()
        self._deadline = started + self.movetime_ms / 1000
        best_move = self._order_moves(board, legal, None, 0)[0]
        best_score = -INFINITY
        previous_score = 0

        for current_depth in range(1, self.depth + 1):
            window = 45 if current_depth >= 3 else INFINITY
            alpha = max(-INFINITY, previous_score - window)
            beta = min(INFINITY, previous_score + window)

            while True:
                try:
                    score, move = self._root_search(
                        board,
                        current_depth,
                        alpha,
                        beta,
                    )
                except SearchTimeout:
                    self.elapsed_ms = int((time.perf_counter() - started) * 1000)
                    self.principal_variation = self._extract_pv(board, self.depth_reached)
                    if not self.principal_variation:
                        self.principal_variation = (best_move,)
                    return best_move

                if score <= alpha and alpha > -INFINITY:
                    window *= 2
                    alpha = max(-INFINITY, score - window)
                    continue
                if score >= beta and beta < INFINITY:
                    window *= 2
                    beta = min(INFINITY, score + window)
                    continue
                break

            best_score = score
            best_move = move
            previous_score = score
            self.depth_reached = current_depth
            self.score = score
            self.principal_variation = self._extract_pv(board, current_depth)

            if abs(score) >= MATE_THRESHOLD:
                break

        self.elapsed_ms = int((time.perf_counter() - started) * 1000)
        self.score = best_score
        if not self.principal_variation:
            self.principal_variation = (best_move,)
        return best_move

    def _root_search(
        self,
        board: Board,
        depth: int,
        alpha: int,
        beta: int,
    ) -> tuple[int, Move]:
        self._check_time(force=True)
        key = self.hasher.hash(board)
        table_move = self._table.get(key)
        moves = self._order_moves(
            board,
            board.legal_moves(),
            table_move.best_move if table_move else None,
            0,
        )
        best_move = moves[0]
        best_score = -INFINITY
        original_alpha = alpha
        path = {key: 1}

        for index, move in enumerate(moves):
            child = board.after(move)
            if index == 0:
                score = -self._search(child, depth - 1, -beta, -alpha, 1, path)
            else:
                score = -self._search(child, depth - 1, -alpha - 1, -alpha, 1, path)
                if alpha < score < beta:
                    score = -self._search(child, depth - 1, -beta, -alpha, 1, path)

            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                self.cutoffs += 1
                break

        bound = Bound.EXACT
        if best_score <= original_alpha:
            bound = Bound.UPPER
        elif best_score >= beta:
            bound = Bound.LOWER
        self._store(key, TTEntry(depth, best_score, bound, best_move))
        return best_score, best_move

    def _search(
        self,
        board: Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
        path: dict[int, int],
        allow_null: bool = True,
    ) -> int:
        self.nodes += 1
        self._check_time()
        key = self.hasher.hash(board)
        prior_visits = path.get(key, 0)
        if prior_visits >= 2 or board.halfmove_clock >= 100:
            return 0

        in_check = board.is_in_check()
        if depth <= 0:
            return self._quiescence(board, alpha, beta, ply, 0, path)
        if in_check and depth <= 2:
            depth += 1

        entry = self._table.get(key)
        if entry and entry.depth >= depth:
            self.tt_hits += 1
            if entry.bound == Bound.EXACT:
                return entry.score
            if entry.bound == Bound.LOWER and entry.score >= beta:
                return entry.score
            if entry.bound == Bound.UPPER and entry.score <= alpha:
                return entry.score

        moves = board.legal_moves()
        if not moves:
            return -MATE_SCORE + ply if in_check else 0
        if board._has_insufficient_material():
            return 0

        if (
            allow_null
            and depth >= 3
            and not in_check
            and beta < MATE_THRESHOLD
            and self._has_non_pawn_material(board)
        ):
            null_board = self._null_move(board)
            reduction = 2 + depth // 5
            score = -self._search(
                null_board,
                depth - 1 - reduction,
                -beta,
                -beta + 1,
                ply + 1,
                path,
                allow_null=False,
            )
            if score >= beta:
                self.cutoffs += 1
                return score

        original_alpha = alpha
        best_score = -INFINITY
        best_move: Move | None = None
        table_move = entry.best_move if entry else None
        ordered = self._order_moves(board, moves, table_move, ply)
        path[key] = prior_visits + 1

        try:
            for index, move in enumerate(ordered):
                quiet = self._is_quiet(board, move)
                child = board.after(move)
                next_depth = depth - 1
                reduction = 0
                if (
                    depth >= 3
                    and index >= 4
                    and quiet
                    and not in_check
                    and not move.promotion
                ):
                    reduction = 1 + int(depth >= 6 and index >= 8)

                if index == 0:
                    score = -self._search(
                        child,
                        next_depth,
                        -beta,
                        -alpha,
                        ply + 1,
                        path,
                    )
                else:
                    score = -self._search(
                        child,
                        next_depth - reduction,
                        -alpha - 1,
                        -alpha,
                        ply + 1,
                        path,
                    )
                    if reduction and score > alpha:
                        score = -self._search(
                            child,
                            next_depth,
                            -alpha - 1,
                            -alpha,
                            ply + 1,
                            path,
                        )
                    if alpha < score < beta:
                        score = -self._search(
                            child,
                            next_depth,
                            -beta,
                            -alpha,
                            ply + 1,
                            path,
                        )

                if score > best_score:
                    best_score = score
                    best_move = move
                if score > alpha:
                    alpha = score
                    if quiet:
                        piece = board.squares[move.from_sq]
                        if piece:
                            history_key = (piece, move.to_sq)
                            self._history[history_key] = (
                                self._history.get(history_key, 0) + depth * depth
                            )
                if alpha >= beta:
                    self.cutoffs += 1
                    if quiet:
                        self._record_killer(move, ply)
                    break
        finally:
            if prior_visits:
                path[key] = prior_visits
            else:
                path.pop(key, None)

        bound = Bound.EXACT
        if best_score <= original_alpha:
            bound = Bound.UPPER
        elif best_score >= beta:
            bound = Bound.LOWER
        self._store(key, TTEntry(depth, best_score, bound, best_move))
        return best_score

    def _quiescence(
        self,
        board: Board,
        alpha: int,
        beta: int,
        ply: int,
        qdepth: int,
        path: dict[int, int],
    ) -> int:
        self.qnodes += 1
        self._check_time()
        in_check = board.is_in_check()
        stand_pat = self.evaluator.evaluate_for_turn(board)

        if not in_check:
            if stand_pat >= beta:
                return stand_pat
            alpha = max(alpha, stand_pat)
            if qdepth >= MAX_QUIESCENCE_DEPTH:
                return stand_pat

        legal = board.legal_moves()
        if not legal:
            return -MATE_SCORE + ply if in_check else 0

        if in_check:
            moves = legal
        else:
            moves = [
                move
                for move in legal
                if not self._is_quiet(board, move) or move.promotion
            ]
        if not moves:
            return stand_pat

        ordered = self._order_moves(board, moves, None, ply)
        for move in ordered:
            score = -self._quiescence(
                board.after(move),
                -beta,
                -alpha,
                ply + 1,
                qdepth + 1,
                path,
            )
            if score >= beta:
                return score
            alpha = max(alpha, score)
        return alpha

    def _order_moves(
        self,
        board: Board,
        moves: list[Move],
        table_move: Move | None,
        ply: int,
    ) -> list[Move]:
        killers = self._killers.get(ply, [])

        def priority(move: Move) -> int:
            if move == table_move:
                return 10_000_000
            piece = board.squares[move.from_sq]
            victim = board.squares[move.to_sq]
            if move.is_en_passant:
                victim = "p" if piece and piece.isupper() else "P"
            score = 0
            if victim and piece:
                score += 1_000_000
                score += 16 * MG_VALUES[victim.lower()] - MG_VALUES[piece.lower()]
            if move.promotion:
                score += 900_000 + MG_VALUES[move.promotion]
            if move in killers:
                score += 700_000 - killers.index(move) * 1_000
            if piece:
                score += self._history.get((piece, move.to_sq), 0)
            if move.is_castling:
                score += 25_000
            return score

        return sorted(moves, key=priority, reverse=True)

    def _record_killer(self, move: Move, ply: int) -> None:
        killers = self._killers.setdefault(ply, [])
        if move in killers:
            killers.remove(move)
        killers.insert(0, move)
        del killers[2:]

    def _is_quiet(self, board: Board, move: Move) -> bool:
        return (
            board.squares[move.to_sq] is None
            and not move.is_en_passant
            and move.promotion is None
        )

    def _has_non_pawn_material(self, board: Board) -> bool:
        return any(
            piece.lower() not in {"p", "k"}
            for _, piece in board.pieces(board.turn)
        )

    def _null_move(self, board: Board) -> Board:
        position = board.copy()
        moving_color = position.turn
        position.turn = opponent(position.turn)
        position.en_passant = None
        position.halfmove_clock += 1
        if moving_color == BLACK:
            position.fullmove_number += 1
        return position

    def _store(self, key: int, entry: TTEntry) -> None:
        existing = self._table.get(key)
        if existing is None or entry.depth >= existing.depth:
            if len(self._table) >= self.table_capacity and key not in self._table:
                self._table.pop(next(iter(self._table)))
            self._table[key] = entry

    def _extract_pv(self, board: Board, depth: int) -> tuple[Move, ...]:
        position = board.copy()
        variation: list[Move] = []
        seen: set[int] = set()
        for _ in range(depth):
            key = self.hasher.hash(position)
            if key in seen:
                break
            seen.add(key)
            entry = self._table.get(key)
            if entry is None or entry.best_move is None:
                break
            legal = position.legal_moves()
            if entry.best_move not in legal:
                break
            variation.append(entry.best_move)
            position.push(entry.best_move)
        return tuple(variation)

    def _check_time(self, force: bool = False) -> None:
        if force or ((self.nodes + self.qnodes) & 255) == 0:
            if time.perf_counter() >= self._deadline:
                raise SearchTimeout

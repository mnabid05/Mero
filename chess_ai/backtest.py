"""Color-balanced strength regression for the original engine."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from .board import Board
from .engine import ChessAI
from .legacy import LegacyAI
from .model import BLACK, GameStatus, Move, WHITE

OPENINGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Open Game", ("e2e4", "e7e5", "g1f3", "b8c6")),
    ("Queen's Gambit", ("d2d4", "d7d5", "c2c4", "e7e6")),
    ("English Opening", ("c2c4", "e7e5", "b1c3", "g8f6")),
    ("King's Indian Attack", ("g1f3", "d7d5", "g2g3", "c7c5")),
    ("Sicilian Defense", ("e2e4", "c7c5", "g1f3", "d7d6")),
    ("King's Indian Defense", ("d2d4", "g8f6", "c2c4", "g7g6")),
)


class MatchEngine(Protocol):
    name: str

    def choose_move(self, board: Board) -> Move | None: ...

    def reset(self) -> None: ...


@dataclass(frozen=True, slots=True)
class GameRecord:
    game: int
    opening: str
    candidate_color: str
    result: str
    winner: str | None
    reason: str
    plies: int
    final_fen: str


@dataclass(frozen=True, slots=True)
class MatchReport:
    candidate: str
    candidate_depth: int
    candidate_movetime_ms: int
    baseline: str
    baseline_depth: int
    games: int
    max_plies: int
    candidate_wins: int
    draws: int
    baseline_wins: int
    candidate_score_percent: float
    records: tuple[GameRecord, ...]

    def as_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def opening_board(moves: Sequence[str]) -> Board:
    board = Board.starting()
    for notation in moves:
        board.play_uci(notation)
    return board


def repetition_key(board: Board) -> str:
    return " ".join(board.to_fen().split()[:4])


def play_game(
    white: MatchEngine,
    black: MatchEngine,
    opening_name: str,
    opening_moves: Sequence[str],
    game_number: int,
    candidate_color: str,
    max_plies: int,
) -> GameRecord:
    white.reset()
    black.reset()
    board = opening_board(opening_moves)
    repetitions: Counter[str] = Counter({repetition_key(board): 1})

    for played in range(max_plies):
        status = board.status()
        if status != GameStatus.ACTIVE:
            break
        engine = white if board.turn == WHITE else black
        move = engine.choose_move(board)
        if move is None:
            break
        board.push(move)
        repetitions[repetition_key(board)] += 1
        if repetitions[repetition_key(board)] >= 3:
            return GameRecord(
                game_number,
                opening_name,
                "white" if candidate_color == WHITE else "black",
                "1/2-1/2",
                None,
                "threefold repetition",
                len(opening_moves) + played + 1,
                board.to_fen(),
            )
    else:
        return GameRecord(
            game_number,
            opening_name,
            "white" if candidate_color == WHITE else "black",
            "1/2-1/2",
            None,
            "maximum plies",
            len(opening_moves) + max_plies,
            board.to_fen(),
        )

    status = board.status()
    if status == GameStatus.CHECKMATE:
        winning_color = BLACK if board.turn == WHITE else WHITE
        winner = white.name if winning_color == WHITE else black.name
        result = "1-0" if winning_color == WHITE else "0-1"
    else:
        winner = None
        result = "1/2-1/2"
    return GameRecord(
        game_number,
        opening_name,
        "white" if candidate_color == WHITE else "black",
        result,
        winner,
        status.value,
        len(opening_moves) + played,
        board.to_fen(),
    )


def run_match(
    candidate: ChessAI,
    baseline: LegacyAI,
    games: int = 8,
    max_plies: int = 160,
    show_progress: bool = False,
) -> MatchReport:
    if games < 2 or games % 2:
        raise ValueError("Games must be a positive even number")
    records: list[GameRecord] = []
    for index in range(games):
        opening_name, opening_moves = OPENINGS[(index // 2) % len(OPENINGS)]
        candidate_color = WHITE if index % 2 == 0 else BLACK
        white: MatchEngine = candidate if candidate_color == WHITE else baseline
        black: MatchEngine = baseline if candidate_color == WHITE else candidate
        record = play_game(
            white,
            black,
            opening_name,
            opening_moves,
            index + 1,
            candidate_color,
            max_plies,
        )
        records.append(record)
        if show_progress:
            print(
                f"Game {index + 1}/{games}: {record.result} "
                f"({opening_name}, candidate as {record.candidate_color}, "
                f"{record.reason}, {record.plies} plies)"
            )

    candidate_wins = sum(record.winner == candidate.name for record in records)
    baseline_wins = sum(record.winner == baseline.name for record in records)
    draws = games - candidate_wins - baseline_wins
    score = (candidate_wins + 0.5 * draws) / games * 100
    return MatchReport(
        candidate=candidate.name,
        candidate_depth=candidate.depth,
        candidate_movetime_ms=candidate.movetime_ms,
        baseline=baseline.name,
        baseline_depth=baseline.depth,
        games=games,
        max_plies=max_plies,
        candidate_wins=candidate_wins,
        draws=draws,
        baseline_wins=baseline_wins,
        candidate_score_percent=round(score, 2),
        records=tuple(records),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backtest the advanced native engine against its baseline."
    )
    parser.add_argument("--games", type=int, default=8)
    parser.add_argument("--move-time", type=int, default=100, metavar="MS")
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--baseline-depth", type=int, default=2)
    parser.add_argument("--max-plies", type=int, default=160)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    candidate = ChessAI(depth=args.depth, movetime_ms=args.move_time)
    baseline = LegacyAI(depth=args.baseline_depth)
    report = run_match(
        candidate,
        baseline,
        games=args.games,
        max_plies=args.max_plies,
        show_progress=True,
    )
    print(
        "\nResult: "
        f"{report.candidate_wins} wins, {report.draws} draws, "
        f"{report.baseline_wins} losses "
        f"({report.candidate_score_percent:.2f}% score)."
    )
    if args.json_out:
        args.json_out.write_text(f"{report.as_json()}\n", encoding="utf-8")
        print(f"Report written to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

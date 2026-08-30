"""Deterministic paired UCI matches for engine regression testing."""

from __future__ import annotations

import argparse
import json
import math
import shlex
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from .backtest import OPENINGS, opening_board, repetition_key
from .gauntlet import UCIEngine
from .model import BLACK, GameStatus, WHITE


@dataclass(frozen=True, slots=True)
class MatchGame:
    game: int
    opening: str
    candidate_color: str
    candidate_score: float
    reason: str
    plies: int
    final_fen: str


@dataclass(frozen=True, slots=True)
class MatchReport:
    candidate: str
    baseline: str
    move_time_ms: int
    games: int
    wins: int
    draws: int
    losses: int
    score_percent: float
    elo_difference: int
    records: tuple[MatchGame, ...]

    def as_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def score_to_elo(score: float) -> int:
    """Convert a bounded fractional score into head-to-head Elo."""
    bounded = min(1 - 1e-6, max(1e-6, score))
    return round(400 * math.log10(bounded / (1 - bounded)))


def _play_game(
    candidate: UCIEngine,
    baseline: UCIEngine,
    game_number: int,
    opening_name: str,
    opening_moves: Sequence[str],
    candidate_color: str,
    move_time_ms: int,
    max_plies: int,
) -> MatchGame:
    candidate.new_game()
    baseline.new_game()
    board = opening_board(opening_moves)
    repetitions: Counter[str] = Counter({repetition_key(board): 1})

    for played in range(max_plies):
        status = board.status()
        if status != GameStatus.ACTIVE:
            break
        candidate_turn = board.turn == candidate_color
        engine = candidate if candidate_turn else baseline
        try:
            notation = engine.choose_move(board, move_time_ms)
            move = board.find_legal_move(notation)
        except (RuntimeError, ValueError) as error:
            return MatchGame(
                game_number,
                opening_name,
                "white" if candidate_color == WHITE else "black",
                0.0 if candidate_turn else 1.0,
                f"engine forfeit: {error}",
                len(opening_moves) + played,
                board.to_fen(),
            )
        board.push(move)
        key = repetition_key(board)
        repetitions[key] += 1
        if repetitions[key] >= 3:
            return MatchGame(
                game_number,
                opening_name,
                "white" if candidate_color == WHITE else "black",
                0.5,
                "threefold repetition",
                len(opening_moves) + played + 1,
                board.to_fen(),
            )
    else:
        return MatchGame(
            game_number,
            opening_name,
            "white" if candidate_color == WHITE else "black",
            0.5,
            "maximum plies",
            len(opening_moves) + max_plies,
            board.to_fen(),
        )

    status = board.status()
    candidate_score = 0.5
    if status == GameStatus.CHECKMATE:
        winner = BLACK if board.turn == WHITE else WHITE
        candidate_score = 1.0 if winner == candidate_color else 0.0
    return MatchGame(
        game_number,
        opening_name,
        "white" if candidate_color == WHITE else "black",
        candidate_score,
        status.value,
        len(opening_moves) + played,
        board.to_fen(),
    )


def run_match(
    candidate_command: Sequence[str],
    baseline_command: Sequence[str],
    games: int,
    move_time_ms: int,
    max_plies: int,
    threads: int = 1,
    show_progress: bool = False,
) -> MatchReport:
    if games < 2 or games % 2:
        raise ValueError("games must be a positive even number")
    if move_time_ms < 10:
        raise ValueError("move time must be at least 10 ms")
    if not 1 <= threads <= 64:
        raise ValueError("threads must be between 1 and 64")

    records: list[MatchGame] = []
    options = {"Threads": threads, "Hash": 64, "Move Overhead": 0}
    with UCIEngine(candidate_command, options) as candidate, UCIEngine(
        baseline_command, options
    ) as baseline:
        for index in range(games):
            opening_name, opening_moves = OPENINGS[(index // 2) % len(OPENINGS)]
            record = _play_game(
                candidate,
                baseline,
                index + 1,
                opening_name,
                opening_moves,
                WHITE if index % 2 == 0 else BLACK,
                move_time_ms,
                max_plies,
            )
            records.append(record)
            if show_progress:
                print(
                    f"Game {index + 1}/{games}: candidate {record.candidate_score:g} "
                    f"as {record.candidate_color} ({record.reason}, {record.plies} plies)",
                    flush=True,
                )

    wins = sum(record.candidate_score == 1 for record in records)
    draws = sum(record.candidate_score == 0.5 for record in records)
    losses = games - wins - draws
    score = (wins + 0.5 * draws) / games
    return MatchReport(
        candidate.name,
        baseline.name,
        move_time_ms,
        games,
        wins,
        draws,
        losses,
        round(score * 100, 2),
        score_to_elo(score),
        tuple(records),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, help="candidate UCI command")
    parser.add_argument("--baseline", required=True, help="baseline UCI command")
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument("--move-time", type=int, default=30, metavar="MS")
    parser.add_argument("--max-plies", type=int, default=160)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    report = run_match(
        shlex.split(args.candidate),
        shlex.split(args.baseline),
        args.games,
        args.move_time,
        args.max_plies,
        threads=args.threads,
        show_progress=True,
    )
    print(
        f"\nResult: {report.wins} wins, {report.draws} draws, "
        f"{report.losses} losses ({report.score_percent:.2f}% score, "
        f"{report.elo_difference:+d} Elo)."
    )
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(report.as_json() + "\n", encoding="utf-8")
        print(f"Report written to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

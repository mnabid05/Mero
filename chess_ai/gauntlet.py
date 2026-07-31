"""Color-balanced UCI gauntlet against calibrated external opponents."""

from __future__ import annotations

import argparse
import json
import math
import shlex
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from .backtest import OPENINGS, opening_board, repetition_key
from .board import Board
from .model import BLACK, GameStatus, WHITE, opponent


@dataclass(frozen=True, slots=True)
class GauntletGame:
    game: int
    opponent_elo: int
    opening: str
    candidate_color: str
    result: str
    candidate_score: float
    reason: str
    plies: int
    final_fen: str


@dataclass(frozen=True, slots=True)
class LevelResult:
    opponent_elo: int
    games: int
    wins: int
    draws: int
    losses: int
    score_percent: float


@dataclass(frozen=True, slots=True)
class RatingEstimate:
    elo: int
    confidence_low: int
    confidence_high: int
    confidence_percent: int


@dataclass(frozen=True, slots=True)
class GauntletReport:
    candidate: str
    opponent: str
    move_time_ms: int
    max_plies: int
    total_games: int
    wins: int
    draws: int
    losses: int
    score_percent: float
    estimate: RatingEstimate
    levels: tuple[LevelResult, ...]
    games: tuple[GauntletGame, ...]

    def as_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


class UCIEngine:
    """Small synchronous UCI process client used only by the test harness."""

    def __init__(
        self,
        command: Sequence[str],
        options: dict[str, str | int | bool] | None = None,
    ) -> None:
        if not command:
            raise ValueError("Engine command cannot be empty")
        self.command = tuple(command)
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self.name = " ".join(command)
        self._send("uci")
        for line in self._read_until("uciok"):
            if line.startswith("id name "):
                self.name = line.removeprefix("id name ")
        for option, value in (options or {}).items():
            normalized = str(value).lower() if isinstance(value, bool) else str(value)
            self._send(f"setoption name {option} value {normalized}")
        self._send("isready")
        self._read_until("readyok")

    def _send(self, command: str) -> None:
        if self.process.stdin is None:
            raise RuntimeError("UCI engine stdin is unavailable")
        self.process.stdin.write(f"{command}\n")
        self.process.stdin.flush()

    def _read_until(self, prefix: str) -> list[str]:
        if self.process.stdout is None:
            raise RuntimeError("UCI engine stdout is unavailable")
        lines: list[str] = []
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(
                    f"Engine exited before replying with {prefix!r}: {self.command}"
                )
            stripped = line.strip()
            lines.append(stripped)
            if stripped.startswith(prefix):
                return lines

    def new_game(self) -> None:
        self._send("ucinewgame")
        self._send("isready")
        self._read_until("readyok")

    def choose_move(self, board: Board, move_time_ms: int) -> str:
        self._send(f"position fen {board.to_fen()}")
        self._send(f"go movetime {move_time_ms}")
        response = self._read_until("bestmove")[-1].split()
        if len(response) < 2:
            raise RuntimeError(f"Malformed bestmove response from {self.name}")
        return response[1]

    def set_option(self, name: str, value: str | int | bool) -> None:
        normalized = str(value).lower() if isinstance(value, bool) else str(value)
        self._send(f"setoption name {name} value {normalized}")
        self._send("isready")
        self._read_until("readyok")

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self._send("quit")
                self.process.wait(timeout=2)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                self.process.terminate()
                self.process.wait(timeout=2)

    def __enter__(self) -> "UCIEngine":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def estimate_rating(
    results: Sequence[tuple[int, float]],
    confidence_z: float = 1.96,
) -> RatingEstimate:
    """Fit one Elo value by maximum likelihood against known opponent ratings."""
    if not results:
        raise ValueError("At least one result is required")

    slope = math.log(10) / 400

    def expected(rating: float, opponent: int) -> float:
        return 1 / (1 + math.exp(-slope * (rating - opponent)))

    low = min(opponent for opponent, _ in results) - 1600.0
    high = max(opponent for opponent, _ in results) + 1600.0
    for _ in range(100):
        middle = (low + high) / 2
        gradient = sum(
            score - expected(middle, opponent)
            for opponent, score in results
        )
        if gradient > 0:
            low = middle
        else:
            high = middle
    rating = (low + high) / 2
    information = sum(
        slope * slope
        * expected(rating, opponent)
        * (1 - expected(rating, opponent))
        for opponent, _ in results
    )
    standard_error = 1 / math.sqrt(max(information, 1e-12))
    return RatingEstimate(
        elo=round(rating),
        confidence_low=round(rating - confidence_z * standard_error),
        confidence_high=round(rating + confidence_z * standard_error),
        confidence_percent=95,
    )


def _play_game(
    candidate: UCIEngine,
    opponent: UCIEngine,
    opponent_elo: int,
    game_number: int,
    opening_name: str,
    opening_moves: Sequence[str],
    candidate_color: str,
    move_time_ms: int,
    max_plies: int,
) -> GauntletGame:
    candidate.new_game()
    opponent.new_game()
    board = opening_board(opening_moves)
    repetitions: Counter[str] = Counter({repetition_key(board): 1})

    for played in range(max_plies):
        status = board.status()
        if status != GameStatus.ACTIVE:
            break
        candidate_turn = board.turn == candidate_color
        engine = candidate if candidate_turn else opponent
        try:
            notation = engine.choose_move(board, move_time_ms)
            move = board.find_legal_move(notation)
        except (RuntimeError, ValueError) as error:
            candidate_score = 0.0 if candidate_turn else 1.0
            candidate_wins = candidate_score == 1.0
            winning_color = (
                candidate_color if candidate_wins else opponent(candidate_color)
            )
            return GauntletGame(
                game_number,
                opponent_elo,
                opening_name,
                "white" if candidate_color == WHITE else "black",
                "1-0" if winning_color == WHITE else "0-1",
                candidate_score,
                f"engine forfeit: {error}",
                len(opening_moves) + played,
                board.to_fen(),
            )
        board.push(move)
        key = repetition_key(board)
        repetitions[key] += 1
        if repetitions[key] >= 3:
            return GauntletGame(
                game_number,
                opponent_elo,
                opening_name,
                "white" if candidate_color == WHITE else "black",
                "1/2-1/2",
                0.5,
                "threefold repetition",
                len(opening_moves) + played + 1,
                board.to_fen(),
            )
    else:
        return GauntletGame(
            game_number,
            opponent_elo,
            opening_name,
            "white" if candidate_color == WHITE else "black",
            "1/2-1/2",
            0.5,
            "maximum plies",
            len(opening_moves) + max_plies,
            board.to_fen(),
        )

    status = board.status()
    if status == GameStatus.CHECKMATE:
        winning_color = BLACK if board.turn == WHITE else WHITE
        candidate_score = 1.0 if winning_color == candidate_color else 0.0
        result = "1-0" if winning_color == WHITE else "0-1"
    else:
        candidate_score = 0.5
        result = "1/2-1/2"
    return GauntletGame(
        game_number,
        opponent_elo,
        opening_name,
        "white" if candidate_color == WHITE else "black",
        result,
        candidate_score,
        status.value,
        len(opening_moves) + played,
        board.to_fen(),
    )


def run_gauntlet(
    candidate_command: Sequence[str],
    opponent_command: Sequence[str],
    opponent_elos: Sequence[int],
    games_per_level: int,
    move_time_ms: int,
    max_plies: int,
    show_progress: bool = False,
) -> GauntletReport:
    if games_per_level < 2 or games_per_level % 2:
        raise ValueError("Games per level must be a positive even number")
    if not opponent_elos:
        raise ValueError("At least one opponent Elo is required")
    if move_time_ms < 10:
        raise ValueError("Move time must be at least 10 ms")

    games: list[GauntletGame] = []
    with UCIEngine(
        candidate_command,
        {"Hash": 64, "Move Overhead": 0},
    ) as candidate, UCIEngine(
        opponent_command,
        {
            "Threads": 1,
            "Hash": 64,
            "Move Overhead": 0,
            "UCI_LimitStrength": True,
            "UCI_Elo": opponent_elos[0],
        },
    ) as opponent:
        game_number = 0
        for elo in opponent_elos:
            opponent.set_option("UCI_Elo", elo)
            for index in range(games_per_level):
                game_number += 1
                opening_name, opening_moves = OPENINGS[
                    (index // 2) % len(OPENINGS)
                ]
                candidate_color = WHITE if index % 2 == 0 else BLACK
                record = _play_game(
                    candidate,
                    opponent,
                    elo,
                    game_number,
                    opening_name,
                    opening_moves,
                    candidate_color,
                    move_time_ms,
                    max_plies,
                )
                games.append(record)
                if show_progress:
                    print(
                        f"Game {game_number}/"
                        f"{games_per_level * len(opponent_elos)}: "
                        f"candidate {record.candidate_score:g} vs Elo {elo} "
                        f"as {record.candidate_color} "
                        f"({record.reason}, {record.plies} plies)",
                        flush=True,
                    )

        level_results: list[LevelResult] = []
        rating_inputs: list[tuple[int, float]] = []
        for elo in opponent_elos:
            level_games = [game for game in games if game.opponent_elo == elo]
            wins = sum(game.candidate_score == 1 for game in level_games)
            draws = sum(game.candidate_score == 0.5 for game in level_games)
            losses = len(level_games) - wins - draws
            score = (wins + 0.5 * draws) / len(level_games) * 100
            level_results.append(
                LevelResult(elo, len(level_games), wins, draws, losses, round(score, 2))
            )
            rating_inputs.extend((elo, game.candidate_score) for game in level_games)

        wins = sum(game.candidate_score == 1 for game in games)
        draws = sum(game.candidate_score == 0.5 for game in games)
        losses = len(games) - wins - draws
        score = (wins + 0.5 * draws) / len(games) * 100
        return GauntletReport(
            candidate.name,
            opponent.name,
            move_time_ms,
            max_plies,
            len(games),
            wins,
            draws,
            losses,
            round(score, 2),
            estimate_rating(rating_inputs),
            tuple(level_results),
            tuple(games),
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        default=f"{shlex.quote(sys.executable)} -m chess_ai.uci",
        help="candidate UCI command",
    )
    parser.add_argument("--opponent", required=True, help="opponent UCI command")
    parser.add_argument(
        "--opponent-elo",
        type=int,
        action="append",
        dest="opponent_elos",
        default=None,
        help="limited-strength opponent Elo; repeat for multiple levels",
    )
    parser.add_argument("--games-per-level", type=int, default=20)
    parser.add_argument("--move-time", type=int, default=50, metavar="MS")
    parser.add_argument("--max-plies", type=int, default=160)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    report = run_gauntlet(
        shlex.split(args.candidate),
        shlex.split(args.opponent),
        args.opponent_elos or [1320, 1500, 1700],
        args.games_per_level,
        args.move_time,
        args.max_plies,
        show_progress=True,
    )
    print(
        f"\nResult: {report.wins} wins, {report.draws} draws, "
        f"{report.losses} losses ({report.score_percent:.2f}% score)."
    )
    print(
        f"Estimated Elo: {report.estimate.elo} "
        f"({report.estimate.confidence_percent}% CI "
        f"{report.estimate.confidence_low}–{report.estimate.confidence_high})."
    )
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(f"{report.as_json()}\n", encoding="utf-8")
        print(f"Report written to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

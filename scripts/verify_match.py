"""Replay a match JSON report: python -m scripts.verify_match REPORT.json."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from chess_ai.board import Board
from chess_ai.backtest import repetition_key
from chess_ai.model import GameStatus, WHITE


def verify_report(report: dict) -> int:
    records = report.get("records", report.get("games"))
    if not isinstance(records, list) or not records:
        raise ValueError("report needs game records")
    scores = []
    for number, record in enumerate(records, 1):
        if "moves" not in record:
            raise ValueError(f"game {number}: missing replay")
        board = Board.starting()
        repetitions = Counter({repetition_key(board): 1})
        for notation in record["moves"]:
            board.play_uci(notation)
            repetitions[repetition_key(board)] += 1
        if board.to_fen() != record["final_fen"]:
            raise ValueError(f"game {number}: final FEN does not match replay")
        if record["plies"] != len(record["moves"]):
            raise ValueError(f"game {number}: incorrect ply count")
        status = board.status()
        reason = record["reason"]
        if reason == "threefold repetition":
            if repetitions[repetition_key(board)] < 3:
                raise ValueError(f"game {number}: repetition not present")
        elif reason == "maximum plies":
            if status != GameStatus.ACTIVE:
                raise ValueError(f"game {number}: terminal position marked as capped")
        elif reason != status.value:
            raise ValueError(f"game {number}: result reason does not match board")
        expected = 0.5
        if status == GameStatus.CHECKMATE:
            candidate_white = record["candidate_color"] == "white"
            expected = float((board.turn == WHITE) != candidate_white)
        if record["candidate_score"] != expected:
            raise ValueError(f"game {number}: incorrect score")
        scores.append(expected)
    for field, value in (("wins", 1), ("draws", 0.5), ("losses", 0)):
        if report[field] != scores.count(value):
            raise ValueError(f"incorrect aggregate {field}")
    if report["score_percent"] != round(100 * sum(scores) / len(scores), 2):
        raise ValueError("incorrect aggregate score")
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    count = verify_report(json.loads(args.report.read_text()))
    print(f"Verified {count} complete legal replays and result totals")


if __name__ == "__main__":
    main()

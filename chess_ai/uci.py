"""Universal Chess Interface entry point for chess GUIs."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from .board import Board
from .engine import ChessAI
from .model import WHITE


def parse_position(command: str) -> Board:
    tokens = command.split()
    if len(tokens) < 2:
        raise ValueError("position command is incomplete")

    moves_index: int | None = None
    if tokens[1] == "startpos":
        board = Board.starting()
        if "moves" in tokens:
            moves_index = tokens.index("moves") + 1
    elif tokens[1] == "fen":
        if "moves" in tokens:
            marker = tokens.index("moves")
            fen_tokens = tokens[2:marker]
            moves_index = marker + 1
        else:
            fen_tokens = tokens[2:]
        board = Board.from_fen(" ".join(fen_tokens))
    else:
        raise ValueError("position must use startpos or fen")

    if moves_index is not None:
        for notation in tokens[moves_index:]:
            board.play_uci(notation)
    return board


def time_budget(command: str, board: Board, overhead_ms: int) -> int | None:
    tokens = command.split()
    if "movetime" in tokens:
        return max(10, int(tokens[tokens.index("movetime") + 1]) - overhead_ms)

    clock_name = "wtime" if board.turn == WHITE else "btime"
    increment_name = "winc" if board.turn == WHITE else "binc"
    if clock_name not in tokens:
        return None

    remaining = int(tokens[tokens.index(clock_name) + 1])
    increment = (
        int(tokens[tokens.index(increment_name) + 1])
        if increment_name in tokens
        else 0
    )
    moves_to_go = (
        int(tokens[tokens.index("movestogo") + 1])
        if "movestogo" in tokens
        else 30
    )
    allocation = remaining // max(8, moves_to_go) + int(increment * 0.75)
    return max(10, min(remaining // 2, allocation) - overhead_ms)


def go(engine: ChessAI, board: Board, command: str, overhead_ms: int) -> None:
    tokens = command.split()
    original_depth = engine.depth
    original_time = engine.movetime_ms
    try:
        if "depth" in tokens:
            engine.depth = max(1, int(tokens[tokens.index("depth") + 1]))
            engine.movetime_ms = max(engine.movetime_ms, 60_000)
        budget = time_budget(command, board, overhead_ms)
        if budget is not None:
            engine.movetime_ms = budget

        move = engine.choose_move(board)
        if move is None:
            print("bestmove 0000", flush=True)
            return

        result = engine.last_result
        nodes = result.nodes + result.qnodes
        nps = nodes * 1000 // max(1, result.elapsed_ms)
        pv = " ".join(candidate.uci for candidate in result.principal_variation)
        print(
            f"info depth {result.depth} score cp {result.score} "
            f"nodes {nodes} nps {nps} time {result.elapsed_ms} pv {pv}",
            flush=True,
        )
        print(f"bestmove {move.uci}", flush=True)
    finally:
        engine.depth = original_depth
        engine.movetime_ms = original_time


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    engine = ChessAI()
    board = Board.starting()
    overhead_ms = 20

    for raw_line in sys.stdin:
        command = raw_line.strip()
        if command == "uci":
            print("id name Mero Chess Engine 3.0 Reference")
            print("id author Mohammed Nabid")
            print("option name Hash type spin default 64 min 1 max 1024")
            print("option name Move Overhead type spin default 20 min 0 max 5000")
            print("uciok", flush=True)
        elif command == "isready":
            print("readyok", flush=True)
        elif command == "ucinewgame":
            board = Board.starting()
            engine.reset(clear_table=True)
        elif command.startswith("setoption name Hash value "):
            megabytes = int(command.rsplit(" ", 1)[1])
            engine.table_capacity = max(1_000, megabytes * 4_000)
        elif command.startswith("setoption name Move Overhead value "):
            overhead_ms = max(0, int(command.rsplit(" ", 1)[1]))
        elif command.startswith("position "):
            try:
                board = parse_position(command)
            except ValueError as error:
                print(f"info string position error: {error}", flush=True)
        elif command.startswith("go"):
            go(engine, board, command, overhead_ms)
        elif command == "quit":
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

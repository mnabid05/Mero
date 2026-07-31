"""Move-generator performance test utilities."""

from __future__ import annotations

import argparse
import time
from collections.abc import Sequence

from .board import Board


def perft(board: Board, depth: int) -> int:
    if depth < 0:
        raise ValueError("Perft depth cannot be negative")
    if depth == 0:
        return 1
    return sum(perft(board.after(move), depth - 1) for move in board.legal_moves())


def divide(board: Board, depth: int) -> dict[str, int]:
    if depth < 1:
        raise ValueError("Divide depth must be at least one")
    return {
        move.uci: perft(board.after(move), depth - 1)
        for move in board.legal_moves()
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run legal-move perft validation.")
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--fen")
    parser.add_argument("--divide", action="store_true")
    args = parser.parse_args(argv)
    board = Board.from_fen(args.fen) if args.fen else Board.starting()
    started = time.perf_counter()
    if args.divide:
        branches = divide(board, args.depth)
        for move, count in branches.items():
            print(f"{move}: {count}")
        nodes = sum(branches.values())
    else:
        nodes = perft(board, args.depth)
    elapsed = time.perf_counter() - started
    print(
        f"depth {args.depth}: {nodes:,} nodes in {elapsed:.3f}s "
        f"({int(nodes / max(elapsed, 1e-9)):,} nps)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

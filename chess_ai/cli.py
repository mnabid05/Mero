"""Interactive terminal interface for Simple Chess AI."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from .board import Board
from .engine import ChessAI
from .model import BLACK, GameStatus, WHITE

HELP_TEXT = """\
Enter moves in coordinate notation:
  e2e4       move a piece
  a7a8q      promote a pawn

Commands:
  moves      list every legal move
  fen        print the current FEN
  help       show this help
  quit       leave the game
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Play chess against a minimax AI.")
    parser.add_argument(
        "--depth",
        type=int,
        default=3,
        help="AI search depth in plies (default: 3)",
    )
    parser.add_argument(
        "--color",
        choices=("white", "black"),
        default="white",
        help="your side (default: white)",
    )
    parser.add_argument(
        "--fen",
        help="start from a custom FEN instead of the initial position",
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="use letters instead of Unicode chess pieces",
    )
    return parser


def result_message(board: Board, status: GameStatus) -> str:
    if status == GameStatus.CHECKMATE:
        winner = "Black" if board.turn == WHITE else "White"
        return f"Checkmate — {winner} wins."
    if status == GameStatus.STALEMATE:
        return "Stalemate — the game is a draw."
    return f"{status.value.capitalize()}."


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        board = Board.from_fen(args.fen) if args.fen else Board.starting()
        ai = ChessAI(depth=args.depth)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    human_color = WHITE if args.color == "white" else BLACK
    use_unicode = not args.ascii

    print("Simple Chess AI")
    print("Type 'help' for commands.\n")

    while True:
        print(board.render(perspective=human_color, unicode=use_unicode))
        if board.is_in_check():
            print("\nCheck!")

        status = board.status()
        if status != GameStatus.ACTIVE:
            print(f"\n{result_message(board, status)}")
            return 0

        if board.turn != human_color:
            print(f"\nAI is thinking at depth {ai.depth}...")
            move = ai.choose_move(board)
            if move is None:
                return 0
            board.push(move)
            print(f"AI plays {move.uci} ({ai.nodes:,} nodes, {ai.cutoffs:,} cutoffs).\n")
            continue

        try:
            entry = input("\nYour move: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nGood game.")
            return 0

        if entry in {"quit", "exit", "q"}:
            print("Good game.")
            return 0
        if entry in {"help", "?"}:
            print(f"\n{HELP_TEXT}")
            continue
        if entry == "fen":
            print(f"\n{board.to_fen()}\n")
            continue
        if entry == "moves":
            print("\n" + " ".join(move.uci for move in board.legal_moves()) + "\n")
            continue

        try:
            board.play_uci(entry)
        except ValueError as error:
            print(f"\n{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())

# Mwahaha Chess Engine

A self-contained original chess engine written in Python.

No Stockfish, engine wrappers, chess libraries, or external runtime dependencies.

## Features

- Complete legal move generation with check and pin filtering
- Castling, en passant, and all four promotion choices
- Checkmate, stalemate, fifty-move, and insufficient-material detection
- FEN position import and export
- Minimax search with alpha-beta pruning and move ordering
- Material and piece-activity evaluation
- White or Black play, Unicode or ASCII boards, and configurable AI depth
- Standard-library-only runtime with automated tests

## Play

Python 3.11 or newer is required. No third-party packages are needed.

```bash
python3 -m chess_ai
```

Moves use UCI coordinate notation:

```text
Your move: e2e4
Your move: g1f3
Your move: a7a8q
```

Useful options:

```bash
python3 -m chess_ai --color black
python3 -m chess_ai --depth 4
python3 -m chess_ai --ascii
python3 -m chess_ai --fen "7k/8/8/8/8/8/q7/R6K w - - 0 1"
```

Inside the game, enter `moves`, `fen`, `help`, or `quit` for utility commands.

## Install a command

```bash
python3 -m pip install .
simple-chess
```

## Test

```bash
python3 -m unittest discover -v
```

The test suite covers coordinate conversion, FEN round trips, legal move counts,
pins, checkmate, stalemate, castling, en passant, promotion, draw detection, and
AI move selection.

## How the AI works

The engine scores material in centipawns, adds small activity bonuses, and searches
future positions using negamax. Alpha-beta bounds skip branches that cannot change
the result, while captures and promotions are searched first to make that pruning
more effective.

The default depth of three plies keeps moves responsive on ordinary hardware.
Increase `--depth` for stronger but slower play.

## Project layout

```text
chess_ai/
  board.py    board state, FEN, move generation, and game rules
  model.py    chess constants, coordinates, pieces, and moves
  engine.py   evaluation and alpha-beta search
  cli.py      interactive terminal game
tests/        standard-library unittest suite
```

## License

MIT

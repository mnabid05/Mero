# Mwahaha Chess Engine

A self-contained original chess engine written in Python.

**No Stockfish. No engine wrapper. No chess library. No runtime dependency.**

The project implements its own board representation, legal move generator,
evaluation, search, time management, UCI protocol, terminal game, and strength
regression harness.

## Search

- Iterative deepening with hard move-time control
- Principal variation search
- Alpha-beta pruning with aspiration windows
- Zobrist-keyed transposition table
- Quiescence search for tactical stability
- Null-move pruning
- Late-move reductions
- Check extensions
- Killer-move and history heuristics
- MVV-LVA capture ordering
- Repetition and fifty-move detection inside search

## Evaluation

- Tapered middlegame/endgame scoring
- Phase-specific material values
- Algorithmic piece-square placement
- Doubled, isolated, and passed pawns
- Bishop pair
- Open and semi-open rook files
- King shelter
- Mobility

## Chess rules

- Fully legal move generation with check and pin filtering
- Castling, en passant, and all four promotion choices
- Checkmate, stalemate, fifty-move, and insufficient-material detection
- FEN import/export
- Standard UCI coordinate moves

## Play

Python 3.11 or newer is required.

```bash
python3 -m chess_ai --move-time 1000 --depth 6
```

Moves use coordinate notation:

```text
Your move: e2e4
Your move: g1f3
Your move: a7a8q
```

Useful options:

```bash
python3 -m chess_ai --color black
python3 -m chess_ai --move-time 3000 --depth 8
python3 -m chess_ai --ascii
python3 -m chess_ai --fen "7k/8/8/8/8/8/q7/R6K w - - 0 1"
```

Inside the game, enter `moves`, `fen`, `help`, or `quit`.

## Use with a chess GUI

The engine exposes the Universal Chess Interface:

```bash
python3 -m chess_ai.uci
```

After installation, configure the `mwahaha-uci` executable in a UCI-compatible
GUI.

```bash
python3 -m pip install .
mwahaha-chess
mwahaha-uci
```

## Validation

Run the 33-test suite:

```bash
python3 -m unittest discover -v
```

Validate the legal move generator:

```bash
python3 -m chess_ai.perft --depth 4
```

The standard starting position matches the canonical counts:

| Depth | Positions |
| ---: | ---: |
| 1 | 20 |
| 2 | 400 |
| 3 | 8,902 |

## Backtesting

The repository freezes its original minimax engine as `LegacyAI` solely for
regression matches.

```bash
python3 -m chess_ai.backtest \
  --games 8 \
  --move-time 100 \
  --depth 6 \
  --baseline-depth 2 \
  --json-out backtest.json
```

Checked-in results:

| Match | Wins | Draws | Losses | Score |
| --- | ---: | ---: | ---: | ---: |
| Native engine vs legacy depth 3 | 4 | 0 | 0 | 100% |
| Native engine vs legacy depth 2 | 7 | 1 | 0 | 93.75% |

Both matches alternate colors within paired openings. Every decisive game ended
in checkmate. See [strength methodology](docs/STRENGTH.md) and the
[machine-readable reports](backtests/).

These results prove a large improvement over the original engine; they do not
establish a human-platform Elo rating. Strength must be built through continued
matches against progressively stronger independent opponents.

## Project layout

```text
chess_ai/
  board.py       board state, FEN, move generation, and game rules
  model.py       chess constants, coordinates, pieces, and moves
  evaluation.py tapered positional evaluation
  hashing.py     deterministic Zobrist keys
  engine.py      advanced native search
  legacy.py      frozen regression baseline
  cli.py         terminal game
  uci.py         chess GUI protocol
  perft.py       move-generator validation
  backtest.py    color-balanced engine matches
backtests/       machine-readable match reports
docs/            architecture and strength methodology
tests/           standard-library test suite
```

## Fair play

This is an engine-development project. Do not use it for unauthorized assistance
in online games.

## License

MIT

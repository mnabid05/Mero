# Mero Chess Engine

A self-contained original chess engine written in Python, C, and C++.

**No Stockfish. No engine wrapper. No chess library. No runtime dependency.**

The project implements its own board representation, legal move generator,
evaluation, search, time management, UCI protocol, terminal game, and strength
regression harness. The strongest UCI engine runs board logic and search in
C++20, combines synchronized piece/occupancy bitboards with a reversible square
array, shares the portable C11 evaluation kernel, and keeps Python as a readable
reference implementation and testing layer.

## Native acceleration

Build the C11 evaluator and C++20 native engine:

```bash
python3 scripts/build_native.py
```

The build produces:

```text
build/native/mwahaha-engine
build/native/libmwahaha_eval.so    # .dylib on macOS
```

Use `build/native/mwahaha-engine` as the UCI executable in a chess GUI. The
Python engine detects the native evaluator library automatically. Without it,
the dependency-free Python evaluator is used; set `MWAHAHA_PURE_PYTHON=1` to
force that reference path.

Mero 5.0 retains selective tactical extensions while focusing quiescence on
captures, promotions, and required check evasions. A fresh one-million-node
probe measured 1.757 million nodes/second, 7.54% above the frozen Mero 4.0
baseline. A 20-game paired regression scored 4 wins, 15 draws, and 1 loss
(57.5%, approximately +53 head-to-head Elo). This is encouraging but does not
establish a 100-point rating gain. See [`docs/STRENGTH.md`](docs/STRENGTH.md)
for methodology and limitations.

## Search

- Iterative deepening with hard move-time control
- Principal variation search
- Alpha-beta pruning with aspiration windows
- Zobrist-keyed transposition table
- Incremental Zobrist updates with verified make/unmake state
- Synchronized piece and occupancy bitboards
- Four-byte moves and stack-backed move lists in recursive search
- Precomputed sliding rays with nearest-blocker bit scans
- Parallel principal-root search with configurable UCI threads
- Three-entry transposition clusters with cached static evaluation
- Quiescence search for tactical stability
- Frontier quiet-check search with pseudo-move filtering
- Null-move pruning
- Late-move reductions
- Check, recapture, and advanced-pawn extensions
- Killer-move and history heuristics
- Continuation history and threat-aware quiet ordering
- MVV-LVA capture ordering
- Static exchange evaluation for capture ordering
- Futility and delta pruning
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

### Web app

Build the native engine and launch the playable browser interface:

```bash
python3 scripts/build_native.py
python3 -m webapp.server
```

Open `http://127.0.0.1:8765` to play as either color. The responsive interface
supports click and drag moves, legal-move hints, promotions, move history,
captured pieces, board flipping, themes, clocks, and local game restoration.
See the [web app guide](docs/WEB_APP.md) for the API and architecture.

### Terminal

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
build/native/mwahaha-engine
```

Chess GUIs can configure `Threads` from 1–64 and `Hash` from 1–2048 MiB. Four
threads are the tested strength configuration for version 2.3.

The reference Python UCI remains available as `python3 -m chess_ai.uci` or
`mwahaha-uci`.

```bash
python3 -m pip install .
mwahaha-chess
mwahaha-uci
```

## Validation

Build the native engine and run the 68-test suite:

```bash
python3 scripts/build_native.py
python3 -m unittest discover -v
```

Run a color-balanced native A/B match with:

```bash
python3 -m chess_ai.match \
  --candidate build/native/mwahaha-engine \
  --baseline /path/to/frozen-mwahaha-engine \
  --games 40 --move-time 80 --json-out match.json
```

Validate the legal move generator:

```bash
python3 -m chess_ai.perft --depth 4
build/native/mwahaha-engine --perft 5
```

The standard starting position matches the canonical counts:

| Depth | Positions |
| ---: | ---: |
| 1 | 20 |
| 2 | 400 |
| 3 | 8,902 |
| 4 | 197,281 |
| 5 | 4,865,609 |

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
| Native 2.3 vs Stockfish 18 calibration | 15 | 11 | 14 | 51.25% |
| Architecture candidate vs promotion-search baseline | 7 | 12 | 1 | 65% |
| Native engine vs legacy depth 3 | 4 | 0 | 0 | 100% |
| Native engine vs legacy depth 2 | 7 | 1 | 0 | 93.75% |
| Hybrid tactical search vs previous hybrid | 22 | 3 | 15 | 58.75% |
| C++ native engine vs Python+C hybrid | 40 | 0 | 0 | 100% |

Both matches alternate colors within paired openings. Every decisive game ended
in checkmate. See [strength methodology](docs/STRENGTH.md) and the
[machine-readable reports](backtests/).

The four-thread version 2.3 calibration produced 15 wins, 11 draws, and 14
losses in 40 games against Stockfish 18 settings from 1750–2500. The fitted
estimate is **2139 Elo (95% interval 2003–2275)** on the tested Apple Silicon
hardware at 30 ms per move, compared with 2033 for version 2.1 and 1247 for the
Python+C engine under related methodology. The result does not establish 2300
strength and is not a chess.com rating.

Run the external-opponent methodology with:

```bash
python3 -m chess_ai.gauntlet \
  --candidate build/native/mwahaha-engine \
  --candidate-threads 4 \
  --opponent /path/to/an/external/uci-engine \
  --opponent-elo 1750 \
  --opponent-elo 2000 \
  --games-per-level 20 \
  --move-time 30 \
  --json-out gauntlet.json
```

External engines are test opponents only and are not included in or required by
Mero.

## Project layout

```text
chess_ai/
  board.py       board state, FEN, move generation, and game rules
  model.py       chess constants, coordinates, pieces, and moves
  evaluation.py tapered positional evaluation
  native.py      optional C evaluator bridge
  see.py         static exchange evaluation
  hashing.py     deterministic Zobrist keys
  engine.py      advanced native search
  legacy.py      frozen regression baseline
  cli.py         terminal game
  uci.py         chess GUI protocol
  perft.py       move-generator validation
  backtest.py    color-balanced engine matches
  gauntlet.py    external UCI matches and Elo intervals
  match.py       paired candidate-versus-baseline UCI matches
native/
  evaluation.c   portable C11 evaluation kernel
  engine.cpp     standalone C++20 board, search, and UCI engine
webapp/
  server.py      threaded HTTP server and native engine lifecycle
  game_manager.py server-authoritative game orchestration
  static/        responsive HTML, CSS, and JavaScript interface
scripts/         native build tooling
backtests/       machine-readable match reports
docs/            architecture and strength methodology
tests/           standard-library test suite
```

## Fair play

This is an engine-development project. Do not use it for unauthorized assistance
in online games.

## License

MIT

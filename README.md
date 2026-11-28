# Mero Chess Engine

A self-contained original chess engine written in Python, C, and C++.

Mero plays using its own search and embedded weights. No Stockfish, PyTorch,
or external chess library is required at runtime.

Mero 8 is the default native engine. Its C++20 search uses an incremental
neural evaluator trained on Mero 7 self-play: 236,778 completed games produced
20,005,910 quiet positions. The network scores the board directly. Its evaluation
doesn't add hand-written material values or a correction from the old evaluator.

**Mero 8 beat Mero 7 on two separate opening books.** Both color-reversed
Fastchess tests crossed the predeclared SPRT boundary at 8 seconds + 0.08
seconds per move. The first scored 349 wins, 92 draws and 251 losses
(+50 relative Elo); the confirmation scored 257 wins, 57 draws and 152 losses
(+80). Neither had a forfeit. These are match-specific gains, not ratings on
a human ladder. See [test conditions and rating calibration](docs/STRENGTH.md)
and the [release evidence](backtests/mero-8-release.json).

**Rating estimate: 2477** against Stockfish 18's 2300 setting on an Apple M4
(44 wins, 6 draws, 14 losses; 100 ms/move, four threads to one). The
pair-effective 95% range is **2344–2610**. This is not an estimate against
unrestricted Stockfish or a FIDE/chess.com rating.

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

Use `build/native/mwahaha-engine` as the UCI executable in a chess GUI or in
the web app below. The build verifies and embeds the bundled Mero 8 weights.
The UCI ID remains `Mero SCReLU 384 experimental` to preserve the exact
tournament executable. The separate Python engine and C shared library use
the older reference evaluation. To build a native control with Mero 7's
evaluation, use `--release-control --output-dir build/control`.

The earlier Mero 6.0 release added coordinated king-attack evaluation, passed-pawn king support,
legal-attacker exchange pruning, full-key evaluation caching, and faster
unpinned move generation. Search now handles check evasions, bounded tactical
extensions, repetition at the frontier, and rule-fifty cache separation more
carefully. A 64-game release-candidate match against Mero 5.0 scored 25 wins,
22 draws, and 17 losses (56.25%, approximately +44 head-to-head Elo); its paired
interval includes zero gain. See [`docs/STRENGTH.md`](docs/STRENGTH.md) for all
calibration results, exact configurations, and uncertainty.

The Mero 6.0 probe against Stockfish 18's 2300 setting scored 32 wins,
3 draws and 29 losses: **2316 setting-relative Elo**, with a model interval of
2231–2402 and a broader paired interval of 2198–2435. The point estimate crosses
2300, but the experiment does not establish a 2300 minimum or a human rating.

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
- Legal-capture SEE pruning with checking-capture exemptions
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

The native Mero 8 network uses 384 hidden units per perspective, squared
clipped ReLU, and eight output heads selected by piece count. Accumulators
are updated on make/unmake. Scalar and Apple Silicon kernels matched the
integer reference on all eight heads. The learned median cost of removing
a queen was 982.5 cp on the original test and 994 cp on an independent panel.

The earlier handcrafted/reference evaluator includes:

- Tapered middlegame/endgame scoring
- Phase-specific material values
- Algorithmic piece-square placement
- Doubled, isolated, and passed pawns
- Bishop pair
- Open and semi-open rook files
- King shelter
- Mobility
- Coordinated attacks around the enemy king (native search)
- Passed-pawn blockers and both kings' proximity (native search)

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

Build the native engine and run the test suite (the two optional Torch tests
also run if PyTorch is installed):

```bash
python3 scripts/build_native.py
python3 -m unittest discover -v
```

Linux CI also builds with AddressSanitizer and UndefinedBehaviorSanitizer.
Replay the published game reports with:

```bash
python3 -m scripts.verify_match backtests/mero-7-stockfish18-2300.json
python3 -m scripts.verify_match backtests/mero-8-stockfish18-2300.json
python3 -m scripts.verify_match backtests/mero-7-neural-ablation.json
```

Reports include complete moves, final positions, paired uncertainty, executable
SHA-256 hashes, and host details. See the [validation guide](docs/VALIDATION.md).

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

The historical four-thread version 2.3 calibration produced 15 wins, 11 draws, and 14
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

External engines are optional test opponents and offline label sources. They
are not bundled with Mero or invoked during normal play.

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

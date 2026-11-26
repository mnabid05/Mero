# Mero Chess Engine

Development gates, the latest validated revision, and the SPRT ledger are in
[PROGRESS.md](PROGRESS.md). For local setup and reproducing the perft, search
bench and match gates, see [engine testing](docs/ENGINE_TESTING.md).

A self-contained original chess engine written in Python, C, and C++.

Mero plays using its own search and embedded weights. No Stockfish, PyTorch,
or external chess library is required at runtime.

Mero 7's evaluator was trained in PyTorch on Stockfish 18 search scores from
archived Mero games and random legal continuations. Of 116,633 labeled positions,
96,784 trained the release network and 19,844 formed an opening-held-out
validation set after overlap filtering. The selected 64-unit network reduced
mean absolute teacher-score error from 388 to 268 centipawns on that set;
the release uses a half-strength correction to the native evaluation.

**Estimated strength: 2377 Elo in the release test.** Mero scored 37 wins,
4 draws and 23 losses against Stockfish 18 set to 2300 across 64 games at
100 ms per move (four threads to one). The paired 95% approximation spans
2256–2498. This is neither a human rating nor evidence of frontier strength.
See the [match report](backtests/mero-7-stockfish18-2300.json),
[training recipe](docs/NEURAL.md), and [training audit](backtests/mero-7-training.json).

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

The preceding Mero 6.0 release added coordinated king-attack evaluation, passed-pawn king support,
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

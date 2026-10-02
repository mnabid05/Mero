# Engine Architecture

## Hybrid execution

Mero uses three implementation languages:

- C++20 owns the strongest engine's board state, legal move generation,
  alpha-beta search, transposition table, time control, perft, and UCI.
- Portable C11 owns the shared static-evaluation hot path.
- Python owns the terminal UI, readable reference engine, gauntlet, and
  differential test orchestration.

The C++ engine links the C evaluator directly. The Python engine loads the same
kernel through `ctypes`; if it is missing or disabled, the pure-Python evaluator
preserves a fully functional reference implementation. No layer has a runtime
chess-engine dependency.

Mero 6 adds native bitboard terms for coordinated king pressure and passed-pawn
king proximity/blockers on top of the shared C evaluator. The Python reference
and C evaluation library retain the original evaluation; the native executable
is the release-strength engine. A per-worker 16,384-entry full-key evaluation
cache avoids repeating leaf evaluation and is reset on `ucinewgame`. This uses
roughly 256 KiB per worker beyond the configured transposition-table budget.

## Position layer

The Python reference stores 64 squares. The C++ engine uses a synchronized
hybrid representation: a 64-square array, 12 piece bitboards, two color
occupancy masks, and one combined occupancy mask. Leaper and sliding attacks,
king lookup, pawn threats, move generation, and search material queries use the
bitboards. The array remains available to the portable C evaluator and FEN
interface.

The native engine keeps a compact undo record for every searched move. Search,
quiescence, legal filtering, and perft can therefore make and unmake moves on
one board instead of copying a full position for every child. The board also
updates its Zobrist key incrementally across normal moves, captures, castling,
en passant, promotions, and null moves. A recursive verifier rebuilds every
bitboard from the square array after make/unmake sequences and covers castling,
en passant, captures, and all promotion types.

Mero 3.0 stores each move in four bytes and uses fixed-capacity stack lists for
pseudo-legal generation, legality filtering, move scoring, searched-move
history, and root ordering. The maximum capacity is above the largest possible
legal chess move count, removing allocator traffic from the recursive search
path without truncating move lists. Sliding attacks use precomputed directional
rays and bit scans to find the nearest blocker instead of walking squares.

The implementation covers normal moves, castling path safety, en passant capture,
promotion, attack detection, FEN, and terminal states.

For non-check positions, moves by non-king pieces that cannot expose a ray to
their king skip make/unmake legality filtering. King moves, possible pins, and
en passant retain full validation. FEN import validates ranks, pieces, kings,
move counters, castling syntax, and en-passant state before accepting a position.
UCI replay is transactional: an invalid move leaves the previous position intact.

Stalemate detection first looks for a provably legal unpinned pawn push or piece
move directly in bitboards. Only ambiguous positions require full move generation.
Across five one-million-node probes, this raised median throughput from 1.03M
to 1.28M NPS at the same completed depth (10), about 25% over the preceding 6.0
candidate. This comparison uses the same node-counter definition in both builds;
see `backtests/mero-6-fast-legality-performance.json`.

Repetition hashes include en passant only when a legal en-passant capture exists.
Search-table keys additionally include the reversible-move counter; identical
piece placements near the fifty-move boundary cannot share incompatible bounds.

## Evaluation

`Evaluator` produces separate middlegame and endgame scores and blends them using
the material phase remaining on the board.

The C11 evaluation pass builds pawn, rook-file, and king-location summaries
while it scans the board. Passed pawns then use bit masks, mobility is computed
for both colors in one pass, and middlegame/endgame square bonuses are calculated
together. This preserves the evaluation score while reducing repeated scans and
floating-point work at search leaves.

The score combines:

- phase-specific material;
- piece placement and centralization;
- pawn advancement, isolation, doubling, and passed-pawn status;
- bishop pair;
- rook files;
- king pawn shelter;
- legal mobility.

Positive scores favor White. Search converts that score to the side-to-move
perspective.

## Search

Both engines use iterative deepening. Every fully completed iteration becomes
the safe result if the clock expires during a deeper iteration.

The root and internal nodes use principal variation search. The first move gets a
full alpha-beta window; later moves receive a null window and are re-searched only
when they prove interesting.

The search includes:

- mate-distance pruning and ply-normalized transposition scores;
- game-history and search-path repetition detection;
- aspiration windows around the previous iteration's score;
- generation-aged transposition bounds keyed by deterministic Zobrist hashes;
- three-entry transposition clusters with depth-and-age replacement;
- cached static evaluations and quiescence bounds in the transposition table;
- verified null-move pruning outside check and pawn-only endings;
- dynamic late-move reductions and frontier pruning;
- check extensions near the horizon;
- quiescence search over captures, promotions, and check evasions;
- razoring, reverse futility pruning, and delta pruning;
- killer, countermove, quiet-history, and capture-history updates;
- continuation history and pawn-threat-aware quiet ordering;
- bitboard-backed static exchange evaluation for capture ordering;
- improving-position context for pruning and late-move reductions;
- PV, transposition, promotion, MVV-LVA, killer, history, and castling ordering.

Mero 6 bounds extension growth by root depth and permits at most one extension
per move. Quiet check evasions bypass futility pruning. Null pruning requires a
non-PV window and an adequate static score; artificial passes do not increment
the real-game draw clock. Same-ply verification and razoring suspend the current
history entry while re-searching it. Quiescence tracks repetition and terminal
draws, and excludes negative exchanges unless they check or promote. SEE filters
pinned defenders and illegal king captures. LMR logarithms are precomputed.

With `Threads` greater than one, the native engine searches the principal root
move first and distributes the remaining root candidates across isolated
workers. Each worker owns its history tables and a slice of the configured hash
budget, avoiding data races. A root depth is published only after every move at
that depth finishes, so timeouts cannot select from a partially searched move
set. Deterministic `go nodes` searches deliberately fall back to one worker.

The transposition table persists between moves and uses depth-preferred
replacement within each cluster. Killer, counter, capture, quiet, and
continuation histories persist within a game and reset on `ucinewgame`.

The C++20 implementation stores its transposition table in fixed-size,
power-of-two clusters and prefetches likely child clusters before recursive
search. In seven same-machine comparisons against version 2.3, Mero 3.0 reached
a median 1.94 million nodes/second with one thread, up 54%, and 2.87 million
aggregate nodes/second with four threads, up 37%. The Python version remains the
slower, easier-to-inspect reference.

## Design influences

Mero remains an original implementation and does not copy or embed another
engine. Its reversible position state, clustered transposition table, search
stack, and staged history ideas are informed by the public architecture of
[Stockfish](https://github.com/official-stockfish/Stockfish). Its cache-first
evaluation direction is also informed by
[Leela Chess Zero](https://github.com/LeelaChessZero/lc0), while deliberately
retaining alpha-beta search because this project does not ship a trained policy
and value network.

## Time management

The terminal interface uses a fixed move budget. The UCI adapter accepts
`movetime`, clocks, increments, and `movestogo`; it reserves configurable move
overhead and computes a conservative allocation.

Search checks the monotonic clock periodically and returns the best move from the
last completed iterative-deepening pass.

The UCI engine exposes `Threads`, `Hash`, and `Move Overhead` options. It also
accepts `go nodes` for deterministic development probes and reports `hashfull`
occupancy with each completed search.

Node limits count each frontier node once and stop at the requested count. Raw
NPS across the 5.0/6.0 boundary therefore cannot be interpreted as speedup: the
counter definition changed. Clocks remain active when combined with node or
depth limits. Mate scores use UCI `score mate` instead of oversized centipawns.

The UCI loop remains synchronous and does not implement asynchronous `stop` or
pondering. Search clients should use a bounded `go` command. The match client
also applies a response deadline and reaps stalled processes.

## Interfaces

- `python -m chess_ai` provides a human terminal game.
- `python -m chess_ai.uci` exposes UCI for chess GUIs.
- `build/native/mwahaha-engine` exposes the strongest native UCI engine.
- `python -m chess_ai.perft` validates move generation.
- `python -m chess_ai.backtest` runs paired strength regressions.
- `python -m chess_ai.gauntlet` runs calibrated external UCI matches.

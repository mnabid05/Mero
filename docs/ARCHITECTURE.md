# Engine Architecture

## Hybrid execution

Mwahaha uses three implementation languages:

- C++20 owns the strongest engine's board state, legal move generation,
  alpha-beta search, transposition table, time control, perft, and UCI.
- Portable C11 owns the shared static-evaluation hot path.
- Python owns the terminal UI, readable reference engine, gauntlet, and
  differential test orchestration.

The C++ engine links the C evaluator directly. The Python engine loads the same
kernel through `ctypes`; if it is missing or disabled, the pure-Python evaluator
preserves a fully functional reference implementation. No layer has a runtime
chess-engine dependency.

## Position layer

Both the Python reference and C++ engine store 64 squares, side to move,
castling rights, en passant target, and move clocks. They generate pseudo-legal
moves and filter them by applying the move to an isolated position and checking
king safety.

The implementation covers normal moves, castling path safety, en passant capture,
promotion, attack detection, FEN, and terminal states.

## Evaluation

`Evaluator` produces separate middlegame and endgame scores and blends them using
the material phase remaining on the board.

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

- aspiration windows around the previous iteration's score;
- transposition table bounds keyed by deterministic Zobrist hashes;
- null-move pruning outside check and pawn-only endings;
- late-move reductions for low-priority quiet moves;
- check extensions near the horizon;
- quiescence search over captures, promotions, and check evasions;
- static exchange evaluation, futility pruning, and delta pruning;
- killer and history updates after quiet cutoffs;
- PV, transposition, promotion, MVV-LVA, killer, history, and castling ordering.

The transposition table persists between moves and uses depth-preferred
replacement. Per-search killer and history tables reset for each move.

The C++20 implementation stores its transposition table in a fixed-size,
power-of-two array and reaches roughly 1.35 million nodes/second at the tested
starting position. The Python version remains the slower, easier-to-inspect
reference.

## Time management

The terminal interface uses a fixed move budget. The UCI adapter accepts
`movetime`, clocks, increments, and `movestogo`; it reserves configurable move
overhead and computes a conservative allocation.

Search checks the monotonic clock periodically and returns the best move from the
last completed iterative-deepening pass.

## Interfaces

- `python -m chess_ai` provides a human terminal game.
- `python -m chess_ai.uci` exposes UCI for chess GUIs.
- `build/native/mwahaha-engine` exposes the strongest native UCI engine.
- `python -m chess_ai.perft` validates move generation.
- `python -m chess_ai.backtest` runs paired strength regressions.
- `python -m chess_ai.gauntlet` runs calibrated external UCI matches.

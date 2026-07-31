# Engine Architecture

## Hybrid execution

Mwahaha uses two implementation languages:

- Python owns board state, legal move generation, search control, UCI, CLI, and
  test orchestration.
- Portable C11 owns the static-evaluation hot path and is loaded through
  `ctypes` when built.

The compiled layer has a narrow versioned API and no chess-engine dependency.
If it is missing or explicitly disabled, the pure-Python evaluator preserves a
fully functional engine.

## Position layer

`Board` stores 64 squares, side to move, castling rights, en passant target, and
move clocks. It generates pseudo-legal moves for every piece and filters them by
making the move on an isolated copy and checking king safety.

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

`ChessAI.choose_move` iterates from depth one to the configured maximum. Every
fully completed iteration becomes the safe result if the clock expires during a
deeper iteration.

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

## Time management

The terminal interface uses a fixed move budget. The UCI adapter accepts
`movetime`, clocks, increments, and `movestogo`; it reserves configurable move
overhead and computes a conservative allocation.

Search checks the monotonic clock periodically and returns the best move from the
last completed iterative-deepening pass.

## Interfaces

- `python -m chess_ai` provides a human terminal game.
- `python -m chess_ai.uci` exposes UCI for chess GUIs.
- `python -m chess_ai.perft` validates move generation.
- `python -m chess_ai.backtest` runs paired strength regressions.
- `python -m chess_ai.gauntlet` runs calibrated external UCI matches.

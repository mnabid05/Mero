# Mero engine development log

Current phase: 1 correctness and throughput gates passed; candidate undergoing its separate promotion SPRT. Apply the guide to the existing Mero engine without resetting the trained evaluator or the project history.

Latest passing perft / search-bench code commit: `d0a8ca7e573b34ec0f897efe51ee07d4c1635c90`. See [reproduction instructions](docs/ENGINE_TESTING.md).

Last validated release: `d74a206778f62f170844f43b7a18dfa7a3dc31a9`.
Last measured setting-relative Elo: **2377** (paired range **2256–2498**), 64 games at 100 ms/move, four threads vs Stockfish 18 at 2300 on one. Not a human rating or a 3000 claim.

## SPRT ledger

| Candidate vs baseline | Conditions | Result |
| --- | --- | --- |
| `d0a8ca7` vs `d74a206` | Fastchess `07fc150`, normalized [0,10], α=β=.05, 8+0.08, 1 thread/16 MiB each; 8 concurrent, random 8-ply PGN prefixes, seed 1701, paired colors, up to 2,000 pairs | Started; no decision at launch. See local `build/sprt-phase1-d0a8ca7/match.log`. |

Earlier 64-game Mero calibration and ablation runs were fixed-length, not SPRTs.

## Phase 1 evidence

* All 761,234,712 leaves matched across the six canonical positions, on both the frozen baseline and the release candidate. See [before](backtests/phase1-perft-before.json) and [after](backtests/phase1-perft-after.json) for per-position results and executable hashes.
* Apple M4, one thread, Apple Clang, `-O3 -march=native -DNDEBUG`: 21.75M → 114.60M weighted perft nodes/s on the final build. All six candidate positions exceeded 50M/s individually. The comparison includes bulk counting the **legal** final ply; it is not a search or Elo multiplier.
* Forty fixed positions at depth 12: **117,479,365 search nodes, 1,212,332 search nodes/s**, legal bestmove for every position; 93 unit tests passed including all 107,648 blocker subsets checked against the old independent ray scan.
* Two-game Fastchess infrastructure smoke at 8+0.08: two checkmates, no forfeits. Baseline emitted a PV/bestmove disagreement once; this is a protocol diagnostic for the next phase, not an illegal move. No strength inference from this match.
* Fastchess installed in `build/tools`, opening book verified, Bullet source pinned. New NNUE datagen/training is **not** part of these results. No new absolute Elo estimate.

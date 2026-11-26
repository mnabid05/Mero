# Mero engine development log

Current phase: 1 — verify the existing board, implement and cross-check magic sliders, measure six-position perft. The guide is being applied to Mero; this is not a new engine or a reset of its history.

Last validated release: `d74a206778f62f170844f43b7a18dfa7a3dc31a9`.
Last measured setting-relative Elo: **2377** (paired range **2256–2498**), 64 games at 100 ms/move, four threads vs Stockfish 18 at 2300 on one. Not a human rating or a 3000 claim.

## SPRT ledger

No SPRT decisions yet. The previous 64-game ablation was a fixed-length match, not an SPRT. Record the two commit IDs, book, clock, threads, game count, W/D/L, LLR and decision before promoting a playing-strength change.

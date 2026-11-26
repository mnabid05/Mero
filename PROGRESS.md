# Mero: Torch-style evaluator experiment

Branch `feat/torch-screlu-512` starts from the released Mero 7 (`d74a206`).
It does not include the unpromoted magic-slider change. Its separate [Phase 1
ledger](https://github.com/mnabid05/Mero/blob/feat/phase-1-perft/PROGRESS.md)
records the 380-game clock-invalidated SPRT; that test supplies no Elo evidence
for this network. Last measured **release** estimate: **2377 setting-relative
Elo** (paired 2256–2498). Target 3000 is unverified.

Latest bench/parity-passing engine commit: `22d8a2116894973399889bc44bd0c4698d5e238d`.
The candidate trained on 96,784 positions and held out 19,844. The quantized
epoch-two model scored 229.35 cp native MAE vs 298.99 for the Mero 7
evaluation on identical rows. Exact scalar and NEON parity on 555 FENs and
1,001 scores across 17 reversible traces. Native depth-12 bench: 40 positions,
78,269,553 nodes, 999,150 search nodes/s on this M4. All 103 local tests passed.
The frozen baseline and candidate executable hashes start with `c8aa94fc`
and `050413c4`, respectively.

| Candidate | SPRT vs main | Latest passing strength commit |
| --- | --- | --- |
| `22d8a21` vs `d74a206`, attempt 1 | **Invalid.** 8+0.08, 4 lanes, 1 thread/16 MiB per engine, seed 1701, paired eight-ply PGN prefixes, normalized [0,10], α=β=.05. Interrupted at 11 finished games (1W/1D/9L): four simultaneous time forfeits during a 30-second clamshell sleep, no completed LLR decision. [Fault record](backtests/screlu512-sprt-01-invalid.json). | None for this candidate |

**Do not promote the standalone model.** Despite its lower teacher error, it
lost all 64 games in a separate 20,000-nodes/move diagnostic (32 color pairs,
seed 1701). All ended in checkmate, none on time. On 1,477 sampled positions,
averaging its scores for opposite sides to move gave a median +141.5 cp for
the mover; the Mero 7 score was antisymmetric (median 0). This is a plausible
search-calibration problem, not proof of a single cause. Test a bounded,
antisymmetric correction to the proven evaluator on a separate branch.

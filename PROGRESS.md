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
The frozen baseline and candidate executable hashes start with `c8aa94fe`
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

## Bounded correction (Phase 4 follow-up)

On `feat/torch-bounded-residual`, keep Mero 7's evaluation and add an
antisymmetric correction capped at ±64 cp. The first fit anchored nonquiet
positions to zero; [validation selected the unchanged starting model](backtests/bounded512-anchor-null.json).
Training on quiet positions alone selected epoch 1, averaging a 22.2 cp
absolute correction. Native held-out error: 289.21 vs 298.99 cp on 19,844
positions. Scalar and NEON exactly matched the exported integer reference
on 555 FENs and 1,001 path scores; all eight heads were covered. Native bench:
40 positions, depth 12, 105,369,914 nodes, 711,963 nodes/s on this M4.

[Equal-node diagnostic](backtests/bounded512-fixednodes.json): 21 wins, 18
draws, 25 losses vs the frozen main release (32 color pairs, 20,000 nodes/move,
new seed 1919, no clock or engine faults). **Not an improvement claim.** The
SPRT power preflight required sustained, non-discharging AC; no valid timed
result for this model. Latest passing strength commit remains the Mero 7
release; neither experimental checkpoint is promoted.

## Phase 5: self-play data pilot (no gameplay change)

`feat/bullet-selfplay` adds an offline command without changing UCI search.
256 complete classical-bootstrap games at 5,000 nodes/move yielded 19,521
quiet labeled positions: 125 White wins, 39 draws and 92 Black wins. The
independent board replayed every game and upstream bulletformat 1.8.0
reproduced every byte. The 206-game training / 50-game validation split
contains 16,143 / 3,374 rows after removing cross-split feature duplicates.
This is a pipeline pilot, **not** the proposed 50M positions or evidence of
rating gain. See [commands and fingerprints](docs/SELFPLAY.md).

## Phase 5: first real Bullet/Metal training run

`feat/bullet-metal-pilot`: 40 superbatches on the Apple M4 GPU; validated
integer checkpoint 35 selected. Confirmed Bullet float graph conversion across
all 8 heads (<0.001 cp maximum error) and exact C++ integer inference parity.
The network lost 0W/0D/64L at equal nodes (32 pairs, seed 33097, 20,000
nodes/move, no clock/engine faults). **Do not release it.** No accepted
promotion SPRT, no new absolute Elo estimate. [Reproduction and data](docs/BULLET.md).

Follow-up: with the bounded correction disabled, four opening pairs split
4W/0D/4L and each pair had the same actual outcome with colors reversed.
With it enabled, a fresh independent 256-pair fixed-node match returned
**175W/126D/211L**, 46.48% (Fastchess relative Elo **−24.47 ±26.07**).
This estimate applies at 20,000 nodes/move, not to a human or timed pool.
No forfeits. The bounded model also does not justify replacing Mero 7;
the combined research branch defaults to the release evaluator.
[Disabled control](backtests/bounded512-zero-control.json);
[512 games](backtests/bounded512-confirmation.json).
The Mac's formal SPRT power preflight still refused to run on discharging AC.

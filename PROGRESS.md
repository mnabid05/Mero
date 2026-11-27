# Mero: Torch-style evaluator experiment

## Scaled standalone campaign (in progress, not promoted)

Fresh Mero 7 self-play: 5,000 nodes/move, eight random plies, 20M quiet-row
target. The ten-worker generator produced identical records and move histories
to the previous generator on all 48 sampled games. Its first sealed
256-game production shard has 21,541 records: independent legal replay and
upstream Rust format verification both passed. Strict 256/384-wide inference
includes all endgames; no hardcoded material is mixed into these networks.
No scaled training, queen-gate pass, SPRT pass or new rating is claimed here.
See [protocol and commands](docs/SCALE-CAMPAIGN.md).

**20M source target reached:** 20,005,910 quiet rows, 925 verified shards,
236,778 completed games, and 22 capped games excluded (640,189,120 bytes of
Bullet records). A missing shard was regenerated against its surviving
original hashes, without replacing its seal or changing the dataset. On the
last shard, all 21,760 positions passed legal replay and byte comparison
against upstream Rust; the release reproduced all 973 searches and 691
quiet scores in the last eight games. [Frozen corpus report](backtests/scale-20m-corpus.json).
This is a dataset milestone, not a strength result.

The final split has **19,626,685 training rows and 16,318 validation rows**;
26 whole games started in reserved match positions and were excluded. In
the production training set, 208,157 rows have a one-queen difference with
identical counts of every other piece type, versus just 180 in the pilot's
16,143 training rows. These are observed positions, not independent games or
a learned queen value. The teacher also changed from HCE to Mero 7.
[Split hashes and bucket counts](backtests/scale-20m-training-split.json).

Checkpoint: 63 sealed shards, 1,365,596 quiet records, 16,125 completed
games and three capped games excluded. Mero 7 UCI independently reproduced
all 762 searched moves and all 488 saved cp scores in an eight-game sample.
The mover scored 6.2% in positions below −300 cp and 93.3% at +300 cp or
higher, counting draws as half. This is a label audit, not an engine rating.
All six isolated search hypotheses have frozen binaries, NPS samples and
reserved books; none has a passing SPRT. Release remains `d74a206`.

Power handoff: 330 shards sealed (7,117,907 quiet positions from 84,480
games attempted). The runner rechecks the battery controller when the OS
labels a draining battery as AC, and can idle until a usable supply returns.
This checkpoint is below the training floor; no new weights or Elo result.

On restoring AC power the same runner sealed shard 330. The frozen release
reproduced all 1,040 searched moves and all 698 saved scores in an eight-game
sample of that shard. On the exact held-out qualification panel (248 queen
removals), Mero 7 measured 924 cp and the rejected 512-wide pilot measured
131 cp. These are controls, not results for a new network. [Audit and paired
NPS measurements](backtests/scale-resume-checks.json).

Fresh-opening isolation: seven data games among the next audited 375-shard
snapshot (8,090,922 records) transposed into reserved SPRT opening positions.
The split now excludes those entire games and protects the root features in
both orientations. An independent scan of the 7,942,771 training records in
the split-only rehearsal found zero reserved root or validation layouts. No
model was trained in that rehearsal. [Evidence](backtests/scale-opening-isolation.json).

First independently hash-verified training-eligible snapshot: 10,484,483
usable training records and 16,285 held-out records from 10,686,063 sealed
positions. [Split manifest](backtests/scale-first-eligible-split.json). The
scheduled first fit still uses the full 20M run. Split and network export
publish on completion only; an interrupted shuffle cannot appear as a
finished training directory.

Search diagnostics: six frozen binaries completed 96 fixed-node games on 48
additional, disjoint eight-ply openings. Independent replay validated 11,715
legal plies, all 87 checkmates and all nine draws. Fastchess logged PV display
warnings but no forfeits. These were single-lane, **not** timed strength tests;
no search feature is promoted. [Per-candidate records](backtests/scale-search-canaries.json).

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

## UCI control and diagnostic integrity (separate feature)

`feat/uci-search-control` adds asynchronous `stop`, responsive `isready`, and
honors `go infinite` until cancellation. New live tests cover one and three
workers, immediate stop, readiness, repeated stop, a terminal board, explicit
quit and reuse for a finite search. The reported PV starts with the chosen
root move and terminates at a repetition. With Mero 7 evaluation on both
sides, 32 paired fixed-node openings split **21W/22D/21L**; no clocks or
engines failed. Fastchess emitted 64 PV warnings from the frozen main engine
and **none** from the patched one. [Fixed-node report](backtests/uci-control-fixednodes.json).
This fixes protocol behavior; it is not a strength promotion.

Latest local bench/test-passing UCI feature code: `a9b7298`; 110 tests and
[Linux CI](https://github.com/mnabid05/Mero/actions/runs/45890155028) passed.
40 positions, depth 12: 117,479,365 nodes at 1,057,385 nodes/s on the M4
using the default Mero 7 evaluator. The opt-in standalone Bullet pilot's
separate benchmark was interrupted after 19m23s CPU with no final node count
(it had already lost all 64 match games); **it did not pass the bench gate**.
No strength promotion; GitHub main remains `d74a206`.

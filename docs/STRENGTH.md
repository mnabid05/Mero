# Strength Methodology

## What is measured

This repository measures whether the current original engine improves against its
own frozen predecessor. `LegacyAI` contains the earlier material-and-activity
evaluation with fixed-depth alpha-beta search.

Every match:

- uses deterministic opening sequences;
- plays each opening twice with colors reversed;
- recognizes checkmate, stalemate, draw rules, and threefold repetition;
- limits runaway games by maximum plies;
- records final FEN positions in JSON.

### Mero 4.0 tactical-search update

The Mero 4.0 branch adds quiet-check quiescence at the search frontier,
selective extensions for checks, recaptures, and advanced pawns, safer null
move pruning in sparse endings, and continuation-history-aware reductions.
The implementation also adds a pseudo-move prefilter so quiet-check search does
not run a full legality probe for every quiet move. The existing calibrated
evaluation was retained after profiling rather than accepting unmeasured terms
on the hot path.

On the same machine, with one thread and a one-million-node limit, the current
branch reached a median **1.69M nodes/second** (depth 10) across five fresh
processes. The frozen Mero 3.0 executable reached **1.91M nodes/second** (depth
11) under the same probe, so this branch currently trades about 11.8% of raw
throughput for deeper tactical continuation. The full regression suite passes
56 tests, including perft, incremental-key, bitboard, SEE, UCI, and endgame
fixtures.

An eight-game equal-node smoke match (50,000 nodes per move, colors balanced)
ended with all games reaching the move cap and a 50% score for each version.
That is a regression check, not a statistically meaningful rating result. The
latest external calibration remains the Mero 2.3 estimate of **2139 Elo with a
95% interval of 2003–2275** below; this update does not substantiate a 2300
rating claim until a new Stockfish gauntlet is run.

## Recorded matches

### Mero 3.0 performance regression

Version 3.0 was compared with the exact merged 2.3 release on the same Apple
Silicon machine and compiler settings. Each result is the median of seven fresh
engine processes:

| Configuration | Version 2.3 | Mero 3.0 | Change |
| --- | ---: | ---: | ---: |
| 1 thread, 1,000,000-node search | 1.26M NPS | 1.94M NPS | +53.97% |
| 4 threads, 500 ms search | 2.09M NPS | 2.87M NPS | +37.41% |

The single-thread comparison uses the same one-million-node limit and reaches
depth 11 in both versions, making elapsed search throughput directly comparable.
Timed parallel search naturally varies with scheduling, so the recorded value
uses the median rather than the fastest run. See
`backtests/native-3.0-vs-2.3-performance.json`.

This is a speed result, not a new Elo calibration. Until a new external gauntlet
is completed, the latest defensible rating estimate remains the version 2.3
result below.

### Native 2.3 bitboard and parallel-search calibration

Version 2.3 completed 40 paired games against Stockfish 18 at 30 ms per move.
The candidate used four search threads and Stockfish used one, matching the
intended desktop configuration for this release. The result was 15 wins, 11
draws, and 14 losses:

| Opponent setting | Wins | Draws | Losses | Score |
| ---: | ---: | ---: | ---: | ---: |
| 1750 | 5 | 2 | 3 | 60.0% |
| 2000 | 6 | 0 | 4 | 60.0% |
| 2250 | 4 | 3 | 3 | 55.0% |
| 2500 | 0 | 6 | 4 | 30.0% |

The logistic fit estimates **2139 Elo with a 95% interval of 2003–2275** on
the tested Apple Silicon hardware. This is a 106-point increase over the prior
2033 point estimate, but the candidate also used four cores rather than one, so
it is a release-configuration comparison rather than an isolated algorithmic
Elo measurement. The result does **not** substantiate a 2300 rating claim.

All 40 games completed without a crash, illegal move, or engine forfeit. The
candidate scored 9/20 as White and 11.5/20 as Black. See
`backtests/native-2.3-stockfish-18-gauntlet-40.json`.

The bitboard build averaged roughly 1.30 million nodes/second with one thread
and 2.19 million aggregate nodes/second with four threads across three 500 ms
starting-position probes. Static-exchange ordering scored 5 wins, 10 draws,
and 5 losses in a 20-game equal-resource regression against the pre-SEE build,
so it was neutral in that small sample.

### Architecture candidate vs promotion-search baseline

The reversible-state and cache architecture build scored 7 wins, 12 draws, and
1 loss against commit `c017e04` across 20 paired games at 50 ms per move. Its
65% score is approximately +108 Elo head-to-head. The candidate scored 7/10 as
White and 6/10 as Black, with no illegal moves, crashes, or forfeits.

The same build averaged roughly 1.447 million nodes/second over three 500 ms
starting-position runs, versus 1.188 million for the frozen baseline. This
20-game result is a positive regression gate, not a statistically conclusive
rating claim. See `backtests/native-architecture-vs-2.1-20.json`.

### Native 2.1 vs native 2.0

The 14-contribution engine upgrade scored 18 wins, 27 draws, and 15 losses
against the exact 2.0 baseline across 60 games at 30 ms per move. Its 52.5%
score is approximately +17 Elo head-to-head. The direction is positive, though
this self-match alone is not statistically decisive.

### Native 2.1 Stockfish 18 gauntlet

The independent 100-game rerun produced 37 wins, 31 draws, and 32 losses:

| Opponent setting | Wins | Draws | Losses | Score |
| ---: | ---: | ---: | ---: | ---: |
| 1500 | 18 | 2 | 0 | 95.0% |
| 1750 | 8 | 11 | 1 | 67.5% |
| 2000 | 5 | 6 | 9 | 40.0% |
| 2250 | 5 | 5 | 10 | 37.5% |
| 2500 | 1 | 7 | 12 | 22.5% |

The logistic fit estimates **2033 Elo with a 95% interval of 1939–2127**, a
112-point increase over the 2.0 estimate under the identical methodology. No
game ended by engine crash, illegal move, or forfeit.

### C++ native engine vs Python+C hybrid

The C++20 engine won all 40 games against the preceding Python+C hybrid at
30 ms per move. The test used paired openings and reversed colors; all games
ended in checkmate, with no illegal moves, crashes, or forfeits. Because the
score was 100%, it establishes a decisive regression win but not a finite
head-to-head Elo difference.

### C++ native engine Stockfish 18 gauntlet

The native engine played 100 games across five higher Stockfish 18 `UCI_Elo`
settings under the same one-thread, paired-opening, 30 ms methodology.

| Opponent setting | Wins | Draws | Losses | Score |
| ---: | ---: | ---: | ---: | ---: |
| 1500 | 15 | 4 | 1 | 85.0% |
| 1750 | 6 | 7 | 7 | 47.5% |
| 2000 | 5 | 4 | 11 | 35.0% |
| 2250 | 3 | 7 | 10 | 32.5% |
| 2500 | 1 | 6 | 13 | 20.0% |

The aggregate result was 30 wins, 28 draws, and 42 losses. The logistic fit
estimates **1921 Elo with a 95% interval of 1827–2015**, a measured increase of
674 points over the preceding 1247 baseline under the same methodology.
There were no engine forfeits.

### Hybrid tactical search vs previous hybrid

The tactical-search build beat the immediately preceding C-accelerated version
22–3–15 across 40 games at 30 ms per move. Its 58.75% score corresponds to a
head-to-head difference of approximately +61 Elo. This isolates the benefit of
static exchange ordering, futility pruning, delta pruning, and selective check
extensions from the C evaluator speedup shared by both versions.

### Stockfish 18 limited-strength gauntlet

The engine played 100 games across five external Stockfish 18 `UCI_Elo`
settings, with 20 games per setting, paired openings, reversed colors, one
thread, and 30 ms per move.

| Opponent setting | Wins | Draws | Losses | Score |
| ---: | ---: | ---: | ---: | ---: |
| 1320 | 6 | 3 | 11 | 37.5% |
| 1450 | 3 | 3 | 14 | 22.5% |
| 1600 | 1 | 1 | 18 | 7.5% |
| 1750 | 0 | 5 | 15 | 12.5% |
| 1900 | 0 | 1 | 19 | 2.5% |

The aggregate result was 10 wins, 13 draws, and 77 losses. A logistic
maximum-likelihood fit estimates **1247 Elo with a 95% interval of 1148–1346**
for this hardware and time control. There were no illegal moves, crashes, or
forfeits.

This is the first calibrated baseline, not a chess.com rating. Limited-strength
engine labels, hardware, openings, and very fast time controls introduce
measurement differences from human online pools.

### Native engine vs legacy depth 3

| Setting | Value |
| --- | --- |
| Candidate | Mero native engine, depth 6 |
| Candidate time | 100 ms per move |
| Baseline | Legacy minimax, depth 3 |
| Games | 4 |
| Result | 4 wins, 0 draws, 0 losses |
| Score | 100% |

All four games ended in checkmate. The candidate won both paired openings as
White and Black.

### Native engine vs legacy depth 2

| Setting | Value |
| --- | --- |
| Candidate | Mero native engine, depth 6 |
| Candidate time | 100 ms per move |
| Baseline | Legacy minimax, depth 2 |
| Games | 8 |
| Result | 7 wins, 1 draw, 0 losses |
| Score | 93.75% |

Seven games ended in checkmate. One game ended by threefold repetition.

## What is not measured

These are regression matches, not an Elo certification. They show that the new
engine is decisively stronger than its predecessor under the recorded settings.
They do not establish 2800 strength or any chess.com rating.

A credible rating estimate requires:

- hundreds or thousands of games;
- multiple independent, calibrated opponents;
- fixed hardware and time controls;
- confidence intervals and draw-aware Elo calculation;
- defenses against opening bias.

The next strength milestone is incremental make/unmake with bitboards, stronger
static exchange evaluation, repetition history, and automated tuning. Future
changes should use multiple independent opponents and SPRT-style testing.
Stockfish and other engines remain outside the runtime and repository.

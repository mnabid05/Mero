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

## Recorded matches

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
| Candidate | Mwahaha native engine, depth 6 |
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
| Candidate | Mwahaha native engine, depth 6 |
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

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

The next strength milestone is to move board make/unmake and alpha-beta search
into compiled code, then use several independent opponents and SPRT-style
testing. Stockfish and other engines remain outside the runtime and repository.

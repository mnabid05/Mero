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

The next strength milestone should use a broader gauntlet and SPRT-style testing,
while keeping Stockfish or other engines outside the runtime and repository.

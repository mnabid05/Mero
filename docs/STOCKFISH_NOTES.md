# Stockfish-Inspired Search Notes

Mero remains an original engine and does not copy or link Stockfish code. This
document records the search ideas studied in Stockfish's official source and
the smaller adaptations that fit Mero's architecture.

## Candidate techniques

### Correction history

Static evaluation has repeatable blind spots. Stockfish keeps bounded history
tables that learn the difference between static and searched scores for related
positions, then uses that signal to correct later evaluations. Mero can start
with a compact pawn-structure correction table keyed by side to move. The table
must use gravity updates, remain bounded, and be cleared for a new game.

### ProbCut

At sufficiently deep non-PV nodes, a shallow tactical search can establish that
a position is very likely above beta. Mero can search ordered, SEE-safe captures
against a raised beta and use a reduced verification search before cutting off.
The guard must exclude checks, mate-score windows, and shallow nodes.

### Dynamic null-move reduction

Stockfish varies null-move reduction with depth and the static-evaluation margin
above beta, then verifies risky deep cutoffs. Mero already has zugzwang guards
and deep verification; adding a capped evaluation-margin term can save work in
positions where a null cutoff is especially likely.

### Selective move pruning

Stockfish combines move-count, history, futility, and SEE signals. Mero already
has the first three, but can avoid late, losing captures at shallow non-PV nodes
and reject negative-SEE captures deeper in quiescence. These rules must preserve
checks, promotions, recaptures, and the first ordered moves.

## Validation policy

Every search change must pass perft, special-move, incremental-key, mate, and UCI
tests. Node-limited probes measure search efficiency, not Elo. Strength claims
require deterministic paired games against a frozen binary, with colors reversed
for every opening. A small match is a regression signal, not a rating certificate.

## Experiment outcome

The first combined candidate implemented correction history, verified capture
ProbCut, dynamic null-move reduction, late SEE/history pruning, and additional
hand-tuned evaluation terms. It scored 6 wins, 23 draws, and 11 losses in a
40-game 20 ms match, so those changes were removed rather than shipped.

The retained change follows modern capture-focused quiescence design: quiet
checks are handled by the regular search instead of expanding every frontier
node. With the existing tactical extensions preserved, the isolated candidate
scored 4 wins, 15 draws, and 1 loss in a paired 80 ms regression. The lesson is
architectural rather than numerical: Stockfish's heuristics are interdependent
and tuned together, so transplanting individual formulas into a different
evaluation and search tree can reduce strength.

## Primary reference

- Stockfish official `src/search.cpp`:
  <https://github.com/official-stockfish/Stockfish/blob/master/src/search.cpp>

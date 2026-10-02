# Mero 6 development protocol

Baseline: `8b96747` (Mero 5.0), built with the same compiler and release flags
as each candidate. The baseline binary lives in ignored `build/baseline-5`.

The 2300 Elo target is an experiment, not an assumed result. Changes cover
search correctness, move generation, ordering, resource control, and reproducible
measurement. Each accepted implementation or regression fixture is recorded as
a separate reviewable commit. No empty commits or fabricated match results.

Validation gates:

1. Native build with warnings treated as errors.
2. Legal-move, hash, special-move, search, and protocol regressions.
3. Equal-resource, color-reversed matches against the frozen baseline.
4. External Stockfish 18 limited-strength probes, explicitly described as
   setting-relative calibration at the recorded time control.
5. Publish losses, draw caps, forfeits, and uncertainty alongside wins.

Stockfish remains an external test opponent; its source and networks are not
part of Mero. A short-time-control probe cannot certify a human 2300 rating.

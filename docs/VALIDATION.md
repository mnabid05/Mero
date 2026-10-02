# Reproducing Mero validation

## Correctness

```bash
python3 scripts/build_native.py
python3 -m unittest discover -v
build/native/mwahaha-engine --perft 5
build/native/mwahaha-engine --verify-keys 3
build/native/mwahaha-engine --verify-bitboards 3
```

The start-position perft result must be 4,865,609. Native white-box tests compile
the actual engine and cover Kiwipete, en-passant pins, special-move hashes,
draw/material handling, SEE legality, score symmetry, and transactional replay.
The Python reference supplies an independent move-generator comparison.

## Memory safety

```bash
python3 scripts/build_native.py --sanitize --output-dir build/sanitized
build/sanitized/mwahaha-engine --perft 4
build/sanitized/mwahaha-engine --verify-keys 3
```

GitHub Linux jobs cover these commands plus UCI search and special positions.
On the development Mac, the instrumented executable spun without output, both
inside and outside the sandbox; a bounded 20-second retry was stopped. Native
release tests passed locally and the Linux ASan/UBSan job passed. Mac sanitizer
runtime validation remains unresolved; do not describe it as a passing check.

## Equal-resource regression

Freeze the predecessor in a separate checkout and build it using the same
compiler. Keep both binaries unchanged for the duration of a match:

```bash
python3 -m chess_ai.match \
  --candidate build/native/mwahaha-engine \
  --baseline /path/to/frozen-mero-5 \
  --candidate-threads 1 --baseline-threads 1 \
  --games 64 --move-time 50 --max-plies 400 --json-out match.json
python3 -m scripts.verify_match match.json
```

Both engines receive full game histories, 64 MiB hash and a new-game reset.
Openings are paired by color. A timeout is a forfeit, and caps are recorded
explicitly. A decisive terminal position at the cap remains decisive. The
replay verifier checks move legality, final FEN, draw reason, score and totals.

Avoid concurrent benchmarks and heavy workloads. Development runs used an
interactive Mac and are not isolated laboratory measurements. In particular,
the 64-game Mero 5 comparison overlapped stalled sanitizer processes for part
of its run; both sides had the same requested resources, but scheduling noise
remains. Small positive scores are evidence for further testing, not proof.

## External setting calibration

Use the official Stockfish 18 release as an external opponent. Its executable
and network stay outside version control and are not dependencies of Mero.

```bash
python3 -m chess_ai.gauntlet \
  --candidate build/native/mwahaha-engine --candidate-threads 4 \
  --opponent /path/to/stockfish18 --opponent-threads 1 \
  --opponent-elo 2300 --games-per-level 64 \
  --move-time 100 --max-plies 400 --json-out calibration.json
python3 -m scripts.verify_match calibration.json
```

The runner verifies the advertised strength option and its allowed range.
Stockfish's 120s+1s calibration differs from this experiment. Do not transfer
the estimate to chess.com, FIDE, or another human rating pool. Compare both
the logistic interval and the broader pair-effective interval; neither models
all systematic error. Confirmation should use new openings, longer controls,
more games, and multiple independently calibrated opponents.

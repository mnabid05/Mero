# Mero's SCReLU candidate

This branch keeps Mero 7 as its default and offers experimental evaluators. It
does not replicate the [Torch engine](https://www.chess.com/news/view/torch-chess-engine)
or establish a 3000 Elo rating. The design follows the requested two-perspective
NNUE, implemented and trained here in PyTorch. Stockfish was an offline source
of scores for the existing corpus, never a runtime dependency.

## What changed

* 768 piece-square inputs (Mero square 0 = a8), 512 shared hidden lanes, two
  perspectives ordered as side-to-move and opponent. SCReLU squares the
  clipped activations; one of eight independent readouts is selected by
  `min(7, (piece_count - 2) / 4)` using integer division.
* In the first experiment the output was a **standalone**, side-to-move centipawn score. That engine
  used it at full weight by default except in positions with three or fewer
  pieces, which keep the established classical conversion evaluation. Search
  rules, draws and mates are still handled by search. The original Mero 7
  scored a hand-tuned prior plus a 64-wide half-strength learned correction.
* Initialization preserves that learned correction using complementary SCReLU
  lanes and adds a linear material-count basis inside the new network. AdamW
  fine-tunes the transformer and bucket heads. From epoch two, straight-through
  rounding uses the deployed parameter scales. The selected epoch minimizes
  **exported integer validation loss**. This is teacher distillation on the
  existing corpus, **not** a completed 50M-position Bullet self-play run.
* A checksummed little-endian weight file is validated and embedded at build
  time. Both weight scales are fixed: QA=255, QB=64. Input sums use checked
  int16 bounds; the squared readout uses int64, includes output bias scaled
  by QA, multiplies by 400 and divides by QA²×QB toward zero.
* Each board and each worker owns its accumulator. Piece placement/removal
  toggles dirty bits. Changes canceled before the next evaluation cost no
  vector additions. Evaluation materializes net removals before additions.
  Native row updates support AVX2, AVX-512BW, ARM NEON and a scalar fallback.

## Play and verify

```sh
python3 scripts/build_native.py --bounded512 --native-arch --output-dir build/bounded
build/bounded/mwahaha-engine bench
python3 -m scripts.check_screlu_fixtures build/bounded/mwahaha-engine
python3 scripts/build_native.py --bounded512 --scalar-only --output-dir build/scalar512
python3 -m scripts.check_screlu_fixtures build/scalar512/mwahaha-engine
```

Use the executable as a UCI engine. A normal build goes in `build/native/`,
which the web app finds automatically. To explicitly build the release evaluator use
`--release-control --output-dir build/control`. For a promotion match use the
frozen main binary (see the ledger). The opt-in `--bounded512` checkpoint is
`mero-bounded512.bin`: the two halves of each bucket head are exact negatives,
and the output bias is zero. Its correction is clamped to ±64 cp and added to
the unmodified Mero 7 evaluation. For this checkpoint `NeuralBlend=0` restores
the release's static scores. With the earlier standalone checkpoint it does not.

## Reproduce training

Create the 4,096-node teacher corpus as in [NEURAL.md](NEURAL.md). From the repo
root and a Python environment with the optional Torch and NumPy dependencies:

```sh
python -m training.train_screlu build/torch-expanded.db build/new-fit \
  --epochs 12 --qat-start 2 --threads 2 --seed 1701
python3 scripts/build_native.py --native-arch --screlu build/new-fit/weights.bin \
  --output-dir build/new-net
python -m training.audit_screlu build/new-fit/weights.bin build/new-net/mwahaha-engine
```

The [float checkpoint](../training/checkpoints/mero-screlu512.pt), [integer
weights](../training/checkpoints/mero-screlu512.bin), [training curve](../backtests/screlu512-training.json)
and [per-bucket native comparison](../backtests/screlu512-teacher.json) are
checked in. Train and validation opening families are disjoint; held-out rows
that duplicate the training feature layout under color reversal are excluded.
The validation set selects a checkpoint. Its error is neither an untouched
strength test nor a rating. See [PROGRESS.md](../PROGRESS.md) for game results.

To reproduce the bounded model, compile the quiet-position labeling control,
then fit from the standalone feature transformer (no paid compute is needed):

```sh
python3 scripts/build_native.py --native-arch --release-control --output-dir build/control
python -m training.train_residual build/torch-expanded.db build/control/mwahaha-engine \
  training/checkpoints/mero-screlu512.pt build/bounded-fit --epochs 10 --threads 2 --quiet-only
```

This run used 41,518 quiet training rows, selecting an epoch against 7,810 quiet
validation rows. [Training](../backtests/bounded512-training.json), [integer
checkpoint](../training/checkpoints/mero-bounded512.bin), [float checkpoint](../training/checkpoints/mero-bounded512.pt),
[native comparison](../backtests/bounded512-teacher.json) and [games](../backtests/bounded512-fixednodes.json).

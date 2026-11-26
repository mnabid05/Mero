# Mero's trained evaluator

Mero runs its own C++ search. Stockfish 18 is an offline teacher and a separate
match opponent; no Stockfish code, executable, or weights are embedded in the
player. PyTorch is needed to train or export new weights, not to play. The
design borrows the idea of incrementally updated, clipped integer features from
[NNUE](https://official-stockfish.github.io/docs/nnue-pytorch-wiki/docs/nnue.html).
It is not a port of Stockfish's king-conditioned network or search.

For each position, a shared embedding maps 12 piece types × 64 squares into a
hidden vector. A second accumulator sees the same board with colors swapped and
ranks reflected. After adding a bias and clipping each side to [0, 1], a linear
readout scores their difference. Training predicts a correction to Mero's C
evaluation. AdamW optimizes a robust centipawn loss and a sigmoid-score loss.
The runtime keeps its king-pressure and passer terms, adds half the learned
correction by default, and uses classical evaluation alone with three or fewer
pieces. Each search worker updates its own pair of integer accumulators by
diffing piece bitboards. Set UCI `NeuralBlend` to 0 to disable the network.

## Reproduce the release experiment

The [original float checkpoint](../training/checkpoints/mero-7.pt) contains the
selected width and learned state dictionary, not executable model code. Load it
with `training.export.load_model` to fine-tune, or reproduce the shipped header
without collecting any data:

```sh
python -m training.export training/checkpoints/mero-7.pt build/reexported-weights.h
cmp build/reexported-weights.h native/mero_weights.h
```

Use a local Stockfish 18 binary. From the repository root, in a fresh environment:

```sh
python3 -m venv build/torch-env
build/torch-env/bin/python -m pip install -r training/requirements.txt
python3 scripts/build_native.py
python3 -m training.collect build/torch-expanded.db /path/to/stockfish \
  backtests/mero-6-final-stockfish18-2300.json \
  backtests/mero-6-vs-stockfish18-2300.json \
  backtests/mero-6-confirmation-before-fast-legality.json \
  backtests/mero-6-vs-5-release-candidate.json \
  --nodes 4096 --variants 9 --seed 1702
build/torch-env/bin/python -m training.train build/torch-expanded.db build/torch-final \
  --epochs 36 --widths 32 64 96 --seed 1701 --threads 4
build/torch-env/bin/python -m training.export build/torch-final/best.pt native/mero_weights.h
python3 scripts/build_native.py
build/torch-env/bin/python -m training.audit build/torch-expanded.db build/torch-final \
  build/native/mwahaha-engine native/mero_weights.h build/torch-audit.json
```

The starting games were already public Mero match records. Deterministic short
legal walks add nearby positions; checked positions are omitted. The teacher
uses the last available exact centipawn principal-variation score, capped by
rejecting magnitudes over 1600; mate scores are not regression targets. Fixed
opening families are held out together, and validation also excludes training
piece layouts identical under color reversal. Width and epoch are chosen on
this validation split, not on release-match scores. Different compiler,
teacher binary, thread scheduling, or Torch version can affect reproduction.

The network sees piece placement, not castling rights, en passant, repetition
history or a move clock. Search handles those rules. Validation error measures
agreement with a bounded-search teacher, not Elo. Evaluate playing strength
against a full-search Mero control and a separately configured opponent.

## What the release learned

On the 19,844 held-out positions, mean absolute error relative to the teacher
fell from 387.6 cp (C prior) to 268.2 cp (prior plus the full floating-point
correction). The improvement was smaller with most pieces still on the board:

| Pieces remaining | Held-out positions | C prior MAE | With network |
| --- | ---: | ---: | ---: |
| 2–10 | 3,661 | 413.0 cp | 247.3 cp |
| 11–22 | 8,745 | 461.4 cp | 290.7 cp |
| 23–32 | 7,438 | 288.4 cp | 252.0 cp |

These are pre-search predictions at full network weight, not the native
half-blended scores or game results. A useful next experiment is to train on
more quiet middlegames and compare a king-conditioned network at equal move
time. The smaller gain with 23–32 pieces motivates that experiment; it does
not establish that a larger model will win more games.

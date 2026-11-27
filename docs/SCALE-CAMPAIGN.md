# Standalone NNUE scale campaign

The teacher is Mero 7's released evaluation and search, **not** the old HCE-only
bootstrap or Stockfish. Each game begins with eight seeded random legal plies,
then uses 5,000 nodes per move. Completed games supply mover-relative WDL;
quiet positions carry the last completed iteration's mover-relative score.
No in-check positions, best captures, promotions, mate scores, or truncated
games are used. Output remains 32 bytes/position; the full move ledger permits
independent replay. One persistent worker per available CPU and a bounded
reordering buffer write the same records regardless of thread scheduling.

```sh
python3 scripts/build_native.py --native-arch --release-control --output-dir build/producer-v2
python3 -m training.large_run build/producer-v2/mwahaha-engine build/mero20m-01 --target 20000000 --wait-power
```

Use the identical frozen binary and arguments to resume. The generator
verifies SHA-256 fingerprints before accepting sealed shards, refuses a second
writer, and ignores partial attempts. On macOS it stops at a shard boundary
if unplugged, or when discharging at or below 25% on AC. If the battery
controller reports no charge-capable adapter while the battery is draining,
that overrides a stale AC source label. With `--wait-power` it idles, then
resumes automatically when usable power returns. No system sleep or
power settings are changed. Storage: 640 MB binary for 20M rows, plus ledgers
and temporary split/shuffle files; disk headroom is checked.

If a sealed shard later loses files but its original `verified.json` survives,
use `python3 -m training.recover_sealed ROOT PRODUCER INDEX ORIGINAL_WORKERS`.
It takes the same exclusive lock, regenerates the deterministic shard, checks
every byte against the old hashes, and installs only missing files. It refuses
to create a new seal or overwrite conflicting existing data.

Split all complete shards by opening and shuffle to disk with bounded memory.
Reserve held-out whole games; keep at most 16,384 validation positions and
exclude their observed layouts (both orientations) from training. Group games by
the board after eight plies (including castling rights and a legally usable
en-passant target), not by move string. Drop entire games starting in any of
the nine reserved SPRT books, plus occurrences of their root feature layouts
from training and validation. The split requires the pinned EPD files in
`build/scale-openings` (or pass `--books`). The production
split refuses fewer than **10,000,000 usable training rows**.

Splits and exported checkpoints are written to private sibling directories,
then published by rename once the completion manifest has been written.
A failed or interrupted attempt cannot replace an existing final directory.

```sh
python -m training.large_split build/mero20m-01 build/mero20m-split
cargo build --locked --release --features metal --manifest-path training/bullet-fit/Cargo.toml --target-dir build/bullet-scale-fit
build/bullet-scale-fit/release/mero-bullet-fit build/mero20m-split/train.bullet build/mero-fit-256 12 training/bullet-probes.fen 256 0.625
python -m training.import_bullet build/mero-fit-256 build/mero20m-split build/mero-selected-256 --backend Metal
python3 scripts/build_native.py --native-arch --screlu build/mero-selected-256/weights.bin --output-dir build/mero256
python3 scripts/build_native.py --scalar-only --screlu build/mero-selected-256/weights.bin --output-dir build/mero256-scalar
python -m training.audit_screlu build/mero-selected-256/weights.bin build/mero256/mwahaha-engine build/mero256-scalar/mwahaha-engine --report build/mero256-parity.json
python -m training.qualify_standalone build/mero-selected-256 build/mero20m-split build/mero256/mwahaha-engine build/mero256-parity.json training/data/selfplay-pilot-v1/positions.bullet build/mero256-queen.json
```

See [the pinned Bullet setup](BULLET.md). The small-width networks have no
material terms, HCE blend, Mero 7 warm start or endgame fallback. Search still
adjudicates legal draws/mates. The primary recipe is 256 hidden units, eight
SCReLU output buckets, 62.5% WDL + 37.5% sigmoid(search score / 400), AdamW
and cosine LR decay. A 384-unit comparison is available. The production
trainer rejects a 512-wide run before 50M training records.

The fixed queen gate is 850–1,000 cp median, at least 150 removals, on the
fingerprinted historical cohort excluded from new datagen. The gate is only
a diagnostic, never Elo. Before promotion: verify integer parity, run a
crash-free native bench, record paired NPS, then run color-paired Fastchess
at 8+0.08, one thread/16 MiB each, normalized SPRT [0,+10], alpha=beta=.05.
Reserve disjoint fresh eight-ply EPDs for each hypothesis. Do not run clocked
tests against an all-core generator. No merge without an actual H1 decision.

### Running the frozen M4 experiment

[Campaign inputs](../backtests/scale-campaign-inputs.json) pin the release,
producer, native Metal trainer, Fastchess, six individually built search binaries,
and nine non-overlapping 2,000-pair opening sets. The actual corpus remains
local. Book seeds, full EPD hashes and candidate source revisions are public;
byte hashes for compiled programs refer to this particular M4 build.

```sh
# Use the project's Python environment with NumPy and PyTorch.
# Start/resume the complete local pipeline (including datagen):
build/torch-env/bin/python -m scripts.scale_campaign run
# Or attach to an already running large_run process:
build/torch-env/bin/python -m scripts.scale_campaign follow
# Or isolate/resume just one stage after datagen:
build/torch-env/bin/python -m scripts.scale_campaign prepare
build/torch-env/bin/python -m scripts.scale_campaign networks
build/torch-env/bin/python -m scripts.scale_campaign search
```

`follow` is a finite local job. While the generator owns the lock it uses
no compute. If the generator stops short, it exits without starting a fit;
resume datagen with the command above, then restart the controller.
The first fit uses width 256 and WDL 0.625. If its queen gate fails or the
network does not pass SPRT, try width 384 and WDL 0.5. The training split
excludes the actual qualification layouts, including their synthetic removals
and color-reversed copies. Each match requires the frozen 40-FEN depth-12
bench, an NPS sample, legal eight-ply book replay and non-discharging power.
A second, never-before-used book confirms a standalone H1 before release review.
Faulted and inconclusive runs never qualify; do not keep replaying the same
opening set until it wins. No branch is merged or pushed by the runner.

Dataset diagnostics (no model training):

```sh
python3 -m training.label_profile build/mero20m-01 build/label-profile.json --first 63
python3 -m training.replay_teacher build/mero20m-01/shard-000046 build/phase1-baseline/mwahaha-engine build/teacher-replay.json --first 17 --games 8
build/torch-env/bin/python -m training.layout_diversity build/mero20m-01 build/distinct-layouts.json --first 330
```

The last command counts distinct inputs exactly by externally sorting the
24 normalized piece-layout bytes, not by comparing labels or full game
states. Its temporary sorted runs use at most 24 bytes per record and
are removed after counting. The [first 330 shards](../backtests/scale-layout-diversity.json)
contained 6,770,829 distinct inputs among 7,117,907 records (95.12%).

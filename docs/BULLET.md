# Mero's Bullet experiment: reproduce it, don't promote it

This is an original Mero experiment using the public Bullet trainer, not a copy
of the commercial Torch chess engine. The graph uses two perspectives over a
shared 768×512 transform, squared clipped ReLUs and eight piece-count heads.
At inference all weights are embedded integers; there is no GPU dependency.
The trainer uses AdamW, cosine LR and a target of 35% actual game result plus
65% sigmoid(search cp / 400). It trains on Mero's own completed games.

The [audited pilot shard](../training/data/selfplay-pilot-v1) contains 19,521
positions, **not 50 million**. Split by whole openings before shuffling to
prevent positions from the same game leaking into validation. The 40
superbatches revisit 16,143 training positions; they do not represent 634,880
distinct positions. Bullet can use different initialization on a fresh run;
the published dataset, selected weights and fingerprints identify this run.

```sh
python3 -m training.split_selfplay training/data/selfplay-pilot-v1 build/my-split
git clone https://github.com/jw1912/bullet.git build/tools/bullet
git -C build/tools/bullet switch --detach 5d70177680437b7c0ddf958bd4722d95afa78b0c
cargo build --locked --release --features metal --manifest-path training/bullet-fit/Cargo.toml --target-dir build/bullet-fit
build/bullet-fit/release/mero-bullet-fit build/my-split/train.bullet build/my-fit 40 training/bullet-probes.fen
python -m training.import_bullet build/my-fit build/my-split build/my-selected --backend Metal
```

These training-import commands require the optional PyTorch/NumPy environment.
The local pilot used Metal on an Apple M4; CUDA and ROCm build features are
passed through to Bullet but were not run here. Rust and the Metal toolchain
are not required to **play** the already-exported model:

```sh
python3 scripts/build_native.py --native-arch --screlu training/checkpoints/mero-bullet-pilot.bin --output-dir build/pilot
python3 -m scripts.check_screlu_fixtures build/pilot/mwahaha-engine --weights training/checkpoints/mero-bullet-pilot.bin --fixture tests/bullet_golden.json
build/pilot/mwahaha-engine bench
```

Feature rows are rank-flipped during import because Bullet uses a1=0 and
Mero uses a8=0. The float conversion was checked against the final live GPU
graph on both turns and every output head (max difference <0.001 cp).
Checkpoint 35 of 40 minimized the **exported integer** mixed-target MSE on
3,374 held-out positions from 50 games. The C++ scalar and NEON kernels
matched the PyTorch integer reference exactly across 555 boards and 1,001
make/unmake scores. This proves representation and inference, not strength.

At 20,000 nodes/move the pilot lost all 64 games to Mero 7. Keep the release
for play. [Validation curve and hashes](../backtests/bullet-metal-pilot.json),
[match](../backtests/bullet-metal-fixednodes.json), [float checkpoint](../training/checkpoints/mero-bullet-pilot.pt),
[deployed bytes](../training/checkpoints/mero-bullet-pilot.bin).
The [upstream graph example](https://github.com/jw1912/bullet/blob/5d70177680437b7c0ddf958bd4722d95afa78b0c/examples/progression/2_output_buckets.rs)
documents the trainer's two-perspective and bucket conventions.

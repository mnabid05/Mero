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
python3 -m training.large_run build/producer-v2/mwahaha-engine build/mero20m-01 --target 20000000
```

Use the identical frozen binary and arguments to resume. The generator
verifies SHA-256 fingerprints before accepting sealed shards, refuses a second
writer, and ignores partial attempts. On macOS it stops at a shard boundary
if unplugged, or when discharging at or below 25% on AC. No system sleep or
power settings are changed. Storage: 640 MB binary for 20M rows, plus ledgers
and temporary split/shuffle files; disk headroom is checked.

Split all complete shards by opening and shuffle to disk with bounded memory.
Reserve held-out whole games; keep at most 16,384 validation positions and
exclude their observed layouts (both orientations) from training. The production
split refuses fewer than **10,000,000 usable training rows**.

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

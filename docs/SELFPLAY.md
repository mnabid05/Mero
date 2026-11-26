# Native self-play data, one auditable shard at a time

For a bootstrap run, use Mero's hand-coded evaluation with the native search.
The generator uses one search thread per game and parallelizes across games.
It never changes the UCI defaults. A bounded shard is reproducible across
worker counts; start each shard in a **new** directory and use a distinct seed.

```sh
python3 scripts/build_native.py --native-arch --release-control --output-dir build/bootstrap
build/bootstrap/mwahaha-engine datagen build/my-shard 256 5000 4 290341 hce
python3 -m training.audit_selfplay build/my-shard
python3 -m training.split_selfplay build/my-shard build/my-split
```

Use `active` instead of `hce` for subsequent self-play with the weights compiled
into the supplied executable. This pilot starts with eight uniformly sampled
legal moves (not a balanced tournament book). The node limit applies per
searched move. Training labels use the last completed search iteration; a
position in check, a best capture (including en passant), a promotion, an
unfinished search depth or a mate score cannot produce a record. Each game
ends by checkmate, stalemate, repetition, the fifty-move rule or insufficient
material. A game stopped at the 512-ply safety cap provides **no labels**.

`positions.bullet` is headerless: 32 bytes per record, normalized to the mover,
with integer centipawns and outcome. `games.tsv` stores every move, kept plies,
termination and offset. Only consume a shard with a valid `COMPLETE.json` and
matching counts. The full audit checks each legal move, each retained board,
its result, and the terminal position using the independent Python engine.
For a byte-by-byte check against **upstream bulletformat 1.8.0**:

```sh
cargo build --locked --release --manifest-path training/bullet-oracle/Cargo.toml --target-dir build/oracle
python3 -m training.audit_selfplay build/my-shard --oracle build/oracle/release/mero-bullet-oracle
```

The pilot split groups by the eight-ply opening, shuffles deterministically,
and excludes feature-identical/color-reversed training layouts from validation.
It is an in-memory utility for shards of at most one million rows, not a
50M-position distributed shuffler. [Pilot data audit](../backtests/selfplay-pilot-audit.json)
and [split fingerprints](../backtests/selfplay-pilot-split.json).

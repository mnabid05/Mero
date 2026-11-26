# Mero engine gates

Use the existing Mero checkout. The web app and UCI clients continue using
`mwahaha-engine`; the roadmap's “AstraChess” refers to the role of this native
engine, not a second executable. All dependencies below are local developer
tools, not runtime dependencies. No sudo is needed with a working C11 and
C++20 compiler, make, git, Python 3, curl and unzip.

## Phase 1: correctness and speed

```sh
python3 scripts/build_native.py --native-arch --output-dir build/candidate
python3 -m scripts.perft_gate build/candidate/mwahaha-engine --min-nps 50000000
build/candidate/mwahaha-engine bench
python3 -m unittest tests.test_native_invariants
```

The deep reference is the [six CPW positions](https://www.chessprogramming.org/Perft_Results).
Each is searched once with one thread, no cache, counting a legal list directly
at depth one. The rate is total leaf nodes divided by total wall time including
startup. It is **not search NPS**. The separate search bench resets all search
tables between 40 fixed positions, searches to depth 12 (or a proven mate) and
reports visited nodes and search throughput. Run `bench 3` for a quick smoke test.
The slider invariant checks the new table against the old ray-scan oracle for
all 107,648 relevant blocker subsets and again with irrelevant bits occupied.
To regenerate the multipliers independently:

```sh
c++ -std=c++20 -O3 scripts/generate_magics.cpp -o build/generate-magics
build/generate-magics --output build/recreated-magics.h
cmp native/magic_numbers.h build/recreated-magics.h
```

## Match prerequisites

```sh
git clone https://github.com/Disservin/fastchess.git build/tools/fastchess
git -C build/tools/fastchess checkout 07fc150ac666f0c4e590810d63bce4d280ef8d2e
make -C build/tools/fastchess -j4
mkdir -p build/books
curl -fL https://raw.githubusercontent.com/official-stockfish/books/37751b08db745aa02babfa74056dd1168b9da803/8moves_v3.pgn.zip -o build/books/8moves_v3.pgn.zip
unzip -n build/books/8moves_v3.pgn.zip -d build/books
```

Verify extracted PGN SHA-256 `5835239f88cc2c7511b177c32392a69f3ede21819cf0616f80a7f907cd21d17e`.
The [official book](https://github.com/official-stockfish/books) has 34,700
16-ply PGN lines. Pass `format=pgn plies=8` for the guide's eight **plies**;
do not rename this PGN to EPD. Distinct lines may share their first eight plies.
Use paired colors, fixed seed, the same hash and one engine thread on each
side. Use a fresh directory under `build/` per experiment. No PGN output is
necessary; preserve the aggregate results, tool revisions, binary hashes and
exit reasons. An accepted H1 with engine crashes, illegal moves or repeated
time forfeits is not a clean pass.

```sh
root=$(pwd)
mkdir -p build/match-01
cd build/match-01
"$root/build/tools/fastchess/fastchess" \
  -engine "cmd=$root/build/candidate/mwahaha-engine" name=New \
  -engine "cmd=$root/build/baseline/mwahaha-engine" name=Main \
  -each tc=8+0.08 option.Threads=1 option.Hash=16 \
  -openings "file=$root/build/books/8moves_v3.pgn" format=pgn order=random plies=8 \
  -srand 1701 -rounds 2000 -repeat -concurrency 4 \
  -sprt elo0=0 elo1=10 alpha=0.05 beta=0.05 model=normalized -recover
```

Build the baseline from the frozen main revision with the same compiler and
flags. The cap is 2,000 **pairs**. Accept or reject only at Fastchess's LLR
boundary (approximately ±2.944); a cap without a boundary is inconclusive.
Do not replace this gate with a two-game infrastructure smoke test.

Capture Fastchess stdout in a local match log and use
`python3 -m scripts.sprt_status build/<run>/match.log` from the repo root to
summarize W/D/L, warnings, faults and the latest printed LLR. The summarizer
does not edit branches. It requires an explicit test decision and matching
boundary; a capped or incomplete result never authorizes promotion.

## Later: Bullet

Pinned [Bullet](https://github.com/jw1912/bullet) source: `5d70177680437b7c0ddf958bd4722d95afa78b0c`.
Clone it to `build/tools/bullet` and check out that revision. The upstream
supports a Metal backend on Apple Silicon; do not install NVIDIA CUDA on this
Mac. Fetching the trainer is not a trained NNUE. Mero's existing PyTorch
checkpoint remains in service until candidate weights pass integer parity
and the paired strength gate.

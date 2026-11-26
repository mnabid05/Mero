"""Verify the six CPW reference positions; report single-thread uncached perft."""
import argparse
import hashlib
import json
import platform
import re
import subprocess
import time
from pathlib import Path

# https://www.chessprogramming.org/Perft_Results ; index d contains perft(d).
CASES = (
    ("start", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
     (1,20,400,8902,197281,4865609,119060324)),
    ("kiwipete", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
     (1,48,2039,97862,4085603,193690690)),
    ("rook-ending", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
     (1,14,191,2812,43238,674624,11030083,178633661)),
    ("castling-promotions", "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
     (1,6,264,9467,422333,15833292)),
    ("underpromotion", "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
     (1,44,1486,62379,2103487,89941194)),
    ("middlegame", "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
     (1,46,2079,89890,3894594,164075551)),
)

def gate(engine, quick=False):
    results = []
    for name, fen, expected in CASES:
        depth = 3 if quick else len(expected)-1
        start = time.monotonic()
        output = subprocess.check_output([str(engine.resolve()), "--perft-fen", str(depth), fen],
                                         text=True, timeout=300)
        elapsed = time.monotonic()-start  # Includes process startup, including table creation.
        match = re.fullmatch(r"depth (\d+): (\d+) nodes in \d+ ms\s*", output)
        if not match or (int(match[1]), int(match[2])) != (depth, expected[depth]):
            raise ValueError(f"{name} expected D{depth}={expected[depth]}, got {output!r}")
        results.append(dict(name=name, depth=depth, nodes=expected[depth],
                            wall_seconds=elapsed, nps=round(expected[depth]/elapsed)))
    return dict(engine_sha256=hashlib.sha256(engine.read_bytes()).hexdigest(),
                platform=platform.platform(), cases=results, weighted_nps=round(
                    sum(r["nodes"] for r in results)/sum(r["wall_seconds"] for r in results)))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("engine", type=Path)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--min-nps", type=int, default=0, help="minimum deep-suite aggregate NPS")
    p.add_argument("--json", type=Path)
    args = p.parse_args()
    if args.min_nps < 0 or (args.quick and args.min_nps):
        p.error("a speed gate requires a deep run and a nonnegative threshold")
    report = gate(args.engine, args.quick)
    output = json.dumps(report, indent=2)
    print(output)
    if args.json:
        args.json.write_text(output + "\n")
    return int(report["weighted_nps"] < args.min_nps)

if __name__ == "__main__":
    raise SystemExit(main())

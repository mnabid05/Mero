"""Crash/depth/legality gate using the same 40 positions on old and new UCI binaries."""
import argparse
import re
import subprocess
from pathlib import Path

from chess_ai.board import Board
from training.large_run import atomic, sha

SUITE = Path(__file__).resolve().parents[1] / "native/bench_positions.h"
SUITE_HASH = "3894af7c7678198189ecff25c72f7489b7ecbbf52ea34034b26869d13fc6862d"


def bench(exe, depth=12, timeout=240):
    if sha(SUITE) != SUITE_HASH:
        raise ValueError("changed bench suite")
    fens = re.findall(r'^\s*"([^"]+)"', SUITE.read_text(), re.M)
    if len(fens) != 40:
        raise ValueError("expected 40 fixed FENs")
    samples = []
    for fen in fens:
        command = (f"uci\nsetoption name Hash value 16\nsetoption name Threads value 1\n"
                   f"ucinewgame\nposition fen {fen}\ngo depth {depth}\n")
        proc = subprocess.run([exe], input=command, capture_output=True, text=True,
                              timeout=timeout, check=True)
        info = re.findall(r"^info depth (\d+) score (cp|mate) (-?\d+) nodes (\d+).*? time (\d+)",proc.stdout,re.M)
        moves = re.findall(r"^bestmove (\S+)",proc.stdout,re.M)
        if not info or len(moves) != 1:
            raise ValueError(f"incomplete UCI response for {fen}")
        reached, unit, score, nodes, ms = info[-1]
        if (int(reached) != depth and unit != "mate") or int(nodes) < 1:
            raise ValueError(f"incomplete search for {fen}: {info[-1]}")
        Board.from_fen(fen).find_legal_move(moves[0])
        samples.append(dict(fen=fen,move=moves[0],depth=int(reached),score=[unit,int(score)],
                            nodes=int(nodes),ms=int(ms)))
    nodes = sum(r["nodes"] for r in samples)
    elapsed = sum(r["ms"] for r in samples)
    return dict(binary_sha256=sha(exe),suite_sha256=SUITE_HASH,depth=depth,
                nodes=nodes,engine_nps=1000*nodes//max(1,elapsed),positions=samples)


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("binary",type=Path); p.add_argument("out",type=Path)
    p.add_argument("--depth",type=int,choices=range(1,13),default=12)
    a=p.parse_args()
    result=bench(a.binary,a.depth)
    atomic(a.out,result)
    print(f"{len(result['positions'])} positions; {result['nodes']} nodes; {result['engine_nps']} nps")

"""Cross-check implemented integer math and actual reversible board transitions."""
import argparse
import json
import random
import subprocess
from pathlib import Path
import torch
from chess_ai.board import Board
from .screlu_data import encode
from .screlu_integer import Reference

START = Board.starting().to_fen()
SPECIAL = [
    (START, "e2e4 a7a6 e4e5 d7d5 e5d6"),
    ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1","e1g1 e8c8"),
    ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1","e1c1 e8g8"),
    ("1r5k/P7/8/8/8/8/7p/K7 w - - 0 1","a7b8n h2h1r"),
    ("4k3/8/8/8/3Pp3/8/8/4K3 b - d3 0 1","e4d3"),
]
def ask(binary,flag,lines):
    p = subprocess.run([str(binary.resolve()),flag],input="\n".join(lines)+"\n",
                       check=True,capture_output=True,text=True,timeout=60)
    return [[int(x) for x in line.split()] for line in p.stdout.splitlines()]

def pad_inputs(fens):
    data=[encode(f)[0] for f in fens]
    return (torch.tensor([x[i] for x in data]) for i in (0,1))

def run(weights,binaries):
    rng=random.Random(1701)
    lines=list(SPECIAL)
    for _ in range(12):
        board=Board.starting()
        moves=[]
        for _ in range(40):
            legal=board.legal_moves()
            if not legal: break
            move=rng.choice(legal)
            moves.append(move.uci)
            board.push(move)
        lines.append((START," ".join(moves)))
    traces=[]
    for fen,sequence in lines:
        board=Board.from_fen(fen)
        forward=[fen]
        for move in sequence.split():
            board.play_uci(move)
            forward.append(board.to_fen())
        traces.append(forward+forward[-2::-1])
    fens=set(f for path in traces for f in path)
    # Cover every material bucket boundary and both turns, even if random
    # playouts didn't reach those piece counts. Static-score fixtures only.
    pieces=[(s,p) for s,p in Board.starting().pieces() if p.lower()!="k"]
    for count in range(2,33):
        board=Board.from_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        for sq,piece in pieces[:count-2]:
            board.squares[sq]=piece
        for turn in ("b","w"):
            board.turn=turn
            fens.add(board.to_fen())
    unique=sorted(fens)
    ref=Reference(weights.read_bytes())
    truth={}
    for i in range(0,len(unique),32):
        chunk=unique[i:i+32]
        truth.update(zip(chunk,ref(*pad_inputs(chunk)).tolist(),strict=True))
    for binary in binaries:
        if ask(binary,"--screlu-scores",unique) != [[truth[f]] for f in unique]:
            raise ValueError(f"{binary}: fresh FEN parity failure")
        actual=ask(binary,"--screlu-trace",[f"{f} | {seq}" for f,seq in lines])
        if actual != [[truth[f] for f in path] for path in traces]:
            raise ValueError(f"{binary}: move/undo parity failure")
    return dict(kernels=len(binaries), unique_fens=len(unique),material_buckets=8,
                trace_paths=len(traces),trace_scores=sum(map(len,traces)),integer_mismatches=0)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("weights",type=Path)
    p.add_argument("binaries",type=Path,nargs="+")
    a=p.parse_args()
    torch.set_num_threads(1)
    print(json.dumps(run(a.weights,a.binaries),indent=2))

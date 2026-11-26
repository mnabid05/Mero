"""Generate a small golden test file with the integer Torch reference."""
import argparse
import hashlib
import json
from pathlib import Path
import torch
from chess_ai.board import Board
from .audit_screlu import SPECIAL, pad_inputs
from .screlu_integer import Reference

def generate(weights):
    blob=weights.read_bytes()
    ref=Reference(blob)
    examples=[]
    def score(fen):
        return int(ref(*pad_inputs([fen]))[0])
    pieces=[(sq,p) for sq,p in Board.starting().pieces() if p.lower()!="k"]
    for n in range(2,33):
        board=Board.from_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        for sq,p in pieces[:n-2]: board.squares[sq]=p
        for turn in ("w","b"):
            board.turn=turn
            fen=board.to_fen()
            examples.append([fen,score(fen)])
    paths=[]
    for fen,seq in SPECIAL:
        b=Board.from_fen(fen)
        scores=[score(fen)]
        for m in seq.split():
            b.play_uci(m)
            scores.append(score(b.to_fen()))
        paths.append([f"{fen} | {seq}",scores+scores[-2::-1]])
    return dict(sha256=hashlib.sha256(blob).hexdigest(),positions=examples,paths=paths)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("weights",type=Path)
    p.add_argument("fixture",type=Path)
    args=p.parse_args()
    torch.set_num_threads(1)
    args.fixture.write_text(json.dumps(generate(args.weights),indent=2)+"\n")

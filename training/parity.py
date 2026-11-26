import argparse
import json
import sqlite3
import subprocess
from pathlib import Path
import torch
from chess_ai.board import Board
from .features import indices, flip, PADDING
from .export import load_model

def check(checkpoint, binary, database):
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        all_fens = [r[0] for r in db.execute("SELECT fen FROM samples WHERE cp IS NOT NULL ORDER BY fen")]
    fens = all_fens[::max(1, len(all_fens)//512)][:512]
    scores = subprocess.run([binary, "--neural-scores"], input="\n".join(fens)+"\n",
                            text=True, capture_output=True, check=True, timeout=30)
    model = load_model(checkpoint)
    ids = [indices(Board.from_fen(fen)) for fen in fens]
    def padded(row):
        return row + [PADDING] * (32-len(row))
    with torch.no_grad():
        predicted = model(torch.tensor([padded(row) for row in ids]),
                          torch.tensor([padded(list(map(flip,row))) for row in ids]),
                          torch.zeros(len(ids)))
    actual = torch.tensor([int(x) for x in scores.stdout.splitlines()])
    if len(actual) != len(ids):
        raise ValueError("incomplete native scores")
    delta = (actual-predicted).abs()
    return dict(samples=len(ids), mean_abs_cp=delta.mean().item(), max_abs_cp=delta.max().item())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("checkpoint","binary","database"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.checkpoint,args.binary,args.database), indent=2))

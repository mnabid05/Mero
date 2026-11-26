"""Reserve fresh disjoint 8-ply FENs in a campaign registry; pair each with reversed colors."""
import argparse
import hashlib
import json
import random
import sqlite3
import subprocess
from pathlib import Path
from chess_ai.board import Board
from training.large_run import sha

def create(registry,dest,control,seed,count=2000):
    if dest.exists(): raise FileExistsError(dest)
    rng=random.Random(seed)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(registry) as db:
        db.execute("CREATE TABLE IF NOT EXISTS positions(epd TEXT PRIMARY KEY, seed INTEGER NOT NULL)")
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM positions WHERE seed=? LIMIT 1",(seed,)).fetchone():
            raise ValueError("opening campaign seed already used")
        accepted=[]
        while len(accepted)<count:
            batch=[]
            for _ in range(min(128,count-len(accepted)+32)):
                b=Board.starting(); moves=[]
                for _ in range(8):
                    legal=b.legal_moves()
                    if not legal: break
                    m=rng.choice(legal); moves.append(m.uci); b.push(m)
                if len(moves)==8 and not b.is_in_check() and b.legal_moves():
                    batch.append((b.to_fen(),moves))
            proc=subprocess.run([control,"--static-scores"],input="".join(f+"\n" for f,_ in batch),
                                text=True,check=True,capture_output=True,timeout=60)
            for (fen,moves),cp in zip(batch,proc.stdout.splitlines(),strict=True):
                if abs(int(cp))>120: continue
                epd=" ".join(fen.split()[:4])
                if db.execute("INSERT OR IGNORE INTO positions VALUES(?,?)",(epd,seed)).rowcount!=1: continue
                accepted.append((epd,moves,int(cp)))
                if len(accepted)==count: break
        with dest.open("x") as out:
            for epd,_,_ in accepted: print(epd,file=out)
        manifest=dict(format="fresh-8ply-v1",pairs=count,seed=seed,sha256=sha(dest),
                      control_sha256=sha(control),openings=accepted)
        dest.with_suffix(".json").write_text(json.dumps(manifest,separators=(",",":"))+"\n")
    return manifest["sha256"]

def verify(path, *, replay=False):
    data=json.loads(path.with_suffix(".json").read_text())
    epds=path.read_text().splitlines()
    if (data["format"]!="fresh-8ply-v1" or sha(path)!=data["sha256"] or
        len(epds)!=data["pairs"] or len(set(epds))!=len(epds) or
        [r[0] for r in data["openings"]]!=epds or
        any(len(moves)!=8 or abs(cp)>120 for _,moves,cp in data["openings"])):
        raise ValueError("invalid or modified opening shard")
    if replay:
        for epd,moves,_ in data["openings"]:
            board=Board.starting()
            for move in moves:
                board.play_uci(move)
            if (" ".join(board.to_fen().split()[:4])!=epd or
                    board.is_in_check() or not board.legal_moves()):
                raise ValueError("opening does not match its legal eight-ply replay")
    return data
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("registry","dest","control"): p.add_argument(key,type=Path)
    p.add_argument("--seed",required=True,type=int)
    a=p.parse_args()
    print(create(**vars(a)))

"""Stable, opening-held-out teacher-score split, shared by training and audit."""
import hashlib
import sqlite3
import torch
from chess_ai.board import Board
from .features import indices, flip, PADDING
from .split import validation_openings

def encode(fen):
    board = Board.from_fen(fen)
    ids = sorted(indices(board))
    if not 2 <= len(ids) <= 32:
        raise ValueError("unsupported piece count")
    reflected = sorted(map(flip,ids))
    # The network observes relative side to move; also remove color-reversed
    # and opposite-turn duplicates across train/validation conservatively.
    identity = min(tuple(ids),tuple(reflected))
    pad = [PADDING]*(32-len(ids))
    sides = (ids+pad,reflected+pad) if board.turn=="w" else (reflected+pad,ids+pad)
    return sides, identity, 1 if board.turn=="w" else -1

def load(database,seed,train_limit=0,valid_limit=0):
    with sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro",uri=True) as db:
        rows = db.execute("SELECT fen, opening, cp FROM samples WHERE cp IS NOT NULL ORDER BY fen").fetchall()
    held = validation_openings((r[1] for r in rows),seed)
    # Rank first so subset selection is independent of SQLite insertion order.
    rows.sort(key=lambda r: hashlib.blake2b(f"{seed}|{r[0]}".encode(),digest_size=16).digest())
    seen = set()
    packs = []
    for validation,limit in ((False,train_limit),(True,valid_limit)):
        x,y,z,fens = [],[],[],[]
        for fen,name,cp in rows:
            if (name in held) != validation: continue
            (a,b),identity,sign = encode(fen)
            if validation and identity in seen: continue
            if not validation: seen.add(identity)
            x.append(a); y.append(b); z.append(sign*cp); fens.append(fen)
            if limit and len(z)>=limit: break
        if not z: raise ValueError("empty split")
        packs.append((torch.tensor(x),torch.tensor(y),torch.tensor(z,dtype=torch.float32),fens))
    return *packs,sorted(held)

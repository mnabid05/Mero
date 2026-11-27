"""Canonical eight-ply partitions shared by the validation and match holdouts."""
import csv
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from chess_ai.backtest import repetition_key
from chess_ai.board import Board
from training.large_run import sha

PINS=Path(__file__).resolve().parents[1]/"backtests/scale-campaign-inputs.json"
POLICY="canonical-eight-ply-v1"
TRAIN,VALID,RESERVED,SHORT=range(4)


def book_hashes():
    return {name:spec["sha256"] for name,spec in json.loads(PINS.read_text())["books"].items()}


def reserved_books(directory):
    canonical={}
    for name,fingerprint in book_hashes().items():
        path=directory/(name+".epd")
        if sha(path)!=fingerprint: raise ValueError(f"reserved book changed: {name}")
        for epd in path.read_text().splitlines():
            board=Board.from_fen(epd+" 0 5")
            key=repetition_key(board)
            if key in canonical:
                raise ValueError("reserved match books collide after canonicalization")
            canonical[key]=name
    return canonical


@lru_cache(maxsize=12000)
def _prefix(moves):
    # These cached boards are only ever read/copied.
    if not moves: return Board.starting()
    b=_prefix(moves[:-1]).copy(); b.play_uci(moves[-1]); return b


def opening_key(moves):
    if len(moves)!=8: raise ValueError("need eight opening plies")
    b=_prefix(moves[:4]).copy()
    for move in moves[4:]: b.play_uci(move)
    return repetition_key(b)


def partition(shards,reserved,seed):
    masks=[]
    excluded_games=Counter()
    excluded_rows=Counter()
    short=0
    digest=hashlib.sha256()
    try:
        for path in shards:
            mask=bytearray()
            with (path/"games.tsv").open() as stream:
                for row in csv.DictReader(stream,delimiter="\t"):
                    moves=tuple(row["uci_moves"].split(maxsplit=8)[:8])
                    if len(moves)<8:
                        if int(row["rows"]): raise ValueError("label before the opening finished")
                        mask.append(SHORT); short+=1
                        continue
                    key=opening_key(moves)
                    if key in reserved:
                        name=reserved[key]
                        excluded_games[name]+=1
                        excluded_rows[name]+=int(row["rows"])
                        mask.append(RESERVED)
                    else:
                        h=hashlib.blake2b(f"{seed}/{key}".encode(),digest_size=8).digest()
                        mask.append(VALID if int.from_bytes(h,"little")%64==0 else TRAIN)
            digest.update(len(mask).to_bytes(4,"little")+mask)
            masks.append(bytes(mask))
    finally:
        _prefix.cache_clear()
    return masks,dict(policy=POLICY,book_sha256=book_hashes(),canonical_positions=len(reserved),
                      excluded_games=dict(excluded_games),excluded_records=dict(excluded_rows),
                      terminated_before_ply8=short,membership_sha256=digest.hexdigest())

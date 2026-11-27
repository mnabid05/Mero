"""Split by games/openings, hold validation in bounded memory and externally shuffle training."""
import argparse
import csv
import json
import random
import struct
import tempfile
from contextlib import ExitStack
from pathlib import Path
import numpy as np
from .large_run import atomic, check_shard, sha
from .probe_material import inputs, PANEL, PANEL_HASH
from .opening_holdout import TRAIN,VALID,partition,reserved_books
from .publish import unpublished
from chess_ai.board import Board

def flipped_layout(layout):
    occ=int.from_bytes(layout[:8],"little")
    ranks=[[] for _ in range(8)]
    i=0
    while occ:
        sq=(occ&-occ).bit_length()-1
        pc=(layout[8+i//2]>>(4*(i%2)))&15
        ranks[sq//8].append(pc^8)
        occ&=occ-1; i+=1
    pcs=bytearray(16)
    for i,pc in enumerate(pc for rank in reversed(ranks) for pc in rank):
        pcs[i//2]|=pc<<(4*(i%2))
    return layout[:8][::-1]+pcs

def layout_bytes(board):
    if board.turn!="w": raise ValueError("expected white-to-move layout")
    sorted_pieces=sorted((sq^56,p) for sq,p in board.pieces())
    occ=sum(1<<sq for sq,_ in sorted_pieces)
    pcs=bytearray(16)
    for i,(_,p) in enumerate(sorted_pieces):
        code="pnbrqk".index(p.lower()) | (8 if p.islower() else 0)
        pcs[i//2] |= code<<((i%2)*4)
    return occ.to_bytes(8,"little")+pcs

def panel_layouts():
    """Freeze and exclude both sides of every pre-registered base/removal case."""
    if sha(PANEL)!=PANEL_HASH:
        raise ValueError("qualification panel changed")
    _,fens,_=inputs(PANEL,256)
    blocked=set()
    for fen in fens:
        board=Board.from_fen(fen)
        layout=layout_bytes(board)
        blocked.update((layout,flipped_layout(layout)))
    return blocked

def games(shard,membership):
    with (shard/"positions.bullet").open("rb") as stream,(shard/"games.tsv").open() as ledger:
        offset=0
        for code,row in zip(membership,csv.DictReader(ledger,delimiter="\t"),strict=True):
            n=int(row["rows"])
            if int(row["first"])!=offset or not 0<=n<=512: raise ValueError("invalid row range")
            offset+=n
            data=stream.read(n*32)
            if len(data)!=n*32: raise ValueError("unexpected end of game")
            if code in (TRAIN,VALID):
                yield code==VALID,data
        if stream.read(1): raise ValueError("unclaimed records")

def split(root,dest,minimum=10_000_000,seed=831908,valid_limit=16384,books=None):
    with unpublished(dest,"split.json") as staging:
        return _split(root,staging,minimum,seed,valid_limit,books)

def _split(root,dest,minimum,seed,valid_limit,books):
    shards=sorted(root.glob("shard-[0-9][0-9][0-9][0-9][0-9][0-9]"))
    cfg=json.loads((root/"campaign.json").read_text())
    n=0
    for i,path in enumerate(shards):
        if path.name!=f"shard-{i:06d}": raise ValueError("noncontiguous shard ids")
        n+=check_shard(path,cfg,i,hashes=True)
    if n<minimum: raise ValueError(f"only {n} sealed positions (need {minimum} training rows)")
    reserved=reserved_books(books if books is not None else root.parent/"scale-openings")
    membership,policy=partition(shards,reserved,seed)
    excluded=panel_layouts()
    panel_count=len(excluded)
    for epd in reserved:
        layout=layout_bytes(Board.from_fen(epd+" 0 5"))
        excluded.update((layout,flipped_layout(layout)))
    rng=random.Random(seed)
    held_seen=0
    sample=[]
    for shard,mask in zip(shards,membership,strict=True):
        for held,data in games(shard,mask):
            if held:
                for off in range(0,len(data),32):
                    held_seen+=1
                    row=data[off:off+32]
                    if len(sample)<valid_limit: sample.append(row)
                    else:
                        replacement=rng.randrange(held_seen)
                        if replacement<valid_limit: sample[replacement]=row
    unique=[]
    for row in sample:
        if row[:24] not in excluded:
            excluded.update((row[:24],flipped_layout(row[:24]))); unique.append(row)
    if not unique: raise ValueError("empty validation split")
    dest.mkdir(parents=True,exist_ok=False)
    blocked=nt=ng=nvg=0
    nbuckets=128
    with tempfile.TemporaryDirectory(prefix="shuffle-",dir=dest) as scratch:
        paths=[Path(scratch)/str(i) for i in range(nbuckets)]
        with ExitStack() as handles:
            files=[handles.enter_context(p.open("wb")) for p in paths]
            for shard,mask in zip(shards,membership,strict=True):
                for held,data in games(shard,mask):
                    if held:
                        nvg+=1
                        continue
                    ng+=1
                    keep=bytearray()
                    for off in range(0,len(data),32):
                        if data[off:off+24] not in excluded: keep.extend(data[off:off+32])
                        else: blocked+=1
                    nt+=len(keep)//32
                    files[rng.randrange(nbuckets)].write(keep)
        if nt<minimum: raise ValueError(f"only {nt} usable training records")
        with (dest/"train.bullet").open("xb") as train:
            rng.shuffle(paths)
            shuffle=np.random.default_rng(seed)
            for path in paths:
                if path.stat().st_size>128*1024**2: raise ValueError("shuffle bucket too large")
                rows=np.fromfile(path,dtype="V32")
                shuffle.shuffle(rows)
                rows.tofile(train)
    rng.shuffle(unique)
    (dest/"valid.bullet").write_bytes(b"".join(unique))
    if n!=nt+blocked+held_seen+sum(policy["excluded_records"].values()):
        raise ValueError("records did not reconcile across game partitions")
    info=dict(schema=2,panel_sha256=PANEL_HASH,excluded_panel_layouts=panel_count,opening_holdout=policy,
              seed=seed,source_config=cfg,sealed_shards=len(shards),source_positions=n,
              holdout_seen=held_seen,removed_train_collisions=blocked,groups={})
    for name,positions,ngames in [("train",nt,ng),("valid",len(unique),nvg)]:
        p=dest/(name+".bullet")
        if p.stat().st_size!=positions*32: raise ValueError("output length mismatch")
        info["groups"][name]=dict(positions=positions,games=ngames,sha256=sha(p))
    atomic(dest/"split.json",info)
    return info

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("root","dest"): p.add_argument(name,type=Path)
    p.add_argument("--books",type=Path,help="directory containing the pinned match EPDs")
    a=p.parse_args()
    print(json.dumps(split(a.root,a.dest,books=a.books),indent=2))

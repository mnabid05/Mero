"""Relative material sensitivity on counterfactual boards (diagnostic, not a tactics test)."""
import argparse
import hashlib
import json
import random
import statistics
import struct
import subprocess
from pathlib import Path
from chess_ai.board import Board

def inputs(path,limit):
    size=path.stat().st_size
    if size%32: raise ValueError("truncated Bullet file")
    def records():
        # A deterministic bounded sample; never load the training corpus to probe it.
        indices=random.Random(4816).sample(range(size//32),min(size//32,limit*16))
        with path.open("rb") as stream:
            for ix in indices:
                stream.seek(32*ix)
                yield struct.unpack("<Q16s8x",stream.read(32))
    rows=records()
    fens=[]
    cases=[]
    positions=0
    seen=set()
    for occ,pieces in rows:
        layout=(occ,pieces)
        count=occ.bit_count()
        # Keep the exact same network bucket after removing one piece.
        if count<8 or (count-2)%4==0 or layout in seen: continue
        seen.add(layout)
        board=Board(castling_rights=set())
        j=0
        while occ:
            sq=(occ&-occ).bit_length()-1
            pc=(pieces[j//2]>>(4*(j%2)))&15
            board.squares[sq^56]="PNBRQKpnbrqk"[(pc&7)+6*bool(pc&8)]
            j+=1; occ&=occ-1
        base=len(fens)
        fens.append(board.to_fen())
        for kind in "PNBRQpnbrq":
            sq=next((i for i,p in board.pieces() if p==kind),None)
            if sq is None: continue
            board.squares[sq]=None
            cases.append((base,len(fens),kind))
            fens.append(board.to_fen())
            board.squares[sq]=kind
        positions+=1
        if positions==limit: break
    return positions,fens,cases

def probe(data,engines):
    n,fens,cases=inputs(data,256)
    with data.open("rb") as stream: digest=hashlib.file_digest(stream,"sha256").hexdigest()
    out=dict(positions=n,removals=len(cases),dataset_sha256=digest,
             method="median sign-adjusted cp loss on removing one piece, normalized White to move; same material bucket; synthetic diagnostic only",engines={})
    for name,exe in engines:
        p=subprocess.run([exe,"--static-scores"],input="\n".join(fens)+"\n",text=True,capture_output=True,
                         check=True,timeout=90)
        scores=list(map(int,p.stdout.splitlines()))
        if len(scores)!=len(fens): raise ValueError("missing evaluation")
        groups={k:[] for k in "PNBRQ"}
        for a,b,kind in cases:
            groups[kind.upper()].append((scores[a]-scores[b])*(1 if kind.isupper() else -1))
        out["engines"][name]=dict(sha256=hashlib.sha256(Path(exe).read_bytes()).hexdigest(),
            by_piece={k:dict(n=len(v),median_cp=statistics.median(v),nonpositive=sum(x<=0 for x in v))
                      for k,v in groups.items()})
    return out

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("data",type=Path); p.add_argument("report",type=Path)
    p.add_argument("--engine",action="append",nargs=2,required=True,metavar=("NAME","EXECUTABLE"))
    a=p.parse_args()
    a.report.write_text(json.dumps(probe(a.data,a.engine),indent=2)+"\n")

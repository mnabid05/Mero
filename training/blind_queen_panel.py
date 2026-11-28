"""Extra queen-removal panel for the fourth fit, chosen by layout alone before training."""
import argparse
import hashlib
import json
import statistics
import subprocess
from pathlib import Path
from chess_ai.board import Board
from .large_run import sha,atomic
from .large_split import layout_bytes,flipped_layout
from .probe_material import inputs

def freeze(split,out):
    if out.exists(): raise FileExistsError(out)
    meta=json.loads((split/"split.json").read_text())
    valid=split/"valid.bullet"
    if sha(valid)!=meta["groups"]["valid"]["sha256"]: raise ValueError("changed validation set")
    _,fens,cases=inputs(valid,256)
    cases=[(a,b,k) for a,b,k in cases if k.upper()=="Q"]
    layouts={i:layout_bytes(Board.from_fen(fens[i])) for a,b,_ in cases for i in (a,b)}
    keys={i:{v,flipped_layout(v)} for i,v in layouts.items()}
    banned=set().union(*keys.values())
    seen=set()
    h=hashlib.sha256()
    with (split/"train.bullet").open("rb") as stream:
        while raw:=stream.read(32*65536):
            h.update(raw)
            if len(raw)%32: raise ValueError("truncated training records")
            seen.update(key for i in range(0,len(raw),32) if (key:=raw[i:i+24]) in banned)
    if h.hexdigest()!=meta["groups"]["train"]["sha256"]: raise ValueError("changed training set")
    clean=[(fens[a],fens[b],1 if k=="Q" else -1) for a,b,k in cases if not ((keys[a]|keys[b])&seen)]
    if len(clean)<150: raise ValueError("insufficient unseen pairs")
    atomic(out,dict(method="deterministic validation layouts; no base or removed layout in the training file in either orientation",
                    train_sha256=h.hexdigest(),valid_sha256=sha(valid),before=len(cases),pairs=clean))

def assess(panel,expected,engine):
    if sha(panel)!=expected: raise ValueError("supplementary panel changed")
    pairs=json.loads(panel.read_text())["pairs"]
    fens=[f for base,removed,_ in pairs for f in (base,removed)]
    proc=subprocess.run([engine,"--static-scores"],input="\n".join(fens)+"\n",capture_output=True,text=True,check=True,timeout=90)
    scores=list(map(int,proc.stdout.splitlines()))
    if len(scores)!=len(fens): raise ValueError("missing scores")
    deltas=[s*(scores[2*i]-scores[2*i+1]) for i,(_,_,s) in enumerate(pairs)]
    m=statistics.median(deltas)
    return dict(n=len(deltas),median_cp=m,nonpositive=sum(v<=0 for v in deltas),
                passed=len(deltas)>=150 and 850<=m<=1000,panel_sha256=expected,binary_sha256=sha(engine))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("split",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();freeze(a.split,a.out)
    print(sha(a.out),len(json.loads(a.out.read_text())["pairs"]))

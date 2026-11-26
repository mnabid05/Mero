"""Compare released and candidate native static scores on the same held-out rows."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
import torch
from .audit_screlu import ask
from .screlu_data import load

def assess(database, release, candidate, weights, fit, seed=1701):
    with sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro",uri=True) as db:
        teacher=json.loads(db.execute("SELECT config FROM meta").fetchone()[0])
    _,(a,_,target,fens),held=load(database,seed)
    fit_meta=json.loads(fit.read_text())
    if fit_meta["valid_fens_sha256"] != hashlib.sha256("\n".join(fens).encode()).hexdigest():
        raise ValueError("not the same validation split used to select this network")
    if hashlib.sha256(weights.read_bytes()).hexdigest() != fit_meta["net_sha256"]:
        raise ValueError("incorrect exported checkpoint")
    buckets=(((a!=768).sum(1)-2)//4).clamp(0,7)
    def scores(executable):
        rows=ask(executable,"--static-scores",fens)
        if len(rows)!=len(fens) or any(len(x)!=1 for x in rows):
            raise ValueError("incomplete native audit")
        error=(torch.tensor([x[0] for x in rows])-target).abs()
        return dict(mae_cp=error.mean().item(),by_bucket=[
            dict(bucket=i,n=int((buckets==i).sum()),
                 mae_cp=error[buckets==i].mean().item() if (buckets==i).any() else None)
            for i in range(8)])
    return dict(positions=len(fens),held_out=held,teacher=teacher,
                release=scores(release),candidate=scores(candidate),
                release_binary_sha256=hashlib.sha256(release.read_bytes()).hexdigest(),
                candidate_binary_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest())

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("database","release","candidate","weights","fit","report"):
        p.add_argument(name,type=Path)
    arg=p.parse_args()
    torch.set_num_threads(1)
    arg.report.write_text(json.dumps(assess(arg.database,arg.release,arg.candidate,arg.weights,arg.fit),indent=2)+"\n")

"""Paired non-promotion diagnostics; no wall-clock strength decisions."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from .sprt_status import summarize

def run(fastchess,candidate,baseline,book,output,*,rounds,nodes,seed,jobs,blend=None):
    output.mkdir(parents=True,exist_ok=False)
    binary,cand,base,book=(str(v.resolve(strict=True)) for v in (fastchess,candidate,baseline,book))
    args=[binary,"-engine",f"cmd={cand}","name=New"]
    if blend is not None: args.append(f"option.NeuralBlend={blend}")
    args+=["-engine",f"cmd={base}","name=Main","-each","tc=inf",f"nodes={nodes}","option.Threads=1",
           "option.Hash=16","-rounds",str(rounds),"-repeat","-concurrency",str(jobs),"-openings",
           f"file={book}","format=pgn","order=random","plies=8","-srand",str(seed),"-maxmoves","250"]
    path=output/"match.log"
    with path.open("w") as stream:
        subprocess.run(args,cwd=output,stdout=stream,stderr=subprocess.STDOUT,check=True)
    with path.open() as stream:
        report=summarize(stream)
    if report["games"] != rounds*2 or report["faults"]: raise RuntimeError("invalid diagnostic")
    report.update(status="fixed-length diagnostic (not SPRT)",nodes=nodes,seed=seed,blend=blend,
                  candidate_sha256=hashlib.sha256(Path(cand).read_bytes()).hexdigest(),
                  baseline_sha256=hashlib.sha256(Path(base).read_bytes()).hexdigest(),
                  book_sha256=hashlib.sha256(Path(book).read_bytes()).hexdigest())
    (output/"result.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f'{report["wins"]}W {report["draws"]}D {report["losses"]}L',flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("fastchess","candidate","baseline","book","output"):
        p.add_argument(name,type=Path)
    for k,d in (("rounds",32),("nodes",20000),("seed",1701),("jobs",4)):
        p.add_argument("--"+k,type=int,default=d)
    p.add_argument("--blend",type=int,choices=range(101))
    a=p.parse_args()
    if min(a.rounds,a.nodes,a.jobs)<1: p.error("positive budget required")
    run(**vars(a))

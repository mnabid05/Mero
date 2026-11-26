"""Paired fixed-node search throughput, not Elo. Alternate execution order by FEN."""
import argparse
import hashlib
import json
import re
import statistics
import subprocess
from pathlib import Path

FENS=("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
      "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
      "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10")

def probe(exe,fen,nodes):
    cmd=f"uci\nsetoption name Threads value 1\nsetoption name Hash value 16\nposition fen {fen}\ngo nodes {nodes}\n"
    out=subprocess.run([exe],input=cmd,capture_output=True,text=True,check=True,timeout=90).stdout
    match=re.search(r"info depth (\d+) score (cp|mate) (-?\d+) nodes (\d+) nps (\d+).*? time (\d+)",out)
    move=re.search(r"^bestmove (\S+)$",out,re.M)
    if not match or not move: raise ValueError("no complete UCI report")
    d,unit,score,n,nps,ms=match.groups()
    if int(ms)<1 or not 0<int(n)<=nodes: raise ValueError("invalid node/time accounting")
    return dict(depth=int(d),score=[unit,int(score)],bestmove=move[1],nodes=int(n),ms=int(ms),nps=int(nps))

def run(a,b,nodes=240000,rounds=2):
    samples=[]
    for r in range(rounds):
        for i,fen in enumerate(FENS):
            row={"fen":fen}
            for k,exe in ([("baseline",a),("candidate",b)] if (r+i)%2==0 else [("candidate",b),("baseline",a)]):
                row[k]=probe(exe,fen,nodes)
            samples.append(row)
    summary={k:int(1000*sum(x[k]["nodes"] for x in samples)/sum(x[k]["ms"] for x in samples))
             for k in ("baseline","candidate")}
    return dict(binary_sha256={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in
                               (("baseline",a),("candidate",b))},aggregate_nps=summary,
                median_paired_ratio=statistics.median(x["candidate"]["nps"]/x["baseline"]["nps"] for x in samples),
                samples=samples)
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("baseline","candidate","out"): p.add_argument(n,type=Path)
    a=p.parse_args()
    report=run(a.baseline,a.candidate)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print(report["aggregate_nps"], report["median_paired_ratio"])

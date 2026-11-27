"""Paired non-promotion diagnostics; no wall-clock strength decisions."""
import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from .sprt_status import summarize
from chess_ai.board import Board
from chess_ai.backtest import repetition_key

def epd_pair_scores(pgn,positions):
    """Check the positions Fastchess actually played, not just its command line."""
    expected=Counter((repetition_key(Board.from_fen(epd+" 0 5")),side)
                     for epd in positions for side in ("New","Main"))
    if any(n!=1 for n in expected.values()): raise ValueError("duplicate book position")
    observed=Counter(); scores=Counter(); tags={}
    def finish():
        if not tags: return
        if {tags.get("White"),tags.get("Black")}!={"New","Main"} or "FEN" not in tags:
            raise ValueError("missing PGN opponents or opening")
        board=Board.from_fen(tags["FEN"])
        key=repetition_key(board)
        observed[(key,tags["White"])]+=1
        result=tags.get("Result")
        if result not in ("1-0","1/2-1/2","0-1"): raise ValueError("unfinished PGN")
        winner={"1-0":tags["White"],"0-1":tags["Black"],"1/2-1/2":None}[result]
        scores["draws" if winner is None else "wins" if winner=="New" else "losses"]+=1
    with pgn.open() as stream:
        for line in stream:
            m=re.fullmatch(r'\[(\w+) "(.*)"\]',line.strip())
            if m:
                if m[1]=="Event": finish(); tags={}
                tags[m[1]]=m[2]
    finish()
    if observed!=expected: raise ValueError("played PGN openings/colors differ from reserved pairs")
    return {k:scores[k] for k in ("wins","draws","losses")}

def run(fastchess,candidate,baseline,book,output,*,rounds,nodes,seed,jobs,blend=None,fresh=False):
    if fresh:
        from .fresh_openings import verify
        manifest=verify(book,replay=True)
        if manifest["pairs"]!=rounds or manifest["seed"]!=seed:
            raise ValueError("fixed-node diagnostic needs its own complete, fresh book")
    output.mkdir(parents=True,exist_ok=False)
    binary,cand,base,book=(str(v.resolve(strict=True)) for v in (fastchess,candidate,baseline,book))
    args=[binary,"-engine",f"cmd={cand}","name=New"]
    if blend is not None: args.append(f"option.NeuralBlend={blend}")
    args+=["-engine",f"cmd={base}","name=Main","-each","tc=inf",f"nodes={nodes}","option.Threads=1",
           "option.Hash=16","-rounds",str(rounds),"-repeat","-concurrency",str(jobs),"-openings",
           f"file={book}",*(["format=epd","order=sequential"] if fresh else
                            ["format=pgn","order=random","plies=8"]),"-srand",str(seed),"-maxmoves","250"]
    if fresh:
        args+=["-pgnout","file=games.pgn","notation=uci","min=true"]
    path=output/"match.log"
    with path.open("w") as stream:
        subprocess.run(args,cwd=output,stdout=stream,stderr=subprocess.STDOUT,check=True)
    with path.open() as stream:
        report=summarize(stream)
    if report["games"] != rounds*2 or report["faults"]: raise RuntimeError("invalid diagnostic")
    if fresh:
        scores=epd_pair_scores(output/"games.pgn",[row[0] for row in manifest["openings"]])
        if any(report[k]!=v for k,v in scores.items()): raise ValueError("PGN and logged WDL disagree")
        report.update(verified_color_pairs=rounds,
                      games_sha256=hashlib.sha256((output/"games.pgn").read_bytes()).hexdigest())
    report.update(status="fixed-length diagnostic (not SPRT)",nodes=nodes,seed=seed,blend=blend,
                  candidate_sha256=hashlib.sha256(Path(cand).read_bytes()).hexdigest(),
                  baseline_sha256=hashlib.sha256(Path(base).read_bytes()).hexdigest(),
                  book_sha256=hashlib.sha256(Path(book).read_bytes()).hexdigest())
    (output/"result.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f'{report["wins"]}W {report["draws"]}D {report["losses"]}L',flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("fastchess","candidate","baseline","book","output"):
        p.add_argument(name,type=Path)
    for k,d in (("rounds",32),("nodes",20000),("seed",1701),("jobs",4)):
        p.add_argument("--"+k,type=int,default=d)
    p.add_argument("--blend",type=int,choices=range(101))
    p.add_argument("--fresh",action="store_true",help="use a dedicated verified EPD book and check played pairs")
    a=p.parse_args()
    if min(a.rounds,a.nodes,a.jobs)<1: p.error("positive budget required")
    run(**vars(a))

"""Rate a twice-confirmed Mero against the exact historical Stockfish setting, not a human pool."""
import argparse
import json
from pathlib import Path
import signal
import shlex
import subprocess
import sys
import time
from scripts.audit_clocked_pairs import audit
from scripts.scale_campaign import REPO, machine_slot, expect
from scripts.run_sprt import check_power
from scripts.verify_match import verify_report
from training.large_run import atomic, sha

BOOK_HASH="e5b9b354cd9ab3c7e8002373d7a7bb5a07e71fbc93b53621a31cf960821019b8"
SF_HASH="bc0cac905ecdf2147fe22055c733bcd999b1e3f7c399fbaf7fb9055786563590"

def confirmed(first,second,candidate_sha):
    if any(x["decision"]!="H1" or x["sha256"]["candidate"]!=candidate_sha for x in (first,second)):
        raise ValueError("two H1 decisions for the identical executable required")
    if first["sha256"]["book"]==second["sha256"]["book"] or any(
        first["sha256"][k]!=second["sha256"][k] for k in ("baseline","fastchess")):
        raise ValueError("confirmation requires independent openings and the same comparison")
    return True

def validate(report,exe,stockfish):
    if (report["total_games"],report["move_time_ms"],report["candidate_threads"],report["opponent_threads"],
        report["max_plies"])!=(64,100,4,1,400):
        raise ValueError("calibration budgets differ")
    prov=report["provenance"]
    if (prov["hash_mb_per_engine"]!=64 or prov["opening_count"]!=16 or
            prov["candidate"]["executable_sha256"]!=sha(exe) or
            prov["opponent"]["executable_sha256"]!=sha(stockfish) or
            [v["opponent_elo"] for v in report["levels"]]!=[2300]):
        raise ValueError("calibration provenance differs")
    if any("forfeit" in g["reason"].lower() for g in report["games"]):
        raise ValueError("a forfeit invalidates calibration")
    if verify_report(report)!=64: raise ValueError("not 64 legal games")
    return report["estimate"]

def run(build,name,wait=False):
    with machine_slot(build/"mero20m-01",wait=wait):
        check_power()
        work=build/("campaign-"+name)
        exe=work/"native/mwahaha-engine"
        first,second=(audit(build/"scale-results"/label/"sprt") for label in (name,name+"-confirm"))
        confirmed(first,second,sha(exe))
        stockfish=expect(build/"opponents/stockfish/stockfish-macos-m1-apple-silicon",SF_HASH)
        book=expect(REPO/"training/calibration.openings",BOOK_HASH)
        out=work/"external-rating";out.mkdir(exist_ok=False)
        path=out/"games.json"
        args=[sys.executable,"-u","-m","chess_ai.gauntlet","--candidate",shlex.quote(str(exe)),"--opponent",shlex.quote(str(stockfish)),
              "--opponent-elo","2300","--games-per-level","64","--move-time","100","--candidate-threads","4",
              "--opponent-threads","1","--max-plies","400","--opening-book",str(book),"--json-out",str(path)]
        with (out/"calibration.log").open("x") as log:
            proc=subprocess.Popen(args,cwd=REPO,stdout=log,stderr=subprocess.STDOUT)
            try:
                while proc.poll() is None:
                    wall=time.time()
                    try: proc.wait(timeout=5)
                    except subprocess.TimeoutExpired: pass
                    check_power()
                    if not 0<=time.time()-wall<=15: raise RuntimeError("calibration supervision gap")
                if proc.returncode!=0: raise RuntimeError("gauntlet failed")
            except BaseException:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGINT)
                    try: proc.wait(timeout=8)
                    except subprocess.TimeoutExpired: proc.kill();proc.wait()
                raise
        report=json.loads(path.read_text())
        estimate=validate(report,exe,stockfish)
        atomic(out/"verified.json",dict(scope="Stockfish 18 UCI_Elo 2300, same M4 settings and openings as Mero 7; not a human rating",
               estimate=estimate,games_sha256=sha(path),opening_sha256=BOOK_HASH,pairs=report["levels"][0]["paired_uncertainty"]))
        print(json.dumps(estimate))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build",type=Path,default=REPO/"build")
    p.add_argument("--name",choices=["calibrated384"],default="calibrated384")
    p.add_argument("--wait",action="store_true",help="idle until the exclusive slot is free; never rate without two audited H1 decisions")
    a=p.parse_args();run(a.build.resolve(),a.name,a.wait)

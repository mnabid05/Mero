"""Run one isolated, color-paired strength gate. Never merge automatically."""
import argparse
import hashlib
import json
import platform
import re
import signal
import subprocess
from pathlib import Path

from .sprt_status import FAULT, GAME, summarize

def require_mac_power(status):
    if "drawing from 'AC Power'" not in status:
        raise RuntimeError("SPRT needs a sustained AC power source")
    if "InternalBattery" in status:
        percent = re.search(r"(\d+)%", status)
        if not percent or int(percent[1]) < 20 or "discharging" in status.lower():
            raise RuntimeError("wait for at least 20% battery and an AC source that is not discharging")

def check_power():
    if platform.system() == "Darwin":
        require_mac_power(subprocess.check_output(["pmset", "-g", "batt"], text=True, timeout=5))

def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def run(args):
    check_power()
    harness, candidate, baseline, book = (p.resolve(strict=True) for p in
                                           (args.fastchess,args.candidate,args.baseline,args.book))
    if digest(candidate) == digest(baseline):
        raise ValueError("expected different frozen binaries")
    seed=1701
    openings=[f"file={book}","format=pgn","order=random","plies=8"]
    if getattr(args,"fresh",False):
        from .fresh_openings import verify
        manifest=verify(book)
        if manifest["pairs"]!=2000: raise ValueError("need 2000 fresh opening pairs")
        if not getattr(args,"baseline_sha",None) or digest(baseline)!=args.baseline_sha:
            raise ValueError("fresh strength tests require the pinned release executable")
        if getattr(args,"standalone_gate",None):
            gate=json.loads(args.standalone_gate.read_text())
            if gate.get("passed") is not True or digest(candidate)!=gate.get("binary_sha256"):
                raise ValueError("candidate did not pass its pre-registered queen gate")
        seed=manifest["seed"]
        openings=[f"file={book}","format=epd","order=sequential"]
    elif digest(book) != "5835239f88cc2c7511b177c32392a69f3ede21819cf0616f80a7f907cd21d17e":
        raise ValueError("expected the pinned 8moves_v3 PGN")
    dest = args.output.resolve()
    dest.mkdir(parents=True, exist_ok=False)  # Never resume contaminated statistics.
    command = [str(harness), "-engine", f"cmd={candidate}", "name=New", "-engine",
               f"cmd={baseline}", "name=Main", "-each", "tc=8+0.08", "option.Threads=1",
               "option.Hash=16", "-rounds", "2000", "-repeat", "-concurrency", str(args.jobs),
               "-openings", *openings,
               "-srand", str(seed), "-sprt", "elo0=0", "elo1=10", "alpha=0.05", "beta=0.05",
               "model=normalized", "-ratinginterval", "8", "-recover"]
    metadata = dict(command=command, sha256={n:digest(p) for n,p in
                    zip(("fastchess","candidate","baseline","book"),(harness,candidate,baseline,book))})
    (dest/"inputs.json").write_text(json.dumps(metadata,indent=2)+"\n")
    path = dest/"match.log"
    interrupted = None
    with path.open("w") as out, path.open() as reader:
        child = subprocess.Popen(command,cwd=dest,stdout=out,stderr=subprocess.STDOUT)
        # Bound the idle-sleep assertion to this match only, never global
        # settings. Lid closure is still possible; recheck power/faults.
        awake = None
        try:
            if platform.system()=="Darwin":
                awake=subprocess.Popen(["/usr/bin/caffeinate","-i","-w",str(child.pid)])
            while child.poll() is None:
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    check_power()
                    for line in reader:
                        game = GAME.match(line.strip())
                        if game and FAULT.search(game[5]):
                            raise RuntimeError("clock or engine fault: " + line.strip())
        except (KeyboardInterrupt, RuntimeError, OSError, subprocess.SubprocessError) as error:
            interrupted = str(error) or "operator interrupt"
            if child.poll() is None:
                child.send_signal(signal.SIGINT)
        finally:
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            if awake is not None:
                awake.terminate()
                awake.wait(timeout=5)
    with path.open() as stream:
        result = summarize(stream)
    result.update(returncode=child.returncode, interrupted=interrupted)
    if interrupted or child.returncode:
        result["status"] = "invalid: interrupted or failed"
    (dest/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return 0 if result["status"] == "H1" else 1

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("fastchess","candidate","baseline","book","output"):
        p.add_argument(arg,type=Path)
    p.add_argument("--jobs",type=int,choices=range(1,65),default=4)
    p.add_argument("--fresh",action="store_true",help="require a checksummed 2,000-pair disjoint eight-ply EPD")
    p.add_argument("--baseline-sha",help="frozen release executable digest (mandatory with --fresh)")
    p.add_argument("--standalone-gate",type=Path,help="qualification report bound to this NNUE executable")
    raise SystemExit(run(p.parse_args()))

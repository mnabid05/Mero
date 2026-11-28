"""Independently reconcile a completed Fastchess trial's actual settings and color pairs."""
from pathlib import Path
import argparse
import json
import re
from scripts.sprt_status import GAME, summarize
from training.large_run import sha

PENTA = re.compile(r"^Ptnml\(0-2\): \[([\d, ]+)\]")

def paired_results(lines):
    games = {}
    reported = None
    for raw in lines:
        line = raw.strip()
        if m := GAME.match(line):
            i,white,black,result,_ = m.groups()
            i = int(i)
            if i < 1 or i in games or (white,black) != (("New","Main") if i%2 else ("Main","New")):
                raise ValueError(f"invalid colors or duplicate game ID: {i}")
            side = {"1-0":2,"1/2-1/2":1,"0-1":0}[result]
            games[i] = side if white=="New" else 2-side
        if m := PENTA.match(line):
            reported = [int(x) for x in m[1].split(",")]
    observed = [0]*5
    colors = {s:[0,0,0] for s in ("white","black")}  # loss, draw, win
    for i,score in games.items():
        colors["white" if i%2 else "black"][score] += 1
        if (i+1 if i%2 else i-1) not in games: raise ValueError(f"unpaired game: {i}")
        if i%2: observed[score+games[i+1]] += 1
    if not games or reported != observed:
        raise ValueError(f"pentanomial disagreement: log {reported}, independently reconstructed {observed}")
    return dict(pairs=sum(observed),pentanomial=observed,candidate_loss_draw_win_by_color=colors)

def audit(path):
    report=json.loads((path/"result.json").read_text())
    config=json.loads((path/"config.json").read_text())
    metadata=json.loads((path/"inputs.json").read_text())
    if report["returncode"]!=0 or report["interrupted"] or report["status"] not in ("H0","H1","inconclusive"):
        raise ValueError("not a clean completed match")
    with (path/"match.log").open() as stream: parsed=summarize(stream)
    if any(report[k]!=v for k,v in parsed.items()) or parsed["faults"]: raise ValueError("log and result disagree")
    with (path/"match.log").open() as stream: pairs=paired_results(stream)
    if config["sprt"]!={"alpha":0.05,"beta":0.05,"elo0":0.0,"elo1":10.0,"model":"normalized","enabled":True}:
        raise ValueError("not the registered SPRT")
    if (config["noswap"] or config["reverse"] or (config["games"],config["rounds"],config["concurrency"])!=(2,2000,4)
            or any(config[k]["enabled"] for k in ("resign","draw","tb_adjudication","maxmoves"))):
        raise ValueError("not the registered paired tournament")
    fingerprints=metadata["sha256"]
    engines=config["engines"]
    if len(engines)!=2: raise ValueError("expected exactly two engines")
    for e,key,name in zip(engines,("candidate","baseline"),("New","Main"),strict=True):
        limit=e["limit"]
        if (e["name"]!=name or sha(Path(e["cmd"]))!=fingerprints[key]
                or dict(e["options"])!={"Threads":"1","Hash":"16"}
                or (limit["tc"]["time"],limit["tc"]["increment"],limit["tc"]["fixed_time"],limit["nodes"],limit["plies"])!=(8000,80,0,0,0)):
            raise ValueError("different binary, clock or engine options")
    opening=config["opening"]
    if (opening["format"],opening["order"],opening["start"])!=(0,1,1):
        raise ValueError("not the registered sequential EPD book order")
    book=Path(opening["file"])
    if sha(book)!=fingerprints["book"] or sha(Path(metadata["command"][0]))!=fingerprints["fastchess"]:
        raise ValueError("changed harness or book")
    pins=json.loads((Path(__file__).resolve().parents[1]/"backtests/scale-campaign-inputs.json").read_text())
    retry=json.loads((Path(__file__).resolve().parents[1]/"backtests/scale-lmr-fresh-retry.json").read_text())
    specs=[*pins["books"].values(),retry["book"]]
    if (fingerprints["fastchess"]!=pins["fastchess_sha256"] or fingerprints["baseline"]!=pins["release_sha256"]
            or (fingerprints["book"],config["seed"]) not in {(v["sha256"],v["seed"]) for v in specs}):
        raise ValueError("not a pre-registered harness, control, book or seed")
    if pairs["pairs"]*2!=report["games"]: raise ValueError("incomplete pairing")
    return dict(**pairs, decision=report["status"], games=report["games"],llr=report["reported_llr"],
                sha256=fingerprints,config_sha256=sha(path/"config.json"),log_sha256=sha(path/"match.log"))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("trial",type=Path)
    print(json.dumps(audit(p.parse_args().trial),indent=2))

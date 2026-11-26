"""Run the frozen M4 campaign in stages. Never promote, push, or reuse interrupted games."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from scripts import run_sprt
from scripts.fresh_openings import verify
from scripts.paired_speed import run as speed
from scripts.scale_bench import bench
from scripts.sprt_status import summarize
from training.large_run import atomic, sha
from training.probe_material import PANEL_HASH

REPO = Path(__file__).resolve().parents[1]
PINS = json.loads((REPO/"backtests/scale-campaign-inputs.json").read_text())
RECIPES = {"net256": (256,0.625), "net384": (384,0.5)}
TARGET = 20_000_000


def expect(path, fingerprint):
    if not path.is_file() or sha(path) != fingerprint:
        raise ValueError(f"missing or changed campaign input: {path}")
    return path


@contextmanager
def machine_slot(corpus,wait=False):
    """Use the generator's exact advisory lock for every CPU/GPU/clocked stage."""
    with (corpus/".generator.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|(0 if wait else fcntl.LOCK_NB))
        except BlockingIOError as e:
            raise RuntimeError("datagen or another campaign stage is active") from e
        yield


def load_data(build):
    corpus=build/"mero20m-01"
    config=json.loads((corpus/"campaign.json").read_text())
    if config != dict(schema=1,producer=PINS["teacher_sha256"],seed=2026112601,
                      games_per_shard=256,nodes=5000,source="Mero 7"):
        raise ValueError("unexpected production corpus")
    progress=json.loads((corpus/"progress.json").read_text())
    if progress["quiet_positions"] < TARGET:
        raise ValueError(f"sealed {progress['quiet_positions']:,} / {TARGET:,} quiet positions")
    return corpus


def prepare(build):
    from training.large_split import split
    corpus=load_data(build)
    dest=build/"mero20m-split"
    if not dest.exists():
        split(corpus,dest)
    info=json.loads((dest/"split.json").read_text())
    if (info.get("schema")!=2 or info.get("panel_sha256")!=PANEL_HASH or
            info["source_config"]!=json.loads((corpus/"campaign.json").read_text()) or
            info["source_positions"]<TARGET or info["groups"]["train"]["positions"]<10_000_000):
        raise ValueError("insufficient or mismatched frozen split")
    for name in ("train","valid"):
        group=info["groups"][name]
        path=expect(dest/(name+".bullet"),group["sha256"])
        if path.stat().st_size != 32*group["positions"]:
            raise ValueError("record size mismatch")
    return dest


def call(*argv):
    subprocess.run(list(map(str,argv)),cwd=REPO,check=True)


def artifact(command, final_file):
    # A failed/partial stage is preserved; the underlying commands never
    # overwrite existing checkpoint, selected-network or split directories.
    if not final_file.exists():
        call(*command)
    if not final_file.is_file():
        raise RuntimeError(f"stage did not produce {final_file}")


def fit(build,name):
    run_sprt.check_power()
    data=prepare(build)
    width,wdl=RECIPES[name]
    trainer=expect(build/"bullet-scale-fit/release/mero-bullet-fit",PINS["metal_trainer_sha256"])
    work=build/("campaign-"+name)
    work.mkdir(exist_ok=True)
    checkpoints,selected=work/"fit",work/"selected"
    # Specify the recipe explicitly: the historical pilot mode is not used.
    artifact([trainer,data/"train.bullet",checkpoints,"12",REPO/"training/bullet-probes.fen",width,wdl],
             checkpoints/"final-float-parity.tsv")
    recipe=json.loads((checkpoints/"recipe.json").read_text())
    if (recipe["width"],recipe["wdl_weight"],recipe["superbatches"])!=(width,wdl,12):
        raise ValueError("existing fit is a different experiment")
    artifact([sys.executable,"-m","training.import_bullet",checkpoints,data,selected,"--backend","Metal"],selected/"report.json")
    binaries=[]
    for directory,flag in (("native","--native-arch"),("scalar","--scalar-only")):
        binary=work/directory/"mwahaha-engine"
        artifact([sys.executable,"scripts/build_native.py",flag,"--screlu",selected/"weights.bin",
                  "--output-dir",binary.parent],binary)
        binaries.append(binary)
    parity=work/"parity.json"
    call(sys.executable,"-m","training.audit_screlu",selected/"weights.bin",*binaries,"--report",parity)
    # Always recompute the queen gate; no retry or cp multiplier on failure.
    call(sys.executable,"-m","training.qualify_standalone",selected,data,binaries[0],parity,
         REPO/"training/data/selfplay-pilot-v1/positions.bullet",work/"queen.json")
    return binaries[0],work/"queen.json"


def inputs(build,name):
    harness=expect(build/"tools/fastchess/fastchess",PINS["fastchess_sha256"])
    control=expect(build/"phase1-baseline/mwahaha-engine",PINS["release_sha256"])
    book=expect(build/"scale-openings"/(name+".epd"),PINS["books"][name]["sha256"])
    info=verify(book)
    if (info["seed"]!=PINS["books"][name]["seed"] or info["pairs"]!=2000 or
            info["control_sha256"]!=PINS["teacher_sha256"]):
        raise ValueError("book provenance mismatch")
    return harness,control,book


def match(build,name,binary,gate=None):
    run_sprt.check_power()
    harness,baseline,book=inputs(build,name)
    work=build/"scale-results"/name
    work.mkdir(parents=True,exist_ok=True)
    if gate is not None:
        data=json.loads(gate.read_text())
        if not data["passed"] or data["binary_sha256"]!=sha(binary):
            raise ValueError("missing gate for this exact binary")
    elif name not in PINS["candidates"]:
        raise ValueError("standalone candidates require a queen qualification")
    report=work/"bench.json"
    if not report.exists():
        atomic(report,bench(binary))
    validation=json.loads(report.read_text())
    if validation["binary_sha256"]!=sha(binary) or validation["depth"]!=12 or len(validation["positions"])!=40:
        raise ValueError("invalid bench record")
    timing=work/"speed.json"
    if not timing.exists():
        atomic(timing,speed(baseline,binary))
    hashes={"fastchess":sha(harness),"candidate":sha(binary),"baseline":sha(baseline),"book":sha(book)}
    if json.loads(timing.read_text())["binary_sha256"]!={k:hashes[k] for k in ("candidate","baseline")}:
        raise ValueError("speed samples belong to different binaries")
    dest=work/"sprt"
    if not dest.exists():
        run_sprt.run(SimpleNamespace(fastchess=harness,candidate=binary,baseline=baseline,book=book,
                     output=dest,jobs=4,fresh=True,baseline_sha=sha(baseline),standalone_gate=gate))
    if json.loads((dest/"inputs.json").read_text())["sha256"]!=hashes:
        raise ValueError("match inputs changed")
    result=json.loads((dest/"result.json").read_text())
    with (dest/"match.log").open() as lines:
        verified=summarize(lines)
    if (result["status"] not in ("H0","H1","inconclusive") or result["interrupted"] or
            result["returncode"]!=0 or any(result[k]!=v for k,v in verified.items())):
        raise ValueError(f"no valid finished match for {name}; preserve evidence, use a fresh book for a retry")
    return result["status"]


def search(build):
    for name, spec in PINS["candidates"].items():
        candidate=expect(build/f"scale-search-{name}"/"mero",spec["sha256"])
        print(f"{name}: {match(build,name,candidate)}",flush=True)


def networks(build):
    for name in RECIPES:
        try:
            binary,gate=fit(build,name)
        except subprocess.CalledProcessError as e:
            q=build/("campaign-"+name)/"queen.json"
            failed=e.returncode==3 and "training.qualify_standalone" in list(map(str,e.cmd))
            if not (failed and q.exists() and json.loads(q.read_text()).get("passed") is False):
                raise
            print(f"{name}: failed queen gate; no games",flush=True)
            continue
        if match(build,name,binary,gate)=="H1":
            result=match(build,"confirmation",binary,gate)
            if result=="H1":
                print(f"{name}: two H1 decisions. Ready for release review; main unchanged.",flush=True)
                return True
            # This confirmation book has been consumed; never reuse it for another binary.
            print(f"{name}: confirmation {result}. Register another confirmation before further tests.",flush=True)
            return False
    print("Neither recipe qualified and won; collect new evidence before running another hypothesis.",flush=True)
    return False


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=["prepare","networks","search","follow"],
                   help="follow waits for the running generator, then runs networks and search; never merges")
    p.add_argument("--build",type=Path,default=REPO/"build")
    args=p.parse_args()
    b=args.build.resolve()
    if args.stage=="follow":
        print("Waiting for the generator to release its exclusive machine slot.",flush=True)
    with machine_slot(b/"mero20m-01",wait=args.stage=="follow"):
        if args.stage=="prepare":
            print(prepare(b))
        elif args.stage=="follow":
            load_data(b)  # A power stop or incomplete generator is not a finished corpus.
            run_sprt.check_power()
            won=networks(b)
            search(b)
            return 0 if won else 1
        elif args.stage=="networks":
            return 0 if networks(b) else 1
        else:
            search(b)
    return 0


if __name__=="__main__":
    raise SystemExit(main())

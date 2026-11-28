"""Run the frozen M4 campaign in stages. Never promote, push, or reuse interrupted games."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from scripts import run_sprt
from scripts.fresh_openings import verify
from scripts.paired_speed import run as speed
from scripts.scale_bench import bench
from scripts.sprt_status import summarize
from training.large_run import atomic, sha, await_power, generate
from training.probe_material import PANEL_HASH
from training.opening_holdout import POLICY,book_hashes

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
    holdout=info.get("opening_holdout",{})
    if holdout.get("policy")!=POLICY or holdout.get("book_sha256")!=book_hashes():
        raise ValueError("missing frozen match-opening holdouts")
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


def fit(build,name,*,calibrated=None):
    run_sprt.check_power()
    data=prepare(build)
    if calibrated is None:
        width,wdl=RECIPES[name]
        trainer=expect(build/"bullet-scale-fit/release/mero-bullet-fit",PINS["metal_trainer_sha256"])
        extra=[]
    else:
        from training.outcome_temperature import measure
        computed=measure(data)
        if (computed["split"]!=calibrated["calibration"]["split"] or
                abs(computed["temperature_cp"]-calibrated["calibration"]["temperature_cp"])>1e-6 or
                name!=calibrated["name"] or calibrated["superbatches"]!=12):
            raise ValueError("different corpus, calibration, or registered recipe")
        width,wdl=calibrated["width"],calibrated["wdl_weight"]
        trainer=expect(build/"bullet-calibrated-fit/release/mero-bullet-fit",calibrated["trainer_sha256"])
        extra=[computed["temperature_cp"]]
    work=build/("campaign-"+name)
    work.mkdir(exist_ok=True)
    checkpoints,selected=work/"fit",work/"selected"
    # Specify the recipe explicitly: the historical pilot mode is not used.
    artifact([trainer,data/"train.bullet",checkpoints,"12",REPO/"training/bullet-probes.fen",width,wdl,*extra],
             checkpoints/"final-float-parity.tsv")
    recipe=json.loads((checkpoints/"recipe.json").read_text())
    if (recipe["width"],recipe["wdl_weight"],recipe["superbatches"])!=(width,wdl,12):
        raise ValueError("existing fit is a different experiment")
    if abs(recipe.get("wdl_temperature_cp",400)-(extra[0] if extra else 400))>1e-4:
        raise ValueError("existing fit used a different probability link")
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
    spec=PINS["books"].get(name)
    if spec is None:
        retry=json.loads((REPO/"backtests/scale-lmr-fresh-retry.json").read_text())
        if name!=retry["name"]: raise ValueError("unknown opening reservation")
        spec=retry["book"]
    book=expect(build/"scale-openings"/(name+".epd"),spec["sha256"])
    info=verify(book)
    if (info["seed"]!=spec["seed"] or info["pairs"]!=2000 or
            info["control_sha256"]!=PINS["teacher_sha256"]):
        raise ValueError("book provenance mismatch")
    return harness,control,book


def ensure_exclusive_book(work,book):
    # Assigning an unused protected book is safe; old games are never fresh.
    fingerprint=sha(book)
    for other in work.parent.glob("*/sprt"):
        if other.parent==work: continue
        inp=json.loads((other/"inputs.json").read_text())
        if inp["sha256"]["book"]==fingerprint: raise ValueError("opening set has already been played")


def match(build,name,binary,gate=None,*,book_name=None,search_name=None):
    run_sprt.check_power()
    harness,baseline,book=inputs(build,book_name or name)
    work=build/"scale-results"/name
    ensure_exclusive_book(work,book)
    work.mkdir(parents=True,exist_ok=True)
    if gate is not None:
        data=json.loads(gate.read_text())
        if not data["passed"] or data["binary_sha256"]!=sha(binary):
            raise ValueError("missing gate for this exact binary")
    elif (spec:=PINS["candidates"].get(search_name or name)) is None or sha(binary)!=spec["sha256"]:
        raise ValueError("only the frozen search binaries are exempt from neural qualification")
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
    deferred=None
    for name, spec in PINS["candidates"].items():
        candidate=expect(build/f"scale-search-{name}"/"mero",spec["sha256"])
        old=build/"scale-results"/name/"sprt"
        if name=="lmr" and (old/"result.json").exists() and json.loads((old/"result.json").read_text())["status"].startswith("invalid"):
            retry=json.loads((REPO/"backtests/scale-lmr-fresh-retry.json").read_text())
            expect(old/"result.json",retry["invalid_result_sha256"]);expect(old/"match.log",retry["invalid_log_sha256"])
            deferred=(retry["name"],candidate)
            print("lmr: original trial invalid. Fresh retry scheduled after untouched search tests.",flush=True)
            continue
        print(f"{name}: {match(build,name,candidate)}",flush=True)
    if deferred:
        retry,exe=deferred
        print(f"{retry}: {match(build,retry,exe,book_name=retry,search_name='lmr')}",flush=True)


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


def calibrated_round(build,wide=False):
    planfile="scale-outcome-link-384-plan.json" if wide else "scale-outcome-link-plan.json"
    plan=json.loads((REPO/"backtests"/planfile).read_text())
    if wide:
        gate=json.loads((build/"campaign-calibrated256"/"queen.json").read_text())
        if gate["passed"] is not False or gate["weights_sha256"]!="e5f5e113d957eadfe4d0f506697c137c1932e3ea8e6a31ba06b7d5f4dd9ab384":
            raise ValueError("missing rejected calibrated-256 fingerprint")
        panel=expect(build/"scale-tools/second-queen-panel.json",plan["extra_queen_panel"]["sha256"])
    reference=expect(build/"phase1-baseline/mwahaha-engine",PINS["release_sha256"])
    original=json.loads((REPO/"backtests/scale-first-two-fits.json").read_text())
    for old in RECIPES:
        work=build/("campaign-"+old)
        gate=json.loads((work/"queen.json").read_text())
        exe=expect(work/"native/mwahaha-engine",original["networks"][old]["qualification"]["binary_sha256"])
        if (gate["passed"] is not False or gate["binary_sha256"]!=sha(exe)
                or gate!=original["networks"][old]["qualification"]
                or (build/"scale-results"/old/"sprt").exists()):
            raise ValueError("registered handoff requires both old candidates to have failed before playing")
        if not (work/"rejected-speed.json").exists():
            atomic(work/"rejected-speed.json",speed(reference,exe))
    name=plan["name"]
    try:
        binary,gate=fit(build,name,calibrated=plan)
    except subprocess.CalledProcessError as e:
        q=build/("campaign-"+name)/"queen.json"
        if (e.returncode!=3 or "training.qualify_standalone" not in list(map(str,e.cmd))
                or not q.exists() or json.loads(q.read_text())["passed"] is not False): raise
        print(f"{name}: failed queen gate; no games",flush=True)
        return False
    if wide:
        from training.blind_queen_panel import assess
        extra=assess(panel,plan["extra_queen_panel"]["sha256"],binary)
        atomic(build/("campaign-"+name)/"supplementary-queen.json",extra)
        if not extra["passed"]:
            print(f"{name}: failed supplementary queen gate; no matches",flush=True)
            return False
    if match(build,name,binary,gate,book_name=plan["first_book"])!="H1": return False
    return match(build,name+"-confirm",binary,gate,book_name=plan["confirmation_book"])=="H1"


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=["prepare","networks","search","follow","run","calibrated-follow","wide-follow"],
                   help="run resumes datagen, networks, and search; follow attaches to an existing generator")
    p.add_argument("--build",type=Path,default=REPO/"build")
    args=p.parse_args()
    b=args.build.resolve()
    if args.stage=="run":
        producer=expect(b/"producer-v2/mwahaha-engine",PINS["teacher_sha256"])
        generate(producer,b/"mero20m-01",target=TARGET,games_per_shard=256,
                 workers=os.cpu_count() or 1,seed=2026112601,wait_power=True)
    if args.stage in ("follow","calibrated-follow","wide-follow"):
        print("Waiting for the exclusive campaign slot; no training or matches while queued.",flush=True)
    with machine_slot(b/"mero20m-01",wait=args.stage in ("follow","calibrated-follow","wide-follow")):
        if args.stage=="prepare":
            print(prepare(b))
        elif args.stage in ("run","follow"):
            load_data(b)  # A power stop or incomplete generator is not a finished corpus.
            await_power(b/"mero20m-01",wait=True,clocked=True)
            won=networks(b)
            search(b)
            return 0 if won else 1
        elif args.stage in ("calibrated-follow","wide-follow"):
            await_power(b/"mero20m-01",wait=True,clocked=True)
            won=calibrated_round(b,wide=args.stage=="wide-follow")
            search(b)  # resumable; no completed or interrupted SPRT is replayed
            return 0 if won else 1
        elif args.stage=="networks":
            return 0 if networks(b) else 1
        else:
            search(b)
    return 0


if __name__=="__main__":
    raise SystemExit(main())

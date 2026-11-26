"""Fail closed before playing an experimental standalone NNUE against the release."""
import argparse
import json
from pathlib import Path
from .large_run import sha,atomic
from .probe_material import probe
from .screlu_wire import STANDALONE_MAGIC,width_of,unpack

def gate(selected,split,engine,audit,panel,report):
    weights=selected/"weights.bin"
    blob=weights.read_bytes()
    if blob[:8]!=STANDALONE_MAGIC: raise ValueError("not a strict standalone network")
    unpack(blob)
    fit=json.loads((selected/"report.json").read_text())
    meta=json.loads((split/"split.json").read_text())
    width=width_of(blob)
    if (fit["net_sha256"]!=sha(weights) or fit["split"]!=meta or fit["recipe"]["width"]!=width
            or not 0.5<=fit["recipe"]["wdl_weight"]<=0.75 or width not in (256,384) or
            fit["recipe"]["train_rows"]!=meta["groups"]["train"]["positions"] or
            fit["recipe"]["train_rows"]<10_000_000):
        raise ValueError("unqualified training provenance")
    parity=json.loads(audit.read_text())
    if (parity.get("binary_sha256")!=sha(engine) or parity.get("weights_sha256")!=sha(weights)
            or parity.get("integer_mismatches")!=0 or parity.get("material_buckets")!=8
            or parity.get("kernels",0)<2 or len(set(parity.get("kernel_sha256",[])))<2):
        raise ValueError("missing scalar/native and strict static evaluation parity")
    if sha(panel)!="2e2a7a2d208eddb1a89d0c5f7ca34022a39795b5d696b86bdd319bc6cc6e9d8e":
        raise ValueError("use the pre-registered pilot panel; do not choose positions after looking at results")
    result=probe(panel,[("candidate",engine)])
    queens=result["engines"]["candidate"]["by_piece"]["Q"]
    passed=queens["n"]>=150 and 850<=queens["median_cp"]<=1000
    atomic(report,dict(passed=passed,queen=queens,weights_sha256=sha(weights),binary_sha256=sha(engine),
                       diagnostics=result))
    if not passed: raise ValueError(f"queen-removal gate failed: {queens}")
    return True

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("selected","split","engine","audit","panel","report"): p.add_argument(key,type=Path)
    gate(**vars(p.parse_args()))

"""Check the compiled SIMD/scalar kernel against immutable integer Torch scores."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

def verify(binary, weights, fixture):
    data=json.loads(fixture.read_text())
    if hashlib.sha256(weights.read_bytes()).hexdigest()!=data["sha256"]:
        raise ValueError("fixture was generated for other network weights")
    for mode,rows in (("--screlu-scores",data["positions"]),("--screlu-trace",data["paths"])):
        probe=subprocess.run([str(binary.resolve()),mode],input="\n".join(x for x,_ in rows)+"\n",
                             text=True,capture_output=True,check=True,timeout=30)
        actual=[list(map(int,x.split())) for x in probe.stdout.splitlines()]
        expected=[y if isinstance(y,list) else [y] for _,y in rows]
        if actual!=expected: raise ValueError(f"{mode}: native/reference mismatch")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("binary",type=Path)
    p.add_argument("--weights",type=Path,default=Path("training/checkpoints/mero-bounded512.bin"))
    p.add_argument("--fixture",type=Path,default=Path("tests/screlu_golden.json"))
    args=p.parse_args()
    verify(args.binary,args.weights,args.fixture)
    print("Exact integer parity verified")

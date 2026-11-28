"""Check the compiled SIMD/scalar kernel against immutable integer Torch scores."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

def verify(binary, weights, fixture):
    data=json.loads(fixture.read_text())
    blob=weights.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=data["sha256"]:
        raise ValueError("fixture was generated for other network weights")
    checks=[("--screlu-scores",data["positions"]),("--screlu-trace",data["paths"])]
    if blob[:8]==b"MRSCNET2":
        checks.append(("--static-scores",[(fen,max(-50000,min(50000,cp))) for fen,cp in data["positions"]]))
    for mode,rows in checks:
        probe=subprocess.run([str(binary.resolve()),mode],input="\n".join(x for x,_ in rows)+"\n",
                             text=True,capture_output=True,check=True,timeout=30)
        actual=[list(map(int,x.split())) for x in probe.stdout.splitlines()]
        expected=[y if isinstance(y,list) else [y] for _,y in rows]
        if actual!=expected: raise ValueError(f"{mode}: native/reference mismatch")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("binary",type=Path)
    p.add_argument("--weights",type=Path,default=Path("training/checkpoints/mero-8.bin"))
    p.add_argument("--fixture",type=Path,default=Path("tests/mero8_golden.json"))
    args=p.parse_args()
    verify(args.binary,args.weights,args.fixture)
    print("Exact integer parity verified")

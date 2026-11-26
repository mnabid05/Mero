"""Summarize one fitted network, including native parity and corpus identity."""
import argparse
import hashlib
import json
from pathlib import Path

from .fingerprint import describe
from .parity import check

def audit(database, fit_dir, binary, header):
    fit = json.loads((fit_dir / "training.json").read_text())
    checkpoint = fit_dir / "best.pt"
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    return {
        "corpus": describe(database),
        "training": fit,
        "artifacts": {name: digest(path) for name, path in
                      [("checkpoint", checkpoint), ("header", header), ("engine", binary)]},
        "quantized_residual_vs_float": check(checkpoint, binary, database),
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("database", "fit_dir", "binary", "header", "out"):
        p.add_argument(name, type=Path)
    args = p.parse_args()
    report = audit(args.database, args.fit_dir, args.binary, args.header)
    args.out.write_text(json.dumps(report, indent=2) + "\n")

if __name__ == "__main__":
    main()

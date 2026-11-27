"""Recover missing bytes by deterministic replay; never replace existing evidence."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from .large_run import check_shard, sha, shard_seed
from .power_source import check

FILES = ("COMPLETE.json", "games.tsv", "positions.bullet")

def restore_verified(shard, rebuilt):
    hashes = json.loads((shard/"verified.json").read_text())
    if set(hashes) != set(FILES) or any(not re.fullmatch("[a-f0-9]{64}", h) for h in hashes.values()):
        raise ValueError("original seal is missing or malformed")
    missing = []
    for name in FILES:
        dest = shard/name
        if sha(rebuilt/name) != hashes[name]:
            raise ValueError(f"regeneration differs from original seal: {name}")
        if dest.is_symlink() or (dest.exists() and (not dest.is_file() or sha(dest) != hashes[name])):
            raise ValueError(f"existing evidence differs: {name}")
        if not dest.exists():
            missing.append(name)
    # Validate all files first. link() cannot clobber even if another writer races.
    # Publish COMPLETE last. Interruptions leave an idempotently repairable shard.
    for name in sorted(missing, key=lambda n: n == "COMPLETE.json"):
        os.link(rebuilt/name, shard/name)
    return missing

def recover(root, binary, index, workers):
    if not 0 <= index <= 999999 or workers < 1:
        raise ValueError("invalid shard/worker count")
    with (root/".generator.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        check()
        cfg = json.loads((root/"campaign.json").read_text())
        if cfg["source"] != "Mero 7" or cfg["producer"] != sha(binary) or cfg["nodes"] != 5000:
            raise ValueError("wrong teacher or search budget")
        shard = root/f"shard-{index:06d}"
        if not (shard/"verified.json").is_file():
            raise ValueError("refusing to recreate a seal")
        with tempfile.TemporaryDirectory(dir=root.parent, prefix=".verify-regeneration-") as tmp:
            out = Path(tmp)/"out"
            subprocess.run([binary.resolve(), "datagen", out, str(cfg["games_per_shard"]), "5000",
                            str(workers), str(shard_seed(cfg["seed"], index)), "mero7"], check=True)
            check_shard(out, cfg, index)
            restored = restore_verified(shard, out)
            count = check_shard(shard, cfg, index, hashes=True)
    return dict(shard=index, restored=restored, positions=count, original_seal_sha256=sha(shard/"verified.json"))

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("binary", type=Path)
    p.add_argument("index", type=int)
    p.add_argument("original_workers", type=int)
    args=p.parse_args()
    print(json.dumps(recover(args.root,args.binary,args.index,args.original_workers), indent=2))

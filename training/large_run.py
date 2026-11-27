"""Generate a resumable, hash-pinned Mero 7 corpus. A partial shard never counts."""
import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from .power_source import check as power, PowerUnavailable

def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def atomic(path, data):
    with tempfile.NamedTemporaryFile("w",dir=path.parent,delete=False) as f:
        json.dump(data,f,indent=2)
        f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(f.name,path)

def shard_seed(seed,i):
    return int.from_bytes(hashlib.sha256(f"mero7-corpus-v2:{seed}:{i}".encode()).digest()[:8],"little")

def await_power(root,wait,clocked=False):
    message=None
    while True:
        try:
            power(clocked=clocked)
            if message is not None or (root/"power-state.json").exists():
                if message is not None:
                    print("Power restored; continuing.",flush=True)
                state=root/"power-state.json"
                if not state.is_file() or json.loads(state.read_text()).get("state")!="available":
                    atomic(state,dict(state="available"))
            return
        except PowerUnavailable as error:
            if not wait: raise
            if str(error)!=message:
                message=str(error)
                atomic(root/"power-state.json",dict(state="waiting_for_power",reason=message))
                print(f"Waiting for usable AC: {message}. No self-play or training is running.",flush=True)
            time.sleep(30)

def check_shard(path,config,i,hashes=False):
    manifest=json.loads((path/"COMPLETE.json").read_text())
    expected=dict(games=config["games_per_shard"],nodes=config["nodes"],seed=shard_seed(config["seed"],i),
                  opening_plies=8,mode="mero7",format="bulletformat-chessboard-v1")
    if any(manifest[k]!=v for k,v in expected.items()): raise ValueError(f"shard provenance mismatch: {path}")
    count=manifest["positions"]
    if count<=0 or (path/"positions.bullet").stat().st_size!=32*count or not (path/"games.tsv").is_file():
        raise ValueError(f"incomplete binary/ledger: {path}")
    if hashes:
        verified=json.loads((path/"verified.json").read_text())
        if verified!={p:sha(path/p) for p in ("positions.bullet","games.tsv","COMPLETE.json")}:
            raise ValueError(f"checksum mismatch: {path}")
    return count

def generate(binary,root,*,target,games_per_shard,workers,seed,wait_power=False):
    binary=binary.resolve(strict=True); root.mkdir(parents=True,exist_ok=True)
    with (root/".generator.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        cfg=dict(schema=1,producer=sha(binary),seed=seed,games_per_shard=games_per_shard,nodes=5000,source="Mero 7")
        cfgpath=root/"campaign.json"
        if cfgpath.exists():
            if json.loads(cfgpath.read_text())!=cfg: raise ValueError("refusing to mix different producer, seed or limits")
        else: atomic(cfgpath,cfg)
        total=i=0
        shards=sorted(root.glob("shard-[0-9][0-9][0-9][0-9][0-9][0-9]"))
        for i,path in enumerate(shards):
            if path.name!=f"shard-{i:06d}": raise ValueError("non-contiguous sealed shards")
            total+=check_shard(path,cfg,i,hashes=True)
        i=len(shards)
        active_seconds=0.; initial=total
        while total<target:
            await_power(root,wait_power)
            start=time.monotonic()
            if shutil.disk_usage(root).free < 2*1024**3: raise RuntimeError("less than 2 GiB free")
            # A killed writer can leave a private attempt behind; never overwrite or count it.
            attempt=Path(tempfile.mkdtemp(prefix=f".attempt-{i:06d}-",dir=root))
            path=attempt/"out"
            subprocess.run([binary,"datagen",path,str(games_per_shard),"5000",str(workers),
                str(shard_seed(seed,i)),"mero7"],check=True,stdout=subprocess.DEVNULL)
            count=check_shard(path,cfg,i)
            atomic(path/"verified.json",{p:sha(path/p) for p in ("positions.bullet","games.tsv","COMPLETE.json")})
            path.rename(root/f"shard-{i:06d}"); attempt.rmdir()
            total+=count; i+=1
            active_seconds+=time.monotonic()-start
            rate=(total-initial)/max(active_seconds,0.001)
            progress=dict(quiet_positions=total,sealed_shards=i,target=target,
                rate_basis="generation time (excludes waiting for power)",
                positions_per_second=round(rate,1),eta_hours=round(max(0,target-total)/rate/3600,2))
            atomic(root/"progress.json",progress)
            print(json.dumps(progress),flush=True)
        return total

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("binary",type=Path); p.add_argument("root",type=Path)
    p.add_argument("--target",type=int,default=20_000_000)
    p.add_argument("--games-per-shard",type=int,default=256)
    p.add_argument("--workers",type=int,default=os.cpu_count() or 1)
    p.add_argument("--seed",type=int,default=2026112601)
    p.add_argument("--wait-power",action="store_true",help="idle until usable AC returns")
    a=p.parse_args()
    if min(a.target,a.games_per_shard,a.workers)<1: p.error("positive limits required")
    generate(**vars(a))

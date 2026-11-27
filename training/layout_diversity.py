"""Count distinct normalized Chess768 inputs exactly; labels and move clocks are not inputs."""
import argparse
import hashlib
import heapq
import json
import struct
import tempfile
from contextlib import ExitStack
from itertools import groupby
from pathlib import Path

import numpy as np

from .large_run import atomic, check_shard, sha

KEY_BYTES=24          # 8 byte occupancy + 16 bytes of packed pieces, side-to-move normalized
KEY=struct.Struct("24s")
ROW=np.dtype([("layout","V24"),("label","V8")])
CHUNK=262144


def keys(stream):
    while chunk:=stream.read(KEY_BYTES*4096):
        for (key,) in KEY.iter_unpack(chunk):
            yield key


def count_layouts(files,scratch,chunk_rows=CHUNK):
    """External merge; stores at most 24 bytes per input on disk, never all layouts in RAM."""
    if chunk_rows<1:
        raise ValueError("positive chunk size required")
    rows=0
    buffered=0
    runs=[]
    buf=np.empty(chunk_rows,dtype="V24")
    with tempfile.TemporaryDirectory(dir=scratch,prefix="layout-count-") as t:
        def flush():
            path=Path(t)/f"{len(runs)}.keys"
            np.unique(buf[:buffered]).tofile(path)
            runs.append(path)
        for file in files:
            with file.open("rb") as data:
                while chunk:=data.read((chunk_rows-buffered)*ROW.itemsize):
                    if len(chunk)%ROW.itemsize: raise ValueError(f"partial Bullet row: {file}")
                    records=np.frombuffer(chunk,dtype=ROW)
                    n=len(records); buf[buffered:buffered+n]=records["layout"]
                    rows+=n; buffered+=n
                    if buffered==chunk_rows:
                        flush(); buffered=0
        if buffered: flush()
        # At the 20M target this opens ~77 streams. Bound file descriptors on
        # unexpectedly large inputs rather than silently skipping a run.
        if len(runs)>200: raise ValueError("increase chunk_rows for a larger corpus")
        with ExitStack() as stack:
            sorted_keys=heapq.merge(*(keys(stack.enter_context(path.open("rb"))) for path in runs))
            unique=sum(1 for _key,_items in groupby(sorted_keys))
    return rows,unique


def audit(root,scratch,first=None):
    config=json.loads((root/"campaign.json").read_text())
    shards=sorted(root.glob("shard-[0-9][0-9][0-9][0-9][0-9][0-9]"))
    if first is not None:
        if not 1<=first<=len(shards): raise ValueError("requested shards not yet sealed")
        shards=shards[:first]
    if not shards: raise ValueError("empty corpus")
    chain=hashlib.sha256()
    expected=0
    for i,path in enumerate(shards):
        if path.name!=f"shard-{i:06d}": raise ValueError("missing shard")
        expected+=check_shard(path,config,i,hashes=True)
        chain.update(bytes.fromhex(sha(path/"verified.json")))
    rows,distinct=count_layouts((path/"positions.bullet" for path in shards),scratch)
    if rows!=expected: raise ValueError("corpus length changed")
    return dict(sealed_shards=len(shards),quiet_records=rows,distinct_network_inputs=distinct,
                repeated_records=rows-distinct,distinct_fraction=distinct/rows,
                definition="Exact equality of the first 24 bytes of each Mero-generated Bullet record; no score or WDL. Not distinct full game states.",
                manifest_chain_sha256=chain.hexdigest(),teacher_sha256=config["producer"])


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("corpus",type=Path);p.add_argument("report",type=Path)
    p.add_argument("--first",type=int)
    a=p.parse_args()
    result=audit(a.corpus,a.report.parent,a.first)
    atomic(a.report,result)
    print(json.dumps(result,indent=2))

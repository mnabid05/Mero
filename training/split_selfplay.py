"""Prepare an in-memory pilot split; do not use this small-shard utility for 50M rows."""
import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

def split_shard(src,dest,seed):
    meta=json.loads((src/"COMPLETE.json").read_text())
    data=(src/"positions.bullet").read_bytes()
    if len(data)!=32*meta["positions"] or meta["positions"]>1_000_000:
        raise ValueError("incomplete or oversized pilot shard")
    groups=[[],[]]
    cursor=0
    n_games=[0,0]
    with (src/"games.tsv").open() as ledger:
        for row in csv.DictReader(ledger,delimiter="\t"):
            n=int(row["rows"])
            if int(row["first"])!=cursor: raise ValueError("noncontiguous ledger")
            opening=" ".join(row["uci_moves"].split()[:8])
            h=hashlib.sha256(f"{seed}/{opening}".encode()).digest()
            ix=int.from_bytes(h[:8],"big")%5==0
            n_games[ix]+=1
            groups[ix].extend(data[32*i:32*i+32] for i in range(cursor,cursor+n))
            cursor+=n
    if cursor!=meta["positions"] or sum(n_games)!=meta["games"]:
        raise ValueError("ledger does not cover the shard")
    # Bullet Chess768 observes normalized pieces only. Drop identical and
    # opposite-perspective layouts crossing from training into validation.
    def key(record):
        import struct
        occ,pieces=struct.unpack_from("<Q16s",record)
        ids=[]
        while occ:
            sq=(occ&-occ).bit_length()-1
            i=len(ids)
            pc=(pieces[i//2]>>(4*(i%2)))&15
            ids.append(64*pc+sq)
            occ&=occ-1
        return min(tuple(sorted(ids)),tuple(sorted((x^(8*64+56)) for x in ids)))
    train=set(map(key,groups[0]))
    groups[1]=[r for r in groups[1] if key(r) not in train]
    if min(map(len,groups))==0: raise ValueError("empty split")
    dest.mkdir(parents=True,exist_ok=False)
    summary={"seed":seed,"source_sha256":hashlib.sha256(data).hexdigest(),"groups":{}}
    for rows,games,name in zip(groups,n_games,("train","valid"),strict=True):
        random.Random(seed).shuffle(rows)
        blob=b"".join(rows)
        (dest/(name+".bullet")).write_bytes(blob)
        summary["groups"][name]=dict(games=games,positions=len(rows),sha256=hashlib.sha256(blob).hexdigest())
    (dest/"split.json").write_text(json.dumps(summary,indent=2)+"\n")
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("src",type=Path); p.add_argument("dest",type=Path)
    p.add_argument("--seed",type=int,default=1701)
    a=p.parse_args()
    print(json.dumps(split_shard(a.src,a.dest,a.seed),indent=2))

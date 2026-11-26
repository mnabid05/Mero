"""Stream a sealed corpus snapshot and check mover-relative score/WDL calibration."""
import argparse
import bisect
import csv
import json
import struct
from pathlib import Path
from .large_run import atomic, check_shard, sha

CUTS = [-300,-100,100,300]
ROW=struct.Struct("<Q16x h B 5x")


def profile(root,limit=None):
    config=json.loads((root/"campaign.json").read_text())
    shards=sorted(root.glob("shard-[0-9][0-9][0-9][0-9][0-9][0-9]"))[:limit]
    if not shards:
        raise ValueError("no complete shards")
    bins=[[0]*3 for _ in range(5)]
    heads=[0]*8
    games=[0]*3
    skipped=0
    chain=[]
    for i,path in enumerate(shards):
        count=check_shard(path,config,i,hashes=True)
        chain.append(sha(path/"verified.json"))
        with (path/"games.tsv").open() as stream:
            for game in csv.DictReader(stream,delimiter="\t"):
                result=int(game["white_wdl"])
                if result==-1 and int(game["rows"])==0:
                    skipped+=1
                elif result in (0,1,2):
                    games[result]+=1
                else:
                    raise ValueError("invalid result")
        with (path/"positions.bullet").open("rb") as stream:
            seen=0
            while raw:=stream.read(32*8192):
                for occ,cp,wdl in ROW.iter_unpack(raw):
                    pieces=occ.bit_count()
                    if wdl>2 or not 2<=pieces<=32 or abs(cp)>30_000:
                        raise ValueError("malformed label")
                    bins[bisect.bisect_right(CUTS,cp)][wdl]+=1
                    heads[(pieces-2)//4]+=1
                    seen+=1
            if seen!=count:
                raise ValueError("bad shard length")
    groups=[]
    for lo,hi,wdl in zip([None,*CUTS],[*CUTS,None],bins,strict=True):
        n=sum(wdl)
        groups.append(dict(cp_at_least=lo,cp_below=hi,n=n,mover_loss_draw_win=wdl,
                           mover_score=round((wdl[1]/2+wdl[2])/n,5) if n else None))
    return dict(description="Completed-game outcomes by teacher score, not a match or Elo estimate.",
                config=config,sealed_shards=len(shards),verified_manifest_sha256=chain,
                quiet_positions=sum(heads),rows_by_head=heads,white_loss_draw_win_games=games,
                truncated_games_excluded=skipped,groups=groups)


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("root",type=Path);a.add_argument("out",type=Path)
    a.add_argument("--first",type=int)
    args=a.parse_args()
    result=profile(args.root,args.first)
    atomic(args.out,result)
    print(json.dumps({k:v for k,v in result.items() if k!="verified_manifest_sha256"},indent=2))

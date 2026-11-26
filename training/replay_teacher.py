"""Check recorded moves and quiet cp labels against the separately frozen Mero 7 UCI release."""
import argparse
import csv
import re
import struct
from itertools import islice
from pathlib import Path
from chess_ai.gauntlet import UCIEngine
from training.large_run import atomic,sha


def replay(shard,release,first=0,games=1):
    if first<0 or games<1:
        raise ValueError("invalid game range")
    searches=labels=0
    with (shard/"games.tsv").open() as ledger,(shard/"positions.bullet").open("rb") as data:
        sample=list(islice(csv.DictReader(ledger,delimiter="\t"),first,first+games))
        if len(sample)!=games:
            raise ValueError("range outside ledger")
        # Match datagen: single worker, 8 MiB TT, clear exactly once per game.
        with UCIEngine([str(release.resolve())],{"Hash":8,"Threads":1}) as engine:
            for game in sample:
                engine.new_game()
                data.seek(32*int(game["first"]))
                kept={int(s) for s in game["kept_plies"].split(",") if s}
                moves=game["uci_moves"].split()
                for ply in range(8,len(moves)):
                    engine._send("position startpos moves "+" ".join(moves[:ply]))
                    engine._send("go nodes 5000")
                    reply=engine._read_until("bestmove")
                    if reply[-1].split()[1]!=moves[ply]:
                        raise ValueError(f"teacher move mismatch: game {game['game']}, ply {ply}")
                    searches+=1
                    if ply in kept:
                        matches=[m for line in reply if (m:=re.search(r"^info depth \d+ score cp (-?\d+) nodes (\d+)",line))]
                        raw=data.read(32)
                        if (not matches or int(matches[-1][1])!=struct.unpack_from("<h",raw,24)[0]
                                or not 0<int(matches[-1][2])<=5000):
                            raise ValueError(f"teacher label mismatch: game {game['game']}, ply {ply}")
                        labels+=1
    return dict(games=games,first=first,searches=searches,quiet_labels=labels,
                ledger_sha256=sha(shard/"games.tsv"),records_sha256=sha(shard/"positions.bullet"),
                release_sha256=sha(release),all_moves_and_scores_equal=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("shard","release","output"):
        p.add_argument(n,type=Path)
    p.add_argument("--first",type=int,default=0);p.add_argument("--games",type=int,default=1)
    a=p.parse_args()
    result=replay(a.shard,a.release,a.first,a.games)
    atomic(a.output,result)
    print(result)

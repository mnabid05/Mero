"""Exercise all six frozen search binaries at equal nodes. Never used for promotion."""
import argparse
from pathlib import Path
from chess_ai.backtest import repetition_key
from chess_ai.board import Board
from scripts import fixed_nodes,run_sprt
from scripts.fresh_openings import create,verify
from scripts.replay_uci_pgn import replay
from scripts.scale_campaign import PINS,REPO,expect
from training.large_run import atomic,sha

SEEDS={"lmr":915401,"rfp":915402,"lmp":915403,"singular":915404,
       "continuation":915405,"correction":915406}


def run(build):
    out=build/"scale-canaries"
    out.mkdir(exist_ok=True)
    teacher=expect(build/"producer-v2/mwahaha-engine",PINS["teacher_sha256"])
    baseline=expect(build/"phase1-baseline/mwahaha-engine",PINS["release_sha256"])
    harness=expect(build/"tools/fastchess/fastchess",PINS["fastchess_sha256"])
    official=build/"scale-openings"
    canonical=set()
    def reserve(path):
        for line in path.read_text().splitlines():
            key=repetition_key(Board.from_fen(line+" 0 5"))
            if key in canonical: raise ValueError("overlap with another reserved opening")
            canonical.add(key)
    for name,spec in PINS["books"].items():
        reserve(expect(official/(name+".epd"),spec["sha256"]))
    books={}
    for name,seed in SEEDS.items():
        book=out/(name+".epd")
        if not book.exists(): create(official/"registry.db",book,teacher,seed,count=8)
        meta=verify(book,replay=True)
        if meta["pairs"]!=8 or meta["seed"]!=seed or meta["control_sha256"]!=sha(teacher):
            raise ValueError("changed canary inputs")
        reserve(book)
        books[name]=book
    # Freeze every book before the first game. One lane; no clocks or LLR.
    atomic(out/"books.json",{name:sha(p) for name,p in books.items()})
    results={}
    for name,book in books.items():
        run_sprt.check_power()
        exe=expect(build/f"scale-search-{name}"/"mero",PINS["candidates"][name]["sha256"])
        results[name]=fixed_nodes.run(harness,exe,baseline,book,out/name,
                                      rounds=8,nodes=5000,seed=SEEDS[name],jobs=1,fresh=True)
        results[name]["replay"]=replay(out/name/"games.pgn")
    atomic(out/"complete.json",dict(purpose="fixed-node integration only; no Elo or SPRT decision",
           fastchess_sha256=sha(harness),total_games=sum(x["games"] for x in results.values()),results=results))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build",type=Path,default=REPO/"build")
    run(p.parse_args().build.resolve())

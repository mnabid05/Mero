"""Build a local SQLite corpus for supervised evaluation training."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from .corpus import positions
from .teacher import Teacher

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("teacher", type=Path)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--nodes", type=int, default=2048)
    parser.add_argument("--variants", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1701)
    args = parser.parse_args()
    if args.nodes < 1 or args.variants < 0:
        parser.error("invalid node or variant count")
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    config = json.dumps(dict(nodes=args.nodes, variants=args.variants, seed=args.seed,
                             teacher=digest(args.teacher), reports=[digest(p) for p in sorted(args.reports)]))
    with sqlite3.connect(args.database) as db:
        db.execute("CREATE TABLE IF NOT EXISTS meta(config TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE IF NOT EXISTS samples(fen TEXT PRIMARY KEY, opening TEXT, cp INTEGER)")
        existing = db.execute("SELECT config FROM meta").fetchone()
        if existing and existing[0] != config:
            raise ValueError("resume configuration differs")
        db.execute("INSERT OR IGNORE INTO meta VALUES (?)", (config,))
        with Teacher([str(args.teacher)], {"Hash": 16, "Threads": 1}) as teacher:
            for count, (opening, fen) in enumerate(positions(args.reports, args.seed, args.variants), 1):
                if db.execute("SELECT 1 FROM samples WHERE fen=?", (fen,)).fetchone():
                    continue
                cp = teacher.label(fen, args.nodes)
                db.execute("INSERT INTO samples VALUES (?,?,?)", (fen, opening, cp))
                if count % 500 == 0:
                    db.commit()
                    print(count, flush=True)
    print("Corpus complete", flush=True)

if __name__ == "__main__":
    main()

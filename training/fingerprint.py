import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

def describe(path):
    digest = hashlib.sha256()
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        source = json.loads(db.execute("SELECT config FROM meta").fetchone()[0])
        total, labelled = db.execute("SELECT count(*),count(cp) FROM samples").fetchone()
        for row in db.execute("SELECT fen,opening,cp FROM samples ORDER BY fen"):
            digest.update((json.dumps(row, separators=(",", ":")) + "\n").encode())
    return dict(position_digest=digest.hexdigest(), positions=total, labelled=labelled,
                collection=source)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    print(json.dumps(describe(args.database), indent=2))

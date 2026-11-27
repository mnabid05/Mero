"""Count observed material-imbalance examples in Bullet files. Never used by evaluation or training."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

POPCOUNT = np.array([i.bit_count() for i in range(256)], dtype=np.uint8)
IDS = np.arange(32)

def coverage(path):
    total = imbalance = ahead = behind = 0
    by_head = np.zeros(8, dtype=np.int64)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.read(32 * 8192):
            digest.update(raw)
            if len(raw) % 32:
                raise ValueError("partial record")
            rows = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 32)
            count = POPCOUNT[rows[:, :8]].sum(axis=1, dtype=np.int16)
            if np.any(count < 2):
                raise ValueError("invalid occupancy")
            packed = rows[:, 8:24]
            pcs = np.empty((len(rows), 32), dtype=np.uint8)
            pcs[:, ::2], pcs[:, 1::2] = packed & 15, packed >> 4
            # Unused nibbles are not white pawns, even if all padding bytes equal zero.
            pcs[IDS >= count[:, None]] = 255
            if np.any(((pcs & 7) > 5) & (pcs != 255)):
                raise ValueError("invalid piece")
            def diff(kind):
                return ((pcs == kind).sum(axis=1, dtype=np.int16) -
                        (pcs == kind+8).sum(axis=1, dtype=np.int16))
            if np.any((pcs == 5).sum(axis=1) != 1) or np.any((pcs == 13).sum(axis=1) != 1):
                raise ValueError("expected one king of each color")
            q = diff(4)
            exact = np.abs(q) == 1
            imbalance += int(np.count_nonzero(exact))
            for kind in (0, 1, 2, 3):
                exact &= diff(kind) == 0
            ahead += int(np.count_nonzero(exact & (q == 1)))
            behind += int(np.count_nonzero(exact & (q == -1)))
            by_head += np.bincount((count[exact]-2)//4, minlength=8)
            total += len(rows)
    if not total:
        raise ValueError("empty corpus")
    return dict(rows=total, sha256=digest.hexdigest(), one_queen_difference=imbalance,
                otherwise_equal=ahead+behind, mover_ahead=ahead, mover_behind=behind,
                otherwise_equal_by_output_bucket=by_head.tolist())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", nargs="+", type=Path)
    for path in parser.parse_args().data:
        print(json.dumps(coverage(path), indent=2))

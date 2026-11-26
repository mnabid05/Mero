import sqlite3
import torch

from chess_ai.board import Board
from chess_ai.native import NativeEvaluator
from .features import flip, indices, PADDING
from .split import validation_openings

def load_rows(database, seed):
    evaluator = NativeEvaluator()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        samples = db.execute("SELECT fen,opening,cp FROM samples WHERE cp IS NOT NULL ORDER BY fen").fetchall()
    holdout = validation_openings((r[1] for r in samples), seed)
    groups = ([], [])
    for fen, opening, cp in samples:
        board = Board.from_fen(fen)
        ids = indices(board)
        if len(ids) > 32:
            raise ValueError("position exceeds standard piece count")
        pad = [PADDING] * (32 - len(ids))
        groups[opening in holdout].append((ids + pad, list(map(flip, ids)) + pad,
                                           evaluator.evaluate(board), cp))
    def tensors(rows):
        a, b, prior, target = zip(*rows)
        return (torch.tensor(a), torch.tensor(b), torch.tensor(prior, dtype=torch.float32),
                torch.tensor(target, dtype=torch.float32))
    return tensors(groups[0]), tensors(groups[1]), sorted(holdout)

"""Seed positions from Mero games, with optional reproducible local variations."""
from __future__ import annotations

import json
import random
from pathlib import Path

from chess_ai.board import Board

def positions(paths: list[Path], seed: int, variants: int):
    rng = random.Random(seed)
    seen = set()
    for path in sorted(paths):
        report = json.loads(path.read_text())
        games = report.get("records", report.get("games", []))
        if not isinstance(games, list):
            continue
        for game in games:
            board = Board.starting()
            for ply, move in enumerate(game.get("moves", []), 1):
                board.play_uci(move)
                if ply < 9 or ply % 2:
                    continue
                for index in range(variants + 1):
                    sample = board.copy()
                    if index:
                        for _ in range(rng.randint(1, 4)):
                            legal = sample.legal_moves()
                            if not legal:
                                break
                            sample.push(rng.choice(legal))
                    fen = sample.to_fen()
                    key = tuple(fen.split()[:4])
                    if key in seen or sample.is_in_check():
                        continue
                    seen.add(key)
                    yield game["opening"], fen

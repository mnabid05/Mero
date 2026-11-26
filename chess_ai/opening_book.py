"""Read named UCI move sequences for paired engine matches."""
from pathlib import Path
from .backtest import opening_board, repetition_key
from .model import GameStatus

def load_book(path: Path) -> tuple[tuple[str, tuple[str, ...]], ...]:
    entries, names, positions = [], set(), set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        name, sep, line = raw.partition("|")
        name, moves = name.strip(), tuple(line.split())
        if not sep or not name or not moves or name in names:
            raise ValueError(f"{path}:{number}: invalid or duplicate opening")
        board = opening_board(moves)
        key = repetition_key(board)
        if board.status() != GameStatus.ACTIVE or key in positions:
            raise ValueError(f"{path}:{number}: terminal or duplicate position")
        entries.append((name, moves))
        names.add(name)
        positions.add(key)
    if not entries:
        raise ValueError(f"empty opening book: {path}")
    return tuple(entries)

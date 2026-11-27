"""Independent replay for Fastchess's minimal, UCI-notation, no-adjudication PGNs."""
import argparse
from collections import Counter
from pathlib import Path
import re
from chess_ai.backtest import repetition_key
from chess_ai.board import Board
from chess_ai.model import GameStatus, WHITE

def replay(path, maxmoves=250):
    outcomes = Counter()
    plies = 0
    text = path.read_text().strip()
    if not text.startswith('[Event "'):
        raise ValueError("missing game headers")
    for game in re.split(r'\n+(?=\[Event ")', text):
        headers, body = game.split("\n\n", 1)
        tags = dict(re.findall(r'^\[(\w+) "(.*)"\]$', headers, re.M))
        board = Board.from_fen(tags["FEN"])
        history = Counter({repetition_key(board): 1})
        tokens = body.split()
        if not tokens or tokens[-1] != tags["Result"]:
            raise ValueError("result and move text disagree")
        count = 0
        for token in tokens[:-1]:
            if re.fullmatch(r"[0-9]+\.(?:\.\.)?", token):
                continue
            if not re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", token):
                raise ValueError(f"unexpected UCI PGN token: {token}")
            board.play_uci(token)
            history[repetition_key(board)] += 1
            count += 1
        status = board.status()
        result = "1/2-1/2"
        reason = status.value
        if status == GameStatus.CHECKMATE:
            result = "0-1" if board.turn == WHITE else "1-0"
        elif status == GameStatus.ACTIVE:
            if history[repetition_key(board)] >= 3:
                reason = "threefold repetition"
            elif count >= 2*maxmoves:
                reason = "move limit"
            else:
                raise ValueError("unfinished game recorded as completed")
        if tags["Result"] != result:
            raise ValueError("recorded result disagrees with final position")
        outcomes[reason] += 1
        plies += count
    return dict(games=sum(outcomes.values()), legal_plies=plies, endings=dict(outcomes))

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("game", type=Path, nargs="+")
    for path in p.parse_args().game:
        print(path, replay(path))

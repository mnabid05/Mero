"""JSON-safe game state consumed by the JavaScript client."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict

from chess_ai.model import BLACK, GameStatus, UNICODE_PIECES, WHITE, opponent

from .session import GameSession

STARTING_COUNTS = Counter("RNBQKBNRPPPPPPPPrnbqkbnrpppppppp")


def _captured_pieces(session: GameSession) -> dict[str, list[str]]:
    remaining = Counter(piece for piece in session.board.squares if piece)
    missing = STARTING_COUNTS - remaining
    return {
        "white": [
            UNICODE_PIECES[piece]
            for piece in "qrbnp"
            for _ in range(missing[piece])
        ],
        "black": [
            UNICODE_PIECES[piece]
            for piece in "QRBNP"
            for _ in range(missing[piece])
        ],
    }


def _outcome(session: GameSession) -> tuple[str, str]:
    if session.resigned_color:
        winner = opponent(session.resigned_color)
        return "resigned", "1-0" if winner == WHITE else "0-1"
    if session.threefold_repetition():
        return "draw by threefold repetition", "1/2-1/2"
    status = session.board.status()
    if status == GameStatus.ACTIVE:
        return status.value, "*"
    if status == GameStatus.CHECKMATE:
        winner = opponent(session.board.turn)
        return status.value, "1-0" if winner == WHITE else "0-1"
    return status.value, "1/2-1/2"


def serialize_session(session: GameSession) -> dict[str, object]:
    status, result = _outcome(session)
    active = status == GameStatus.ACTIVE.value
    legal = [move.uci for move in session.board.legal_moves()] if active else []
    check_square = (
        session.board.king_square(session.board.turn)
        if active and session.board.is_in_check()
        else None
    )
    return {
        "id": session.id,
        "fen": session.board.to_fen(),
        "board": session.board.squares,
        "turn": session.board.turn,
        "humanColor": session.human_color,
        "botColor": session.bot_color,
        "humanTurn": session.human_turn and active,
        "difficulty": session.difficulty,
        "status": status,
        "result": result,
        "inCheck": check_square is not None,
        "checkSquare": check_square,
        "legalMoves": legal,
        "lastMove": session.moves[-1].uci if session.moves else None,
        "moves": [asdict(move) for move in session.moves],
        "captured": _captured_pieces(session),
        "createdAt": session.created_at,
        "updatedAt": session.updated_at,
    }

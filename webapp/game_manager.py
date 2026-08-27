"""Concurrent game lifecycle and bot-turn orchestration."""

from __future__ import annotations

import secrets
import threading
import uuid

from chess_ai.model import BLACK, GameStatus, WHITE

from .config import difficulty_for
from .engine_client import EngineClient
from .notation import move_to_san
from .serialize import serialize_session
from .session import GameSession, PlayedMove


class GameNotFoundError(KeyError):
    pass


class GameManager:
    def __init__(self, engine: EngineClient) -> None:
        self.engine = engine
        self._games: dict[str, GameSession] = {}
        self._lock = threading.RLock()

    def new_game(
        self,
        human_color: str = WHITE,
        difficulty: str = "club",
    ) -> dict[str, object]:
        if human_color == "random":
            human_color = WHITE if secrets.randbelow(2) == 0 else BLACK
        if human_color not in {WHITE, BLACK}:
            raise ValueError("color must be w, b, or random")
        selected = difficulty_for(difficulty)
        identifier = uuid.uuid4().hex
        session = GameSession.new(identifier, human_color, selected.key)
        with self._lock:
            self._games[identifier] = session
            if not session.human_turn:
                self._play_bot(session)
            return serialize_session(session)

    def state(self, game_id: str) -> dict[str, object]:
        with self._lock:
            return serialize_session(self._get(game_id))

    def play(self, game_id: str, notation: str) -> dict[str, object]:
        with self._lock:
            session = self._get(game_id)
            if session.resigned_color or session.board.status() != GameStatus.ACTIVE:
                raise ValueError("this game has already ended")
            if session.threefold_repetition():
                raise ValueError("this game ended by repetition")
            if not session.human_turn:
                raise ValueError("wait for Mero to move")
            self._apply(session, notation, session.human_color)
            if session.board.status() == GameStatus.ACTIVE:
                self._play_bot(session)
            return serialize_session(session)

    def resign(self, game_id: str) -> dict[str, object]:
        with self._lock:
            session = self._get(game_id)
            if session.resigned_color is None and session.board.status() == GameStatus.ACTIVE:
                session.resigned_color = session.human_color
            return serialize_session(session)

    def _get(self, game_id: str) -> GameSession:
        try:
            return self._games[game_id]
        except KeyError as error:
            raise GameNotFoundError(game_id) from error

    def _apply(self, session: GameSession, notation: str, color: str) -> None:
        move = session.board.find_legal_move(notation)
        san = move_to_san(session.board, move)
        session.board.push(move)
        session.moves.append(
            PlayedMove(len(session.moves) + 1, color, move.uci, san)
        )
        session.record_position()

    def _play_bot(self, session: GameSession) -> None:
        if session.board.status() != GameStatus.ACTIVE or session.threefold_repetition():
            return
        difficulty = difficulty_for(session.difficulty)
        move = self.engine.choose_move(session.board.to_fen(), difficulty.move_time_ms)
        if move is None:
            return
        self._apply(session, move, session.bot_color)

    def close(self) -> None:
        self.engine.close()

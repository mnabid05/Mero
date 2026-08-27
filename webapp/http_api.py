"""Dependency-free JSON HTTP API for browser games."""

from __future__ import annotations

import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any
from pathlib import Path
from urllib.parse import unquote, urlparse

from .game_manager import GameManager, GameNotFoundError

GAME_ROUTE = re.compile(r"^/api/games/([a-f0-9]{32})$")
MOVE_ROUTE = re.compile(r"^/api/games/([a-f0-9]{32})/moves$")
RESIGN_ROUTE = re.compile(r"^/api/games/([a-f0-9]{32})/resign$")
MAX_BODY_BYTES = 16_384
STATIC_ROOT = Path(__file__).with_name("static")


class MeroRequestHandler(BaseHTTPRequestHandler):
    manager: GameManager
    server_version = "MeroWeb/1.0"

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._json(
                HTTPStatus.OK,
                {"status": "ok", "engine": self.manager.engine.name},
            )
            return
        match = GAME_ROUTE.fullmatch(self.path)
        if match:
            self._execute(lambda: self.manager.state(match.group(1)))
            return
        if not self.path.startswith("/api/"):
            self._static()
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

    def do_POST(self) -> None:
        if self.path == "/api/games":
            self._execute(
                lambda: self.manager.new_game(
                    self._body().get("color", "w"),
                    self._body_cache.get("difficulty", "club"),
                ),
                status=HTTPStatus.CREATED,
            )
            return
        move_match = MOVE_ROUTE.fullmatch(self.path)
        if move_match:
            self._execute(
                lambda: self.manager.play(
                    move_match.group(1), str(self._body().get("move", ""))
                )
            )
            return
        resign_match = RESIGN_ROUTE.fullmatch(self.path)
        if resign_match:
            self._execute(lambda: self.manager.resign(resign_match.group(1)))
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

    def _body(self) -> dict[str, Any]:
        cached = getattr(self, "_body_cache", None)
        if cached is not None:
            return cached
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_BYTES:
            raise ValueError("request body is too large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError("request body must be valid JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        self._body_cache = payload
        return payload

    def _execute(
        self,
        operation: Any,
        *,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        try:
            self._json(status, operation())
        except GameNotFoundError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "game not found"})
        except ValueError as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except RuntimeError:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "Mero could not calculate a move"},
            )

    def _json(self, status: HTTPStatus, payload: object) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _static(self) -> None:
        requested = unquote(urlparse(self.path).path)
        relative = "index.html" if requested == "/" else requested.lstrip("/")
        candidate = (STATIC_ROOT / relative).resolve()
        try:
            candidate.relative_to(STATIC_ROOT.resolve())
        except ValueError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "asset not found"})
            return
        if not candidate.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "asset not found"})
            return
        content = candidate.read_bytes()
        content_type, _ = mimetypes.guess_type(candidate.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        return None

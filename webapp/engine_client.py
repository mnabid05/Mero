"""Thread-safe UCI bridge between web games and the native Mero engine."""

from __future__ import annotations

import re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

BEST_MOVE = re.compile(r"^bestmove\s+(\S+)")


class EngineClient(Protocol):
    name: str

    def choose_move(self, fen: str, move_time_ms: int) -> str | None: ...

    def close(self) -> None: ...


@dataclass(slots=True)
class NativeEngineClient:
    executable: Path
    threads: int = 1
    hash_megabytes: int = 64
    name: str = "Mero Native"
    _process: subprocess.Popen[str] | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        if not self.executable.is_file():
            raise FileNotFoundError(f"native engine not found: {self.executable}")

    def _start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        self._process = subprocess.Popen(
            [str(self.executable)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._send("uci")
        self._read_until("uciok")
        self._send(f"setoption name Hash value {self.hash_megabytes}")
        self._send(f"setoption name Threads value {self.threads}")
        self._send("isready")
        self._read_until("readyok")

    def _send(self, command: str) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("engine process is unavailable")
        self._process.stdin.write(command + "\n")
        self._process.stdin.flush()

    def _read_until(self, prefix: str) -> list[str]:
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("engine output is unavailable")
        lines: list[str] = []
        while True:
            line = self._process.stdout.readline()
            if not line:
                raise RuntimeError(f"engine exited before {prefix}")
            stripped = line.strip()
            lines.append(stripped)
            if stripped.startswith(prefix):
                return lines

    def choose_move(self, fen: str, move_time_ms: int) -> str | None:
        with self._lock:
            self._start()
            self._send(f"position fen {fen}")
            self._send(f"go movetime {max(10, move_time_ms)}")
            response = self._read_until("bestmove")[-1]
            match = BEST_MOVE.match(response)
            if match is None or match.group(1) == "0000":
                return None
            return match.group(1)

    def close(self) -> None:
        with self._lock:
            if self._process is None:
                return
            if self._process.poll() is None:
                try:
                    self._send("quit")
                    self._process.wait(timeout=2)
                except (BrokenPipeError, subprocess.TimeoutExpired):
                    self._process.terminate()
            self._process = None


def default_native_executable() -> Path:
    return Path(__file__).resolve().parents[1] / "build" / "native" / "mwahaha-engine"

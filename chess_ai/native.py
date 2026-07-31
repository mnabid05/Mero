"""Optional bridge to the C11 evaluation accelerator."""

from __future__ import annotations

import ctypes
import os
import platform
from pathlib import Path

from .board import Board
from .evaluation import Evaluation, Evaluator
from .model import WHITE


def _library_name() -> str:
    system = platform.system()
    if system == "Darwin":
        return "libmwahaha_eval.dylib"
    if system == "Windows":
        return "mwahaha_eval.dll"
    return "libmwahaha_eval.so"


def _candidate_paths() -> tuple[Path, ...]:
    configured = os.environ.get("MWAHAHA_NATIVE_LIB")
    project_library = (
        Path(__file__).resolve().parents[1] / "build" / "native" / _library_name()
    )
    if configured:
        return (Path(configured).expanduser(), project_library)
    return (project_library,)


def find_native_library() -> Path | None:
    """Return the compiled evaluator path, unless native code is disabled."""
    if os.environ.get("MWAHAHA_PURE_PYTHON", "").lower() in {"1", "true", "yes"}:
        return None
    return next((path for path in _candidate_paths() if path.is_file()), None)


class NativeEvaluator:
    """Evaluate positions through the portable C11 hot-path kernel."""

    def __init__(self, library_path: Path | None = None) -> None:
        path = library_path or find_native_library()
        if path is None:
            raise FileNotFoundError(
                "Native evaluator not built; run python scripts/build_native.py"
            )
        self.library_path = path
        self._library = ctypes.CDLL(str(path))
        self._library.mwahaha_native_api_version.argtypes = []
        self._library.mwahaha_native_api_version.restype = ctypes.c_int
        if self._library.mwahaha_native_api_version() != 1:
            raise RuntimeError("Unsupported native evaluator API")
        self._evaluate = self._library.mwahaha_evaluate
        self._evaluate.argtypes = [ctypes.c_char_p]
        self._evaluate.restype = ctypes.c_int

    def evaluate(self, board: Board) -> int:
        encoded = "".join(piece or "." for piece in board.squares).encode("ascii")
        return int(self._evaluate(encoded))

    def evaluate_for_turn(self, board: Board) -> int:
        score = self.evaluate(board)
        return score if board.turn == WHITE else -score

    def explain(self, board: Board) -> Evaluation:
        score = self.evaluate(board)
        return Evaluation(score=score, middlegame=score, endgame=score, phase=0)


def best_available_evaluator() -> Evaluator | NativeEvaluator:
    """Prefer the compiled kernel while preserving a dependency-free fallback."""
    path = find_native_library()
    return NativeEvaluator(path) if path is not None else Evaluator()

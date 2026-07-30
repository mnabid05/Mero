"""A small, readable chess engine and command-line game."""

__version__ = "1.0.0"

from .board import Board
from .engine import ChessAI

__all__ = ["Board", "ChessAI"]

import unittest

from chess_ai.board import Board
from chess_ai.engine import ChessAI


class EngineTests(unittest.TestCase):
    def test_evaluation_favors_extra_material(self):
        engine = ChessAI(depth=1)
        board = Board.from_fen("7k/8/8/8/8/8/8/Q6K w - - 0 1")
        self.assertGreater(engine.evaluate(board), 800)

    def test_ai_captures_a_hanging_queen(self):
        engine = ChessAI(depth=1)
        board = Board.from_fen("7k/8/8/8/8/8/q7/R6K w - - 0 1")
        move = engine.choose_move(board)
        self.assertIsNotNone(move)
        self.assertEqual(move.uci, "a1a2")
        self.assertGreater(engine.nodes, 0)

    def test_ai_returns_only_legal_moves(self):
        engine = ChessAI(depth=2)
        board = Board.starting()
        legal = set(board.legal_moves())
        self.assertIn(engine.choose_move(board), legal)


if __name__ == "__main__":
    unittest.main()

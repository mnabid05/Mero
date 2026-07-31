import unittest

from chess_ai.model import BLACK
from chess_ai.uci import parse_position, time_budget


class UCITests(unittest.TestCase):
    def test_startpos_move_sequence(self):
        board = parse_position("position startpos moves e2e4 e7e5 g1f3")
        self.assertEqual(board.turn, BLACK)
        self.assertIsNotNone(board.find_legal_move("b8c6"))

    def test_fen_position(self):
        board = parse_position("position fen 7k/8/8/8/8/8/8/7K w - - 0 1")
        self.assertEqual(board.to_fen(), "7k/8/8/8/8/8/8/7K w - - 0 1")

    def test_movetime_budget_subtracts_overhead(self):
        board = parse_position("position startpos")
        self.assertEqual(time_budget("go movetime 1000", board, 20), 980)


if __name__ == "__main__":
    unittest.main()

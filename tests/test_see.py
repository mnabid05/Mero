import unittest

from chess_ai.board import Board
from chess_ai.see import static_exchange_evaluation


class StaticExchangeTests(unittest.TestCase):
    def test_free_queen_is_winning(self):
        board = Board.from_fen("7k/8/8/8/8/8/q7/R6K w - - 0 1")
        move = board.find_legal_move("a1a2")
        self.assertGreaterEqual(static_exchange_evaluation(board, move), 900)

    def test_defended_pawn_is_poisoned_for_queen(self):
        board = Board.from_fen("3q3k/8/8/3p4/8/8/8/3Q3K w - - 0 1")
        move = board.find_legal_move("d1d5")
        self.assertLess(static_exchange_evaluation(board, move), -700)


if __name__ == "__main__":
    unittest.main()

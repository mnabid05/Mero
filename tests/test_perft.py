import unittest

from chess_ai import Board
from chess_ai.perft import divide, perft


class PerftTests(unittest.TestCase):
    def test_standard_starting_counts(self):
        board = Board.starting()
        self.assertEqual(perft(board, 1), 20)
        self.assertEqual(perft(board, 2), 400)
        self.assertEqual(perft(board, 3), 8902)

    def test_divide_sums_to_total(self):
        board = Board.starting()
        self.assertEqual(sum(divide(board, 2).values()), perft(board, 2))


if __name__ == "__main__":
    unittest.main()

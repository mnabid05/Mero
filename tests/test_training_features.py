import unittest
from chess_ai.board import Board
from training.features import indices, flip, FEATURES
from training.split import validation_openings

class TrainingFeatureTests(unittest.TestCase):
    def test_holdout_is_independent_of_row_order(self):
        groups = ["French", "Slav", "English", "Italian", "Open"]
        held = validation_openings(groups * 2, 1701)
        self.assertEqual(held, validation_openings(reversed(groups), 1701))
        self.assertEqual(len(held), 1)
        with self.assertRaises(ValueError):
            validation_openings(["French", "French"], 1701)

    def test_color_reversal_is_involution(self):
        for index in range(FEATURES):
            self.assertEqual(flip(flip(index)), index)

    def test_starting_position_has_identical_two_views(self):
        ids = indices(Board.starting())
        self.assertEqual(len(set(ids)), 32)
        self.assertEqual(sorted(ids), sorted(map(flip, ids)))

    def test_endgame_white_rook_index(self):
        board = Board.from_fen("7k/8/8/8/8/8/8/R6K w - - 0 1")
        self.assertIn(3 * 64 + 56, indices(board))

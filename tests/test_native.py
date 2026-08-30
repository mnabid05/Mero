import unittest

from chess_ai.board import Board
from chess_ai.native import NativeEvaluator, find_native_library


@unittest.skipUnless(find_native_library(), "native evaluator has not been built")
class NativeEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.evaluator = NativeEvaluator()

    def test_starting_position_is_symmetric(self):
        self.assertEqual(self.evaluator.evaluate(Board.starting()), 0)

    def test_material_advantage_is_large(self):
        board = Board.from_fen("7k/8/8/8/8/8/8/Q6K w - - 0 1")
        self.assertGreater(self.evaluator.evaluate(board), 900)

    def test_mirrored_material_changes_sign(self):
        white = Board.from_fen("7k/8/8/8/8/8/8/Q6K w - - 0 1")
        black = Board.from_fen("q6k/8/8/8/8/8/8/7K b - - 0 1")
        self.assertEqual(
            self.evaluator.evaluate(white),
            -self.evaluator.evaluate(black),
        )

    def test_loose_piece_is_penalized_when_attacked_by_pawn(self):
        safe = Board.from_fen("7k/8/3p4/8/4N3/8/8/7K w - - 0 1")
        threatened = Board.from_fen("7k/8/8/3p4/4N3/8/8/7K w - - 0 1")
        self.assertLess(
            self.evaluator.evaluate(threatened),
            self.evaluator.evaluate(safe),
        )


if __name__ == "__main__":
    unittest.main()

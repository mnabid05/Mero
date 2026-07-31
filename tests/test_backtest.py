import unittest

from chess_ai import Board, ChessAI, LegacyAI
from chess_ai.backtest import OPENINGS, opening_board, repetition_key, run_match


class BacktestTests(unittest.TestCase):
    def test_opening_sequences_are_legal_and_repeatable(self):
        for _, moves in OPENINGS:
            self.assertEqual(opening_board(moves).to_fen(), opening_board(moves).to_fen())

    def test_repetition_key_ignores_move_clocks(self):
        board = Board.starting()
        key = repetition_key(board)
        board.halfmove_clock = 87
        board.fullmove_number = 44
        self.assertEqual(repetition_key(board), key)

    def test_matches_require_paired_colors(self):
        with self.assertRaises(ValueError):
            run_match(
                ChessAI(depth=1, movetime_ms=10),
                LegacyAI(depth=1),
                games=3,
            )


if __name__ == "__main__":
    unittest.main()

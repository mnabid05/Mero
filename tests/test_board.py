import unittest

from chess_ai.board import STARTING_FEN, Board
from chess_ai.model import BLACK, WHITE, parse_square


class BoardTests(unittest.TestCase):
    def test_starting_position_round_trips_through_fen(self):
        board = Board.starting()
        self.assertEqual(board.to_fen(), STARTING_FEN)
        self.assertEqual(board.piece_at(parse_square("e1")), "K")
        self.assertEqual(board.piece_at(parse_square("e8")), "k")

    def test_starting_position_has_twenty_legal_moves(self):
        self.assertEqual(len(Board.starting().legal_moves()), 20)

    def test_copy_is_independent(self):
        board = Board.starting()
        copy = board.copy()
        copy.play_uci("e2e4")
        self.assertEqual(board.turn, WHITE)
        self.assertEqual(copy.turn, BLACK)
        self.assertIsNotNone(board.piece_at(parse_square("e2")))
        self.assertIsNone(copy.piece_at(parse_square("e2")))

    def test_double_pawn_move_updates_state(self):
        board = Board.starting()
        board.play_uci("e2e4")
        self.assertEqual(board.en_passant, parse_square("e3"))
        self.assertEqual(board.halfmove_clock, 0)
        self.assertEqual(board.fullmove_number, 1)

    def test_board_renders_coordinates(self):
        rendered = Board.starting().render(unicode=False)
        self.assertIn("8  r n b q k b n r", rendered)
        self.assertIn("a b c d e f g h", rendered)


if __name__ == "__main__":
    unittest.main()

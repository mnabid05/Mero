import unittest

from chess_ai.board import Board
from chess_ai.model import GameStatus, parse_square


class RuleTests(unittest.TestCase):
    def test_pinned_piece_cannot_expose_king(self):
        board = Board.from_fen("4r2k/8/8/8/8/8/4R3/4K3 w - - 0 1")
        legal = {move.uci for move in board.legal_moves()}
        self.assertNotIn("e2f2", legal)
        self.assertIn("e2e8", legal)

    def test_fools_mate_is_checkmate(self):
        board = Board.starting()
        for notation in ("f2f3", "e7e5", "g2g4", "d8h4"):
            board.play_uci(notation)
        self.assertTrue(board.is_in_check())
        self.assertEqual(board.status(), GameStatus.CHECKMATE)

    def test_castling_moves_the_rook(self):
        board = Board.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        board.play_uci("e1g1")
        self.assertEqual(board.piece_at(parse_square("g1")), "K")
        self.assertEqual(board.piece_at(parse_square("f1")), "R")
        self.assertIsNone(board.piece_at(parse_square("h1")))

    def test_en_passant_removes_captured_pawn(self):
        board = Board.from_fen("7k/8/8/3pP3/8/8/8/7K w - d6 0 1")
        board.play_uci("e5d6")
        self.assertEqual(board.piece_at(parse_square("d6")), "P")
        self.assertIsNone(board.piece_at(parse_square("d5")))

    def test_pawn_promotion_selects_piece(self):
        board = Board.from_fen("7k/P7/8/8/8/8/8/7K w - - 0 1")
        board.play_uci("a7a8q")
        self.assertEqual(board.piece_at(parse_square("a8")), "Q")

    def test_stalemate_is_detected(self):
        board = Board.from_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        self.assertFalse(board.is_in_check())
        self.assertEqual(board.status(), GameStatus.STALEMATE)

    def test_bare_kings_are_a_draw(self):
        board = Board.from_fen("7k/8/8/8/8/8/8/7K w - - 0 1")
        self.assertEqual(board.status(), GameStatus.DRAW_INSUFFICIENT_MATERIAL)


if __name__ == "__main__":
    unittest.main()

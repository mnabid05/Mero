import unittest

from chess_ai.board import Board
from webapp.notation import move_to_san


class WebNotationTests(unittest.TestCase):
    def test_formats_quiet_pawn_and_knight_moves(self):
        board = Board.starting()
        move = board.find_legal_move("e2e4")
        self.assertEqual(move_to_san(board, move), "e4")
        board.push(move)
        board.play_uci("e7e5")
        knight = board.find_legal_move("g1f3")
        self.assertEqual(move_to_san(board, knight), "Nf3")

    def test_marks_checkmate(self):
        board = Board.starting()
        for notation in ("f2f3", "e7e5", "g2g4"):
            board.play_uci(notation)
        mate = board.find_legal_move("d8h4")
        self.assertEqual(move_to_san(board, mate), "Qh4#")


if __name__ == "__main__":
    unittest.main()

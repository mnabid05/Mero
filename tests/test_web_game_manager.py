import unittest

from chess_ai.board import Board
from webapp.game_manager import GameManager


class FirstMoveEngine:
    name = "Deterministic Test Engine"

    def choose_move(self, fen, move_time_ms):
        del move_time_ms
        moves = Board.from_fen(fen).legal_moves()
        return moves[0].uci if moves else None

    def close(self):
        return None


class WebGameManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = GameManager(FirstMoveEngine())

    def test_player_move_is_followed_by_engine_reply(self):
        game = self.manager.new_game("w", "quick")
        updated = self.manager.play(game["id"], "e2e4")
        self.assertEqual(len(updated["moves"]), 2)
        self.assertTrue(updated["humanTurn"])
        self.assertEqual(updated["moves"][0]["uci"], "e2e4")

    def test_engine_opens_when_player_selects_black(self):
        game = self.manager.new_game("b", "quick")
        self.assertEqual(len(game["moves"]), 1)
        self.assertTrue(game["humanTurn"])

    def test_resignation_ends_the_game(self):
        game = self.manager.new_game("w", "quick")
        resigned = self.manager.resign(game["id"])
        self.assertEqual(resigned["status"], "resigned")
        self.assertEqual(resigned["result"], "0-1")


if __name__ == "__main__":
    unittest.main()

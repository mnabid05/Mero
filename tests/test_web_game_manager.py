import unittest

from chess_ai.board import Board
from webapp.engine_client import NativeEngineClient, best_available_engine, default_native_executable
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

    @unittest.skipUnless(default_native_executable().is_file(), "native release not built")
    def test_default_web_backend_answers_a_real_player_move(self):
        engine = best_available_engine()
        self.addCleanup(engine.close)
        self.assertIsInstance(engine, NativeEngineClient)
        manager = GameManager(engine)
        game = manager.new_game("w", "quick")
        state = manager.play(game["id"], "e2e4")
        self.assertTrue(state["humanTurn"])
        self.assertEqual(len(state["moves"]), 2)
        board = Board.starting()
        for row in state["moves"]:
            board.play_uci(row["uci"])
        self.assertEqual(board.to_fen(), state["fen"])


if __name__ == "__main__":
    unittest.main()

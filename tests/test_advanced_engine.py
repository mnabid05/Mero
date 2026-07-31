import time
import unittest

from chess_ai import Board, ChessAI
from chess_ai.evaluation import Evaluator
from chess_ai.hashing import ZobristHasher
from chess_ai.model import GameStatus


class AdvancedEngineTests(unittest.TestCase):
    def test_zobrist_hash_covers_position_state(self):
        hasher = ZobristHasher()
        board = Board.starting()
        self.assertEqual(hasher.hash(board), hasher.hash(board.copy()))
        moved = board.after(board.find_legal_move("e2e4"))
        self.assertNotEqual(hasher.hash(board), hasher.hash(moved))

    def test_starting_evaluation_is_symmetric(self):
        self.assertEqual(Evaluator().evaluate(Board.starting()), 0)

    def test_evaluation_rewards_extra_queen(self):
        board = Board.from_fen("7k/8/8/8/8/8/8/Q6K w - - 0 1")
        self.assertGreater(Evaluator().evaluate(board), 900)

    def test_iterative_search_builds_legal_principal_variation(self):
        board = Board.starting()
        engine = ChessAI(depth=4, movetime_ms=500)
        move = engine.choose_move(board)
        self.assertIn(move, board.legal_moves())
        self.assertGreaterEqual(engine.depth_reached, 3)
        self.assertTrue(engine.principal_variation)
        position = board.copy()
        for candidate in engine.principal_variation:
            self.assertIn(candidate, position.legal_moves())
            position.push(candidate)

    def test_search_uses_transposition_table(self):
        engine = ChessAI(depth=4, movetime_ms=500)
        engine.choose_move(Board.starting())
        self.assertGreater(engine.tt_hits, 0)

    def test_engine_finds_immediate_checkmate(self):
        board = Board.from_fen("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
        engine = ChessAI(depth=4, movetime_ms=500)
        move = engine.choose_move(board)
        board.push(move)
        self.assertEqual(board.status(), GameStatus.CHECKMATE)

    def test_time_control_stops_search(self):
        engine = ChessAI(depth=20, movetime_ms=50)
        started = time.perf_counter()
        move = engine.choose_move(Board.starting())
        elapsed = time.perf_counter() - started
        self.assertIsNotNone(move)
        self.assertLess(elapsed, 1.0)


if __name__ == "__main__":
    unittest.main()

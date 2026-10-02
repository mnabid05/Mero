import unittest
from unittest.mock import Mock

from chess_ai.gauntlet import UCIEngine, _play_game
from chess_ai.model import WHITE, BLACK

from chess_ai.gauntlet import estimate_rating, run_gauntlet


class RatingEstimateTests(unittest.TestCase):
    def test_forfeit_is_assigned_to_the_failed_side(self):
        candidate, rival = Mock(), Mock()
        candidate.choose_move.side_effect = RuntimeError("crashed")
        rival.choose_move.side_effect = RuntimeError("crashed")
        for color, expected in ((WHITE, 0.0), (BLACK, 1.0)):
            game = _play_game(candidate, rival, 2300, 1, "start", (), color, 10, 2)
            self.assertEqual(game.candidate_score, expected)
            self.assertIn("engine forfeit", game.reason)

    def test_unsupported_strength_options_fail_closed(self):
        engine = object.__new__(UCIEngine)
        engine.name, engine.options = "fake", {}
        with self.assertRaisesRegex(ValueError, "does not advertise"):
            engine.set_option("UCI_Elo", 2300)
        engine.options = {"UCI_Elo": "spin default 1500 min 1000 max 2000"}
        with self.assertRaisesRegex(ValueError, "outside advertised"):
            engine.set_option("UCI_Elo", 2300)

    def test_even_score_matches_opponent_rating(self):
        estimate = estimate_rating([(1500, 1.0), (1500, 0.0)])
        self.assertEqual(estimate.elo, 1500)
        self.assertLess(estimate.confidence_low, estimate.elo)
        self.assertGreater(estimate.confidence_high, estimate.elo)

    def test_better_results_raise_estimate(self):
        estimate = estimate_rating(
            [(1500, 1.0), (1500, 1.0), (1500, 0.5), (1500, 0.0)]
        )
        self.assertGreater(estimate.elo, 1500)

    def test_empty_results_are_rejected(self):
        with self.assertRaises(ValueError):
            estimate_rating([])

    def test_candidate_thread_range_is_validated(self):
        with self.assertRaisesRegex(ValueError, "threads"):
            run_gauntlet(
                ("candidate",),
                ("opponent",),
                (2000,),
                2,
                30,
                80,
                candidate_threads=0,
            )

    def test_opponent_thread_range_is_validated(self):
        with self.assertRaisesRegex(ValueError, "Opponent threads"):
            run_gauntlet(
                ("candidate",),
                ("opponent",),
                (2000,),
                2,
                30,
                80,
                opponent_threads=65,
            )


if __name__ == "__main__":
    unittest.main()

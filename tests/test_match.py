import unittest

from chess_ai.match import run_match, score_to_elo


class MatchHarnessTests(unittest.TestCase):
    def test_score_to_elo_is_symmetric(self):
        self.assertEqual(score_to_elo(0.5), 0)
        self.assertEqual(score_to_elo(0.64), -score_to_elo(0.36))
        self.assertGreaterEqual(score_to_elo(0.64), 99)

    def test_matches_require_paired_games(self):
        with self.assertRaisesRegex(ValueError, "positive even"):
            run_match(("candidate",), ("baseline",), 3, 20, 80)

    def test_matches_validate_search_resources(self):
        with self.assertRaisesRegex(ValueError, "at least 10"):
            run_match(("candidate",), ("baseline",), 2, 5, 80)
        with self.assertRaisesRegex(ValueError, "between 1 and 64"):
            run_match(
                ("candidate",),
                ("baseline",),
                2,
                20,
                80,
                candidate_threads=0,
            )
        with self.assertRaisesRegex(ValueError, "between 1 and 64"):
            run_match(
                ("candidate",),
                ("baseline",),
                2,
                20,
                80,
                baseline_threads=65,
            )


if __name__ == "__main__":
    unittest.main()

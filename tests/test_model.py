import unittest

from chess_ai.model import Move, parse_square, square_name


class CoordinateTests(unittest.TestCase):
    def test_every_square_round_trips(self):
        for index in range(64):
            self.assertEqual(parse_square(square_name(index)), index)

    def test_uci_move_round_trips(self):
        self.assertEqual(Move.from_uci("e2e4").uci, "e2e4")
        self.assertEqual(Move.from_uci("a7a8Q").uci, "a7a8q")

    def test_invalid_square_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_square("i9")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from chess_ai.backtest import OPENINGS, opening_board, repetition_key
from chess_ai.opening_book import load_book

class CalibrationBookTests(unittest.TestCase):
    def test_release_book_uses_fresh_endpoints(self):
        path = Path(__file__).resolve().parents[1] / "training/calibration.openings"
        book = load_book(path)
        def endpoints(lines):
            return {repetition_key(opening_board(moves)) for _, moves in lines}
        self.assertEqual(16, len(book))
        self.assertTrue(endpoints(book).isdisjoint(endpoints(OPENINGS)))

    def test_bad_lines_fail_before_any_match(self):
        for content in ("", "x | a1a7", "x | g1f3\nx | b1c3",
                        "x | g1f3 g8f6 b1c3 b8c6\ny | b1c3 b8c6 g1f3 g8f6"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "book"
                path.write_text(content)
                with self.assertRaises(ValueError):
                    load_book(path)

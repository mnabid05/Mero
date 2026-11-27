from pathlib import Path
import tempfile
import unittest
from scripts.fixed_nodes import epd_pair_scores
from scripts.replay_uci_pgn import replay


class ActualOpeningPair(unittest.TestCase):
    epd="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6"
    def game(self,w,b,result):
        return f'[Event "test"]\n[White "{w}"]\n[Black "{b}"]\n[Result "{result}"]\n[FEN "{self.epd} 0 2"]\n\n{result}\n'

    def test_demands_both_colors_and_actual_positions(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"games.pgn"
            first=self.game("New","Main","1-0")
            p.write_text(first+self.game("Main","New","1/2-1/2"))
            self.assertEqual(epd_pair_scores(p,[self.epd]),dict(wins=1,draws=1,losses=0))
            p.write_text(first+first)
            with self.assertRaisesRegex(ValueError,"openings/colors"):
                epd_pair_scores(p,[self.epd])

    def test_replay_requires_legal_moves_and_true_result(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"games.pgn"
            game='[Event "test"]\n[Result "0-1"]\n[FEN "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"]\n\n1. f2f3 e7e5 2. g2g4 d8h4 0-1\n'
            p.write_text(game)
            self.assertEqual(replay(p),dict(games=1,legal_plies=4,endings={"checkmate":1}))
            for bad in (game.replace("d8h4","d8h2"),game.replace("0-1","1-0"),game.replace("d8h4 ","")):
                p.write_text(bad)
                with self.assertRaises(ValueError): replay(p)

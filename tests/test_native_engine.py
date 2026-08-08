import re
import subprocess
import unittest
from pathlib import Path

from chess_ai.board import Board
from chess_ai.perft import perft

ROOT = Path(__file__).resolve().parents[1]
NATIVE_ENGINE = ROOT / "build" / "native" / "mwahaha-engine"

POSITIONS = (
    "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
    "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
    "4k3/P7/8/8/8/8/7p/4K3 w - - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/2pP4/1p2P3/2N2N2/PPPBBPPP/"
    "R2Q1RK1 w kq - 0 1",
)


@unittest.skipUnless(NATIVE_ENGINE.is_file(), "native engine has not been built")
class NativeEngineTests(unittest.TestCase):
    def native_perft(self, fen: str, depth: int) -> int:
        result = subprocess.run(
            [NATIVE_ENGINE, "--perft-fen", str(depth), fen],
            check=True,
            capture_output=True,
            text=True,
        )
        match = re.search(r": (\d+) nodes", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        return int(match.group(1))

    def test_special_rule_positions_match_reference(self):
        for fen in POSITIONS:
            with self.subTest(fen=fen):
                expected = perft(Board.from_fen(fen), 2)
                self.assertEqual(self.native_perft(fen, 2), expected)

    def test_native_uci_returns_legal_move(self):
        commands = "uci\nisready\nposition startpos\ngo movetime 50\nquit\n"
        result = subprocess.run(
            [NATIVE_ENGINE],
            input=commands,
            check=True,
            capture_output=True,
            text=True,
        )
        match = re.search(r"bestmove ([a-h][1-8][a-h][1-8][qrbn]?)", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        board = Board.starting()
        board.find_legal_move(match.group(1))

    def test_native_quiescence_sees_quiet_promotion_threat(self):
        commands = (
            "uci\n"
            "position fen 4k3/7r/8/8/8/8/p6Q/6K1 w - - 0 1\n"
            "go depth 1\n"
            "quit\n"
        )
        result = subprocess.run(
            [NATIVE_ENGINE],
            input=commands,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("bestmove h2a2", result.stdout)


if __name__ == "__main__":
    unittest.main()

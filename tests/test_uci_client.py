"""Process-level regressions for hostile or stalled UCI peers."""
import sys
import unittest

from chess_ai.gauntlet import UCIEngine
from chess_ai.board import Board


FAKE = '''
import sys
for line in sys.stdin:
    command = line.strip()
    if command == "uci":
        print("id name fixture", flush=True)
        print("option name Hash type spin default 1 min 1 max 64", flush=True)
        print("uciok", flush=True)
    elif command == "isready":
        print("readyok", flush=True)
    elif command.startswith("position"):
        position = command
    elif command.startswith("go"):
        print("info string " + position, flush=True)
        print("bestmove e2e4", flush=True)
    elif command == "quit":
        break
'''


class UCIClientTests(unittest.TestCase):
    def test_handshake_move_and_reaping(self):
        with UCIEngine((sys.executable, "-u", "-c", FAKE)) as client:
            self.assertEqual(client.name, "fixture")
            client.set_option("Hash", 16)
            self.assertEqual(client.choose_move(Board.starting(), 10, []), "e2e4")
        self.assertIsNotNone(client.process.returncode)
        self.assertFalse(client._reader.is_alive())

    def test_stalled_peer_is_killed(self):
        with UCIEngine((sys.executable, "-u", "-c", FAKE)) as client:
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                client._read_until("never", timeout=0.05)
        self.assertIsNotNone(client.process.returncode)

    def test_eof_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, "exited"):
            UCIEngine((sys.executable, "-c", "pass"))

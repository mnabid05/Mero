import unittest

from webapp.session import GameSession, PlayedMove
from webapp.serialize import serialize_session


class WebSerializationTests(unittest.TestCase):
    def test_starting_state_contains_complete_browser_contract(self):
        payload = serialize_session(GameSession.new("game-1", "w", "club"))
        self.assertEqual(payload["id"], "game-1")
        self.assertEqual(len(payload["board"]), 64)
        self.assertEqual(len(payload["legalMoves"]), 20)
        self.assertTrue(payload["humanTurn"])
        self.assertEqual(payload["result"], "*")

    def test_capture_summary_tracks_removed_pieces(self):
        session = GameSession.new("game-2", "w", "club")
        for notation in ("e2e4", "d7d5"):
            session.board.play_uci(notation)
        move = session.board.find_legal_move("e4d5")
        session.board.push(move)
        session.moves.append(PlayedMove(3, "w", move.uci, "exd5"))
        payload = serialize_session(session)
        self.assertEqual(payload["captured"]["white"], ["♟"])
        self.assertEqual(payload["lastMove"], "e4d5")


if __name__ == "__main__":
    unittest.main()

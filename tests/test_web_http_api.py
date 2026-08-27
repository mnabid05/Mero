import json
import threading
import unittest
from urllib.request import Request, urlopen

from chess_ai.board import Board
from webapp.game_manager import GameManager
from webapp.http_api import MeroRequestHandler
from webapp.server import MeroWebServer


class TestEngine:
    name = "HTTP Test Engine"

    def choose_move(self, fen, move_time_ms):
        del move_time_ms
        return Board.from_fen(fen).legal_moves()[0].uci

    def close(self):
        return None


class WebHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manager = GameManager(TestEngine())
        handler = type("TestHandler", (MeroRequestHandler,), {"manager": cls.manager})
        cls.server = MeroWebServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def json_request(self, path, data=None):
        body = None if data is None else json.dumps(data).encode()
        request = Request(self.base + path, data=body, headers={"Content-Type": "application/json"})
        with urlopen(request) as response:
            return response.status, json.load(response)

    def test_health_and_static_shell_are_served(self):
        status, health = self.json_request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["engine"], "HTTP Test Engine")
        with urlopen(self.base + "/") as response:
            self.assertIn(b'id="chessboard"', response.read())

    def test_game_and_move_routes(self):
        status, game = self.json_request("/api/games", {"color": "w", "difficulty": "quick"})
        self.assertEqual(status, 201)
        _, updated = self.json_request(f'/api/games/{game["id"]}/moves', {"move": "e2e4"})
        self.assertEqual(len(updated["moves"]), 2)


if __name__ == "__main__":
    unittest.main()

"""Launch the local Mero web application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from http.server import ThreadingHTTPServer

from .engine_client import best_available_engine
from .game_manager import GameManager
from .http_api import MeroRequestHandler


class MeroWebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def build_server(host: str, port: int) -> tuple[MeroWebServer, GameManager]:
    manager = GameManager(best_available_engine())
    handler = type("ConfiguredMeroHandler", (MeroRequestHandler,), {"manager": manager})
    return MeroWebServer((host, port), handler), manager


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    server, manager = build_server(args.host, args.port)

    host, port = server.server_address
    print(f"Mero web is ready at http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Mero web…", flush=True)
    finally:
        manager.close()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

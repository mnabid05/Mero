# Mero Web App

Mero includes a dependency-free browser interface for playing complete games
against the same native UCI engine used by desktop chess clients.

## Run locally

Build the optimized C++ engine, then start the web server:

```bash
python3 scripts/build_native.py
python3 -m webapp.server
```

Open `http://127.0.0.1:8765`. If the native binary has not been built, the
server automatically uses the Python reference engine instead.

The server accepts `--host` and `--port` options:

```bash
python3 -m webapp.server --host 127.0.0.1 --port 9000
```

## Interface

- Choose White, Black, or a random side and one of three move-time presets.
- Select squares or drag pieces; the browser only exposes legal destinations.
- Flip the board, switch among three palettes, resign, and start a new game.
- Review algebraic move notation, captures, checks, results, and active-turn time.
- Refresh the page to restore the current in-memory game while the server runs.

Keyboard shortcuts use `N` for a new game and `F` to flip the board.

## Architecture

The frontend uses semantic HTML, responsive CSS, and plain JavaScript. It sends
UCI moves to a small JSON API built on Python's standard library. `GameManager`
owns server-authoritative rules and game state. `NativeEngineClient` keeps a
thread-safe UCI subprocess alive so multiple HTTP sessions can share the Mero
engine without restarting it for every move.

The API exposes:

- `GET /api/health`
- `POST /api/games`
- `GET /api/games/{id}`
- `POST /api/games/{id}/moves`
- `POST /api/games/{id}/resign`

Game sessions are intentionally in memory: restarting the server begins a clean
session. The API validates all moves again on the server, so browser state cannot
bypass the engine's legal-move generator.

## Test

```bash
python3 -m unittest discover -s tests -v
```

The suite covers notation, state serialization, game orchestration, the HTTP
contract, native engine behavior, and move-generation correctness.

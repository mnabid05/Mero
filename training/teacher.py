"""Read exact principal-variation scores from a fixed-node teacher search."""
import re

from chess_ai.gauntlet import UCIEngine

class Teacher(UCIEngine):
    def label(self, fen: str, nodes: int):
        self._send("position fen " + fen)
        self._send(f"go nodes {nodes}")
        lines = self._read_until("bestmove", timeout=30)
        for line in reversed(lines):
            match = re.search(r"\bscore cp (-?\d+)\b", line)
            if match and "bound" not in line and " pv " in line:
                score = int(match[1])
                if abs(score) > 1600:
                    return None
                return score if fen.split()[1] == "w" else -score
        return None

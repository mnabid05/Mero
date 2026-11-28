import queue
import subprocess
import threading
import unittest
from pathlib import Path
from chess_ai.board import Board

ENGINE=Path(__file__).resolve().parents[1]/"build/native/mwahaha-engine"

@unittest.skipUnless(ENGINE.is_file(),"native build required")
class SearchControlTests(unittest.TestCase):
    def test_stop_infinite_search_and_reuse_pool(self):
        for threads in (1,3):
            with self.subTest(threads=threads), subprocess.Popen(
                [ENGINE],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1
            ) as proc:
                lines=queue.Queue()
                def collect():
                    for line in proc.stdout: lines.put(line.strip())
                reader=threading.Thread(target=collect,daemon=True)
                reader.start()
                def send(cmd):
                    proc.stdin.write(cmd+"\n")
                    proc.stdin.flush()
                def result(board):
                    report=lines.get(timeout=5)
                    self.assertTrue(report.startswith("info depth "),report)
                    moves=report.partition(" pv ")[2].split()
                    self.assertTrue(moves,report)
                    self.assertEqual(lines.get(timeout=5),"bestmove "+moves[0])
                    for move in moves: board.play_uci(move)
                try:
                    send(f"setoption name Threads value {threads}")
                    send("position startpos")
                    send("go infinite")
                    send("isready")
                    self.assertEqual(lines.get(timeout=5),"readyok")
                    send("stop")
                    result(Board.starting())
                    send("stop")  # idempotent: no duplicate bestmove
                    send("position startpos moves e2e4")
                    send("go depth 3")
                    b=Board.starting()
                    b.play_uci("e2e4")
                    result(b)
                    send("go movetime 600000")
                    send("quit")
                    self.assertEqual(proc.wait(timeout=5),0)
                finally:
                    if proc.poll() is None: proc.kill()
                    proc.wait(timeout=5)
                    reader.join(timeout=5)

    def test_eof_and_stop_in_a_mating_position(self):
        # The worker can finish this position immediately, but go infinite
        # must not block shutdown even if its mate result is already known.
        for ending in ("", "stop\n"):
            output=subprocess.run([ENGINE],input="position fen 7k/6Q1/6K1/8/8/8/8/8 b - - 0 1\ngo infinite\n"+ending,
                                  text=True,capture_output=True,check=True,timeout=5).stdout
            self.assertEqual(output.count("bestmove 0000"),1)

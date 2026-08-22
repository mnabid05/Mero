from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_native.py"
SPEC = importlib.util.spec_from_file_location("benchmark_native", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
benchmark_native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark_native)


class NativeBenchmarkTests(unittest.TestCase):
    def test_final_complete_info_line_is_parsed(self) -> None:
        output = "\n".join(
            (
                "info depth 8 score cp 15 nodes 500000 nps 1200000 time 416",
                "bestmove g1f3",
            )
        )

        self.assertEqual(
            benchmark_native.parse_final_info(output),
            {"depth": 8, "nodes": 500000, "nps": 1200000, "time_ms": 416},
        )

    def test_missing_search_report_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "complete info line"):
            benchmark_native.parse_final_info("bestmove 0000")


if __name__ == "__main__":
    unittest.main()

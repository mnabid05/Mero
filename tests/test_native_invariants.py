"""White-box regressions compiled against the native implementation."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("c++") and shutil.which("cc"), "compiler required")
class NativeInvariantTests(unittest.TestCase):
    def test_native_invariants(self):
        target = ROOT / "build" / "invariants"
        target.mkdir(parents=True, exist_ok=True)
        obj = target / "evaluation.o"
        subprocess.run(["cc", "-std=c11", "-O2", "-c", str(ROOT / "native/evaluation.c"),
                        "-o", str(obj)], check=True, timeout=60)
        binary = target / "invariants"
        subprocess.run(["c++", "-std=c++20", "-O2", "-pthread", "-Wall", "-Wextra",
                        "-Werror", str(ROOT / "tests/native_invariants.cpp"), str(obj),
                        "-o", str(binary)], check=True, timeout=120)
        subprocess.run([str(binary)], check=True, timeout=60)

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which(os.environ.get("CXX","c++")),"C++20 compiler required")
class ScreluHead(unittest.TestCase):
    def test_signed_extremes_in_all_supported_widths(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe=Path(tmp)/"check"
            for width in (256,384,512):
                for wide in (0,1):
                    with self.subTest(width=width,wide=wide):
                        subprocess.run([os.environ.get("CXX","c++"),"-std=c++20","-O3",
                          "-I",str(ROOT/"native"),"-I",str(ROOT/"tests/fixtures/screlu-head"),
                          f"-DTEST_WIDTH={width}",f"-DTEST_WIDE={wide}",
                          str(ROOT/"tests/screlu_head_extremes.cpp"),"-o",str(exe)],check=True,timeout=60)
                        subprocess.run([exe],check=True,timeout=10)

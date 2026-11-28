import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

@unittest.skipUnless(importlib.util.find_spec("numpy"), "optional training dependency")
class SupplementalPanel(unittest.TestCase):
    def test_checks_both_color_signs_and_refuses_changed_panel(self):
        from training.blind_queen_panel import assess
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"panel"; engine=Path(d)/"engine";engine.write_bytes(b"test")
            p.write_text(json.dumps({"pairs":[["a","b",1],["c","d",-1]]*75}))
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            with patch("training.blind_queen_panel.subprocess.run",return_value=SimpleNamespace(stdout="900\n0\n0\n900\n"*75)):
                result=assess(p,h,engine)
            self.assertTrue(result["passed"]); self.assertEqual(result["median_cp"],900)
            with self.assertRaisesRegex(ValueError,"panel changed"): assess(p,"wrong",engine)

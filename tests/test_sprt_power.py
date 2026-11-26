import unittest
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
from scripts.run_sprt import run
from scripts.run_sprt import require_mac_power

class PowerGateTests(unittest.TestCase):
    def test_child_failure_is_recorded_not_a_pass(self):
        # An actual child process and files, but no chess games or wall clock.
        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp)
            exe = tmp/"harness"
            exe.write_text("#!/bin/sh\nexit 3\n")
            exe.chmod(0o700)
            for name in ("candidate","baseline","book"):
                (tmp/name).write_text(name)
            args = Namespace(fastchess=exe, candidate=tmp/"candidate", baseline=tmp/"baseline",
                             book=tmp/"book", output=tmp/"run", jobs=1)
            def sha(path):
                return ("5835239f88cc2c7511b177c32392a69f3ede21819cf0616f80a7f907cd21d17e"
                        if path.name=="book" else path.name)
            with patch("scripts.run_sprt.check_power"), patch("scripts.run_sprt.digest", sha):
                with patch("builtins.print"):
                    self.assertEqual(run(args),1)
                self.assertIn('"returncode": 3',(tmp/"run/result.json").read_text())
                with self.assertRaises(FileExistsError):
                    run(args)

    def test_desktop_and_charging_laptop_can_start(self):
        require_mac_power("Now drawing from 'AC Power'")
        require_mac_power("Now drawing from 'AC Power'\n-InternalBattery-0 46%; charging")

    def test_nearly_empty_or_discharging_macs_cannot_run_matches(self):
        for status in ("Now drawing from 'Battery Power'\n-InternalBattery-0 90%",
                       "Now drawing from 'AC Power'\n-InternalBattery-0 4%; discharging",
                       "Now drawing from 'AC Power'\n-InternalBattery-0 4%; charging",
                       "Now drawing from 'AC Power'\n-InternalBattery-0 34%; discharging"):
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                require_mac_power(status)

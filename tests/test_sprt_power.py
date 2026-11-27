import unittest
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
from scripts.run_sprt import run
from scripts.run_sprt import require_mac_power
from training.large_run import await_power
from training.power_source import PowerUnavailable,require_power

class PowerGateTests(unittest.TestCase):
    def test_stale_ac_label_does_not_override_battery_controller(self):
        status="Now drawing from 'AC Power'\n-InternalBattery-0 44%; discharging"
        with self.assertRaisesRegex(PowerUnavailable,"adapter"):
            require_power(status,'  "ExternalConnected" = No')
        require_power(status,'  "ExternalConnected" = Yes\n  "ExternalChargeCapable" = Yes')
        with self.assertRaises(PowerUnavailable):
            require_power(status,clocked=True)

    def test_power_wait_clears_after_a_real_transition(self):
        with tempfile.TemporaryDirectory() as d, patch("training.large_run.time.sleep") as idle:
            root=Path(d)
            with patch("training.large_run.power",side_effect=[PowerUnavailable("unplugged"),None]):
                with patch("builtins.print"):
                    await_power(root,True)
            idle.assert_called_once_with(30)
            self.assertIn('"available"',(root/"power-state.json").read_text())

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

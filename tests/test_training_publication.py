import tempfile
import unittest
from pathlib import Path
from training.publish import unpublished


class OfflinePublication(unittest.TestCase):
    def test_interrupted_stage_is_invisible_then_retries(self):
        with tempfile.TemporaryDirectory() as d:
            final=Path(d)/"selected"
            with self.assertRaises(KeyboardInterrupt):
                with unpublished(final,"report.json") as staged:
                    staged.mkdir()
                    (staged/"weights.bin").write_bytes(b"incomplete")
                    self.assertFalse(final.exists())
                    raise KeyboardInterrupt
            self.assertFalse(final.exists())
            with unpublished(final,"report.json") as staged:
                staged.mkdir()
                (staged/"report.json").write_text("{}")
                (staged/"weights.bin").write_bytes(b"complete")
                self.assertFalse(final.exists())
            self.assertEqual((final/"weights.bin").read_bytes(),b"complete")
            with self.assertRaises(FileExistsError):
                with unpublished(final,"report.json"):
                    self.fail("would overwrite an existing artifact")

    def test_missing_manifest_or_concurrent_writer_cannot_publish(self):
        with tempfile.TemporaryDirectory() as d:
            final=Path(d)/"split"
            with self.assertRaisesRegex(ValueError,"completion manifest"):
                with unpublished(final,"split.json") as staged:
                    staged.mkdir()
                    with self.assertRaisesRegex(RuntimeError,"another writer"):
                        with unpublished(final,"split.json"):
                            self.fail("concurrent writer admitted")
            self.assertFalse(final.exists())

    def test_existing_dangling_link_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            final=Path(d)/"split"
            final.symlink_to(Path(d)/"absent")
            with self.assertRaises(FileExistsError):
                with unpublished(final,"split.json"):
                    self.fail("replaced symlink")
            self.assertTrue(final.is_symlink())

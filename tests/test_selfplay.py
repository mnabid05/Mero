import subprocess
import tempfile
import unittest
from pathlib import Path
from training.audit_selfplay import audit

ENGINE=Path(__file__).resolve().parents[1]/"build/native/mwahaha-engine"

@unittest.skipUnless(ENGINE.is_file(),"native build required")
class SelfplayTests(unittest.TestCase):
    def test_parallel_replay_determinism_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/"one",Path(tmp)/"two"
            def run(path,jobs,check=True):
                return subprocess.run([ENGINE,"datagen",path,"2","256",str(jobs),"91","active"],
                                      check=check,capture_output=True,timeout=120)
            run(a,1)
            run(b,2)
            for name in ("games.tsv","positions.bullet"):
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
            report=audit(a)
            self.assertEqual(report["completed"],2)
            self.assertGreater(report["positions"],0)
            self.assertNotEqual(run(a,1,False).returncode,0)
            blob=bytearray((b/"positions.bullet").read_bytes())
            blob[26]=3
            (b/"positions.bullet").write_bytes(blob)
            with self.assertRaisesRegex(ValueError,"WDL"):
                audit(b)

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from training.large_run import sha
from training.recover_sealed import FILES, restore_verified

class RecoverFromSeal(unittest.TestCase):
    def test_original_hashes_are_authority(self):
        with TemporaryDirectory() as d:
            root=Path(d); shard=root/"shard"; rebuilt=root/"rebuilt"
            shard.mkdir(); rebuilt.mkdir()
            for name in FILES: (rebuilt/name).write_bytes(name.encode())
            seal={name:sha(rebuilt/name) for name in FILES}
            (shard/"verified.json").write_text(json.dumps(seal))
            (shard/"games.tsv").write_bytes(b"different")
            with self.assertRaisesRegex(ValueError,"existing evidence differs"):
                restore_verified(shard,rebuilt)
            self.assertFalse((shard/"COMPLETE.json").exists())
            self.assertEqual((shard/"games.tsv").read_bytes(),b"different")
            (shard/"games.tsv").write_bytes(b"games.tsv")
            (rebuilt/"positions.bullet").write_bytes(b"different")
            with self.assertRaisesRegex(ValueError,"regeneration differs"):
                restore_verified(shard,rebuilt)
            self.assertFalse((shard/"positions.bullet").exists())
            (rebuilt/"positions.bullet").write_bytes(b"positions.bullet")
            self.assertEqual(set(restore_verified(shard,rebuilt)),{"COMPLETE.json","positions.bullet"})
            self.assertEqual(restore_verified(shard,rebuilt),[])
            self.assertEqual({name:sha(shard/name) for name in FILES},seal)

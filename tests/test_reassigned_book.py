import json
from pathlib import Path
import tempfile
import unittest
from scripts.scale_campaign import ensure_exclusive_book
from training.large_run import sha

class BookReservation(unittest.TestCase):
    def test_no_reuse_even_without_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);book=root/"book.epd";book.write_bytes(b"opening")
            first=root/"search";second=root/"other"
            ensure_exclusive_book(first,book)
            p=first/"sprt";p.mkdir(parents=True)
            with self.assertRaises(FileNotFoundError): ensure_exclusive_book(second,book)
            (p/"inputs.json").write_text(json.dumps({"sha256":{"book":sha(book)}}))
            ensure_exclusive_book(first,book)
            with self.assertRaisesRegex(ValueError,"already been played"): ensure_exclusive_book(second,book)

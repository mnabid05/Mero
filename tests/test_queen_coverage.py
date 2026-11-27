import struct
import tempfile
import unittest
from pathlib import Path

try:
    from training.queen_coverage import coverage
except ModuleNotFoundError as e:
    if e.name != "numpy": raise
    coverage = None

@unittest.skipIf(coverage is None, "requires numpy")
class QueenCoverage(unittest.TestCase):
    def row(self, pcs):
        # Deliberately nonzero padding nibbles, including an odd-piece tail.
        packed = bytearray([0xff]*16)
        for i, pc in enumerate(pcs):
            j = 4*(i%2)
            packed[i//2] = (packed[i//2] & ~(15<<j)) | pc<<j
        return struct.pack("<Q16s8x", (1<<len(pcs))-1, bytes(packed))

    def test_other_kinds_sides_and_padding(self):
        pcs = [[5,13,4], [5,13,12,0,8], [5,13,4,0], [5,13,4,12], [5,13,4,1,10]]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"rows.bullet"
            path.write_bytes(b"".join(map(self.row, pcs)))
            v = coverage(path)
            self.assertEqual((v["rows"],v["one_queen_difference"],v["mover_ahead"],v["mover_behind"]), (5,4,1,1))
            self.assertEqual(v["otherwise_equal_by_output_bucket"], [2,0,0,0,0,0,0,0])
            path.write_bytes(self.row([5,13,7]))
            with self.assertRaisesRegex(ValueError, "invalid piece"): coverage(path)

import importlib.util
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("numpy"),"optional training dependency")
class LayoutCounts(unittest.TestCase):
    def test_repeated_layout_and_changed_label_count_only_once(self):
        from training.layout_diversity import count_layouts
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            # Deliberately include NUL bytes, a byte above 127, and duplicates
            # within AND across runs. Preserve bytes through sorting/merging.
            a,b,c,d=(bytes([i])+bytes(23) for i in (0,1,128,255))
            def save(p,rows):
                (root/p).write_bytes(b"".join(k+bytes([v])*8 for k,v in rows))
                return root/p
            x=save("a",[(a,1),(a,2),(b,1),(c,1),(d,1)])
            y=save("b",[(c,0),(a,9),(d,7)])
            self.assertEqual(count_layouts([x,y],root,chunk_rows=3),(8,4))
            self.assertEqual(set(root.iterdir()),{x,y})

    def test_incomplete_record_cannot_be_counted(self):
        from training.layout_diversity import count_layouts
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=root/"broken";p.write_bytes(bytes(31))
            with self.assertRaisesRegex(ValueError,"partial"):
                count_layouts([p],root,chunk_rows=3)

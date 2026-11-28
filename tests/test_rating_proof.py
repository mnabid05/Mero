import unittest
from scripts.rate_standalone import confirmed

class RatingProof(unittest.TestCase):
    def example(self,book):
        return {"decision":"H1","sha256":{"book":book,"baseline":"release","fastchess":"h","candidate":"c"}}
    def test_requires_identical_candidate_on_two_separate_books(self):
        a=self.example("a");b=self.example("b")
        self.assertTrue(confirmed(a,b,"c"))
        for bad in (a,{**b,"decision":"inconclusive"}, {**b,"sha256":{**b["sha256"],"baseline":"other"}},
                    {**b,"sha256":{**b["sha256"],"candidate":"other"}}):
            with self.assertRaises(ValueError): confirmed(a,bad,"c")

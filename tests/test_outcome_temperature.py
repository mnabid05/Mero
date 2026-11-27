import importlib.util
import unittest

@unittest.skipUnless(importlib.util.find_spec("numpy"),"optional training dependency")
class SearchOutcomeLink(unittest.TestCase):
    def test_recovers_known_temperature_without_piece_features(self):
        import numpy as np
        from training.outcome_temperature import estimate,logloss
        x=np.array([-800.,-200.,0.,200.,800.])
        n=np.full(x.shape,20000)
        h=x,n,n/(1+np.exp(-x/190))
        self.assertAlmostEqual(estimate(h),190,places=7)
        self.assertLess(logloss(h,estimate(h)),logloss(h,400))
        with self.assertRaisesRegex(ValueError,"degenerate"):
            estimate((x,n,n/2))

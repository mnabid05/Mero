import importlib.util
import unittest

@unittest.skipUnless(importlib.util.find_spec("torch"), "requires optional torch environment")
class ModelTests(unittest.TestCase):
    def test_reflection_negates_prediction(self):
        import torch
        from training.model import MeroNet
        model = MeroNet(8)
        a = torch.tensor([[0, 10, 45]])
        b = torch.tensor([[400, 383, 29]])
        prior = torch.tensor([75.0])
        torch.testing.assert_close(model(a, b, prior), -model(b, a, -prior))

    def test_export_rejects_overflow(self):
        import torch
        from training.model import MeroNet
        from training.quantize import quantize
        model = MeroNet(8)
        with torch.no_grad():
            model.features.weight.fill_(10)
        with self.assertRaisesRegex(ValueError, "int16"):
            quantize(model)

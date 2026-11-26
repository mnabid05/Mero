import importlib.util
import unittest
from pathlib import Path
from training.screlu_wire import unpack, pack, COUNTS

class EnvelopeTests(unittest.TestCase):
    def test_format_rejects_short_payload(self):
        with self.assertRaises(ValueError):
            unpack(b"MRSCREL1")

    def test_checksum_and_lane_overflow(self):
        import array
        rows=[array.array("h",[0])*n for n in COUNTS]
        blob=bytearray(pack(rows))
        blob[-1]^=1
        with self.assertRaisesRegex(ValueError,"checksum"):
            unpack(blob)
        rows[0][0]=1024
        with self.assertRaisesRegex(ValueError,"unsafe"):
            unpack(pack(rows))

@unittest.skipUnless(importlib.util.find_spec("torch"), "training dependency")
class ModelTests(unittest.TestCase):
    def test_warm_start_is_material_plus_legacy_half_residual(self):
        import torch
        from training.export import load_model
        from training.screlu import Network
        from training.screlu_data import encode
        from chess_ai.board import Board
        legacy=load_model(Path(__file__).resolve().parents[1]/"training/checkpoints/mero-7.pt")
        net=Network()
        net.warm_start(legacy)
        fens=["3qk3/3r4/8/8/8/1B6/8/4K3 b - - 0 1",
              "7k/2b5/4p3/3P4/3N4/8/8/R3K3 w - - 0 1"]
        mat=dict(zip("pnbrqk",(100,325,335,500,975,0)))
        for fen in fens:
            (a,b),_,sign=encode(fen)
            a,b=torch.tensor([a]),torch.tensor([b])
            material=sum((1 if p.isupper() else -1)*mat[p.lower()] for _,p in Board.from_fen(fen).pieces())
            expect=material*sign+legacy(a,b,torch.zeros(1))*0.5
            torch.testing.assert_close(net(a,b),expect,rtol=0,atol=0.01)

    def test_qat_gradient_reaches_transformer(self):
        import torch
        from training.screlu import Network
        net=Network()
        with torch.no_grad(): net.head.fill_(0.125)
        output=net(torch.tensor([[1,2,3]]),torch.tensor([[401,402,403]]),qat=True)
        output.sum().backward()
        self.assertGreater(net.embed.weight.grad.abs().sum().item(),0)

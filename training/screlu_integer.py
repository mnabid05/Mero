"""Executable integer inference specification for the C++ parity gate."""
import torch
from .screlu import WIDTH, QA, QB, SCALE
from .features import PADDING
from .screlu_wire import pack, unpack

def quantized(model, residual=False):
    params = (model.embed.weight[:PADDING],model.bias,model.head,model.out_bias)
    rows = []
    for weight,scale in zip(params,(QA,QA,QB,QA*QB),strict=True):
        q = torch.round(weight.detach().cpu()*scale)
        if not q.isfinite().all() or q.min() < -32768 or q.max() > 32767:
            raise ValueError("cannot represent weight as int16")
        rows.append(q.to(torch.int16).flatten().tolist())
    blob = pack(rows,residual=residual)
    unpack(blob)  # Reject unsafe accumulator bounds before publication.
    return blob

class Reference:
    def __init__(self, blob):
        ft,bias,heads,out = unpack(blob)
        as64 = lambda x: torch.tensor(x.tolist(),dtype=torch.int64)
        self.ft = torch.cat([as64(ft).view(PADDING,WIDTH),torch.zeros(1,WIDTH,dtype=torch.int64)])
        self.bias, self.head, self.out = as64(bias), as64(heads).view(8,2*WIDTH), as64(out)

    def __call__(self, stm, other):
        def side(ids):
            return (self.ft[ids].sum(1)+self.bias).clamp(0,QA).square()
        bucket = (((stm != PADDING).sum(1)-2)//4).clamp(0,7)
        z = torch.cat([side(stm),side(other)],dim=1)
        dot = (z*self.head[bucket]).sum(1)+self.out[bucket]*QA
        return torch.div(SCALE*dot,QA*QA*QB,rounding_mode="trunc")

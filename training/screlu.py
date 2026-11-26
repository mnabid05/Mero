"""Standalone two-perspective evaluator. Features use Mero's a8=0 convention."""
import torch
from torch import nn

from .features import FEATURES, PADDING

WIDTH, BUCKETS, QA, QB, SCALE = 512, 8, 255, 64, 400

class Network(nn.Module):
    def __init__(self, width=WIDTH):
        super().__init__()
        self.embed = nn.EmbeddingBag(FEATURES+1, width, mode="sum", padding_idx=PADDING)
        self.bias = nn.Parameter(torch.full((width,), 0.35))
        self.head = nn.Parameter(torch.zeros(BUCKETS, 2*width))
        self.out_bias = nn.Parameter(torch.zeros(BUCKETS))
        with torch.no_grad():
            self.embed.weight.normal_(0,0.018)
            self.embed.weight[PADDING].zero_()

    def forward(self, stm, other, qat=False):
        count = (stm != PADDING).sum(1)
        buckets = ((count-2)//4).clamp(0,BUCKETS-1)
        def weight(w,scale):
            if not qat: return w
            # Straight-through gradient: optimize the deployed lattice,
            # not a float network that is rounded only after training.
            rounded = torch.round(w.detach()*scale)/scale
            return w+(rounded-w).detach()
        ft=weight(self.embed.weight,QA)
        bias=weight(self.bias,QA)
        def side(ids):
            acc=nn.functional.embedding_bag(ids,ft,mode="sum",padding_idx=PADDING)
            return (acc+bias).clamp(0,1).square()
        hidden = torch.cat((side(stm), side(other)), dim=1)
        return SCALE*((hidden*weight(self.head[buckets],QB)).sum(1)+weight(self.out_bias[buckets],QA*QB))

    @torch.no_grad()
    def warm_start(self, legacy):
        """Transplant the deployed half-weight residual and initialize material.

        clip(x)^2 - clip(1-x)^2 = 2*clip(x)-1. Subtracting opposite
        perspectives cancels the constant, so two SCReLU lanes reproduce each
        old clipped-linear lane exactly before quantization. Remaining lanes
        can learn new interactions. No C evaluator is called by this model.
        """
        h = legacy.output.in_features
        if self.bias.numel()!=512: raise ValueError("legacy warm start is not used by standalone networks")
        if 2*h + 10 > WIDTH:
            raise ValueError("legacy model is too wide")
        self.head.zero_()
        self.out_bias.zero_()
        self.embed.weight[:FEATURES,:h].copy_(legacy.features.weight[:FEATURES])
        self.embed.weight[:FEATURES,h:2*h].copy_(-legacy.features.weight[:FEATURES])
        self.bias[:h].copy_(legacy.bias)
        self.bias[h:2*h].copy_(1-legacy.bias)
        readout = legacy.output.weight.flatten() * (512*0.5/(2*SCALE))
        self.head[:, :h] = readout
        self.head[:, h:2*h] = -readout
        # Complementary lanes also make a linear material-count difference.
        for piece, value in enumerate((100,325,335,500,975)):
            i = 2*h + 2*piece
            self.embed.weight[:FEATURES,i:i+2].zero_()
            for p,sign in ((piece,1),(piece+6,-1)):
                self.embed.weight[p*64:(p+1)*64,i] = sign/32
                self.embed.weight[p*64:(p+1)*64,i+1] = -sign/32
            self.bias[i:i+2] = 0.5
            self.head[:,i] = 8*value/SCALE
            self.head[:,i+1] = -8*value/SCALE
        self.head[:,WIDTH:] = -self.head[:,:WIDTH].clone()
        self.embed.weight[PADDING].zero_()

import torch
from torch import nn
from .features import FEATURES, PADDING

class MeroNet(nn.Module):
    def __init__(self, width=64):
        super().__init__()
        self.features = nn.Embedding(FEATURES + 1, width, padding_idx=PADDING)
        self.bias = nn.Parameter(torch.full((width,), 0.3))
        self.output = nn.Linear(width, 1, bias=False)
        nn.init.normal_(self.features.weight, std=0.025)
        with torch.no_grad():
            self.features.weight[PADDING].zero_()

    def side(self, ids):
        return (self.features(ids).sum(1) + self.bias).clamp(0, 1)

    def forward(self, white, black, prior):
        difference = self.side(white) - self.side(black)
        return prior + 512 * self.output(difference).squeeze(-1)

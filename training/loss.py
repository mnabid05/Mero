import torch
from torch.nn.functional import smooth_l1_loss

def objective(prediction, target):
    # Smooth centipawn errors while preserving a useful gradient in drawn positions.
    centipawns = smooth_l1_loss(prediction / 200, target / 200, beta=0.5)
    probability = (torch.sigmoid(prediction / 220) - torch.sigmoid(target / 220)).square().mean()
    return centipawns + 2 * probability

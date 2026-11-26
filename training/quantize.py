"""Integer contract shared by the header exporter and native inference."""
import torch

INPUT_SCALE = 256
OUTPUT_SCALE = 1024

def quantize(model):
    q = lambda tensor, scale: (tensor.detach().cpu() * scale).round().to(torch.int64)
    features = q(model.features.weight[:-1], INPUT_SCALE)
    bias = q(model.bias, INPUT_SCALE)
    head = q(model.output.weight.squeeze(0), OUTPUT_SCALE)
    bound = features.abs().amax(0) * 32 + bias.abs()
    if bound.max().item() > 32767 or head.abs().max().item() > 32767:
        raise ValueError("model exceeds native int16 representation")
    if (head.abs().sum() * INPUT_SCALE).item() >= 2**31:
        raise ValueError("head exceeds native dot-product representation")
    return features.tolist(), bias.tolist(), head.tolist()

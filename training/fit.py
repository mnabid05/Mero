import copy
import math
import torch
from .loss import objective
from .model import MeroNet

def fit(train, valid, width, epochs, seed, batch=256):
    torch.manual_seed(seed)
    model = MeroNet(width)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=0.01)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs, eta_min=0.00015)
    best_loss = math.inf
    best_state = None
    history = []
    for epoch in range(epochs):
        model.train()
        for ids in torch.randperm(len(train[0])).split(batch):
            white, black, prior, target = (x[ids] for x in train)
            optimizer.zero_grad(set_to_none=True)
            loss = objective(model(white, black, prior), target)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            optimizer.step()
        schedule.step()
        model.eval()
        with torch.no_grad():
            preds = torch.cat([model(*(x[i:i+batch] for x in valid[:3]))
                               for i in range(0, len(valid[0]), batch)])
            valid_loss = objective(preds, valid[3]).item()
            history.append(dict(epoch=epoch+1, loss=valid_loss,
                                mae_cp=(preds-valid[3]).abs().mean().item()))
        if valid_loss < best_loss:
            best_loss = valid_loss
            best_state = copy.deepcopy(model.state_dict())
        if (epoch + 1) % 10 == 0:
            print(width, history[-1], flush=True)
    if best_state is None:
        raise ValueError("training produced no finite checkpoint")
    model.load_state_dict(best_state)
    return model, history

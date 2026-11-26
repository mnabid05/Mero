"""Train an isolated, standalone SCReLU candidate on Mero's existing labels."""
import argparse
import hashlib
import json
from pathlib import Path
import torch
from .export import load_model
from .loss import objective
from .screlu import Network, WIDTH
from .screlu_data import load
from .screlu_integer import Reference, quantized

@torch.no_grad()
def metrics(call, data):
    a,b,target,_ = data
    pred = torch.cat([call(a[i:i+128],b[i:i+128]) for i in range(0,len(a),128)]).float()
    return dict(loss=objective(pred,target).item(),mae_cp=(pred-target).abs().mean().item())

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("database",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--legacy",type=Path,default=Path("training/checkpoints/mero-7.pt"))
    p.add_argument("--epochs",type=int,default=12)
    p.add_argument("--train-limit",type=int,default=0)
    p.add_argument("--valid-limit",type=int,default=0)
    p.add_argument("--threads",type=int,default=1)
    p.add_argument("--qat-start",type=int,default=2,help="first quantization-aware epoch; 0 disables")
    p.add_argument("--seed",type=int,default=1701)
    args = p.parse_args()
    if min(args.epochs,args.threads)<1 or min(args.train_limit,args.valid_limit,args.qat_start)<0:
        p.error("invalid training budget")
    args.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    train,valid,held = load(args.database,args.seed,args.train_limit,args.valid_limit)
    legacy = load_model(args.legacy)
    model = Network()
    model.warm_start(legacy)
    start = 2*legacy.output.in_features
    fixed = slice(start,start+10)
    other_fixed = slice(WIDTH+start,WIDTH+start+10)
    # The material basis is an exact linear count before quantization. Learn
    # positional corrections without allowing a noisy batch to destroy it.
    opt = torch.optim.AdamW(model.parameters(),lr=0.0005,weight_decay=0)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt,args.epochs,eta_min=0.00005)
    report = dict(seed=args.seed,torch=str(torch.__version__),threads=args.threads,qat_start=args.qat_start,
                  warm_start_sha256=hashlib.sha256(args.legacy.read_bytes()).hexdigest(),
                  train_rows=len(train[0]),valid_rows=len(valid[0]),held_openings=held,
                  train_fens_sha256=hashlib.sha256("\n".join(train[3]).encode()).hexdigest(),
                  valid_fens_sha256=hashlib.sha256("\n".join(valid[3]).encode()).hexdigest(),
                  history=[])
    def record(epoch):
        blob = quantized(model)
        integer = metrics(Reference(blob),valid)
        row = dict(epoch=epoch,fp32=metrics(model,valid),integer=integer)
        report["history"].append(row)
        if epoch==0 or integer["loss"] < report["best_loss"]:
            report.update(best_loss=integer["loss"],best_epoch=epoch,
                          net_sha256=hashlib.sha256(blob).hexdigest())
            (args.output/"weights.bin").write_bytes(blob)
            torch.save(model.state_dict(),args.output/"weights.pt")
        (args.output/"report.json").write_text(json.dumps(report,indent=2)+"\n")
        print(epoch,integer,flush=True)
    record(0)
    a,b,y,_ = train
    for epoch in range(1,args.epochs+1):
        for idx in torch.randperm(len(a)).split(256):
            opt.zero_grad(set_to_none=True)
            loss = objective(model(a[idx],b[idx],qat=0<args.qat_start<=epoch),y[idx])
            loss.backward()
            model.embed.weight.grad[:,fixed]=0
            model.bias.grad[fixed]=0
            model.head.grad[:,fixed]=0
            model.head.grad[:,other_fixed]=0
            torch.nn.utils.clip_grad_norm_(model.parameters(),2.0)
            opt.step()
        sched.step()
        record(epoch)
        if epoch-report["best_epoch"] >= 4: break

if __name__ == "__main__":
    main()

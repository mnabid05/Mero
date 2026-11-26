"""Fit a bounded, side-antisymmetric correction to the frozen native Mero 7."""
import argparse
import hashlib
import json
from pathlib import Path
import torch
from torch.nn import functional as F
from .audit_screlu import ask
from .screlu import Network, WIDTH
from .screlu_data import load
from .screlu_integer import Reference, quantized

@torch.no_grad()
def project(net):
    left,right=net.head.chunk(2,dim=1)
    tied=(left-right)*0.5
    left.copy_(tied)
    right.copy_(-tied)
    net.out_bias.zero_()

def targets(control,data):
    _,_,teacher,fens=data
    tags=ask(control,"--quiet-prior-scores",fens)
    if len(tags)!=len(fens) or any(len(r)!=2 for r in tags):
        raise ValueError("expected quiet and static-score labels from the standalone Mero 7 control")
    scores,quiet=torch.tensor(tags).T
    # Saturating distillation target; in tactical positions anchor predictions
    # to the trusted search evaluator rather than fitting a noisy deep score.
    correction=(teacher-scores).clamp(-160,160)*0.4*quiet
    return scores,quiet.bool(),correction

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("database","control","transformer","output"):
        p.add_argument(n,type=Path)
    p.add_argument("--epochs",type=int,default=8)
    p.add_argument("--threads",type=int,default=2)
    p.add_argument("--quiet-only",action="store_true",
                   help="discard nonquiet training positions; select on quiet validation corrections")
    args=p.parse_args()
    if min(args.epochs,args.threads)<1: p.error("positive training budget required")
    args.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(args.threads)
    torch.manual_seed(1701)
    train,valid,held=load(args.database,1701)
    prior_train,qtrain,ytrain=targets(args.control,train)
    prior,qvalid,yvalid=targets(args.control,valid)
    del prior_train
    net=Network()
    net.load_state_dict(torch.load(args.transformer,weights_only=True,map_location="cpu"))
    with torch.no_grad():
        net.head.zero_()
        net.out_bias.zero_()
    opt=torch.optim.AdamW(net.parameters(),lr=0.0003,weight_decay=0)
    sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,args.epochs,eta_min=0.00003)
    report=dict(seed=1701,threads=args.threads,torch=str(torch.__version__),quiet_only=args.quiet_only,
                train_rows=len(qtrain),train_quiet=int(qtrain.sum()),valid_rows=len(qvalid),
                valid_quiet=int(qvalid.sum()),held_openings=held,
                valid_fens_sha256=hashlib.sha256("\n".join(valid[3]).encode()).hexdigest(),
                control_sha256=hashlib.sha256(args.control.read_bytes()).hexdigest(),
                transformer_sha256=hashlib.sha256(args.transformer.read_bytes()).hexdigest(),history=[])
    @torch.no_grad()
    def record(epoch):
        a,b,teacher,_=valid
        blob=quantized(net,residual=True)
        ref=Reference(blob)
        delta=torch.cat([ref(a[i:i+64],b[i:i+64]) for i in range(0,len(a),64)]).clamp(-64,64)
        delta=delta*((a!=768).sum(1)>3)
        active=qvalid if args.quiet_only else torch.ones_like(qvalid)
        loss=F.smooth_l1_loss(delta[active].float()/40,yvalid[active]/40,beta=0.5).item()
        row=dict(epoch=epoch,bounded_target_loss=loss,teacher_mae_cp=(prior+delta-teacher).abs().mean().item(),
                 mean_abs_delta_cp=delta.abs().float().mean().item())
        report["history"].append(row)
        if epoch==0 or loss<report["best_loss"]:
            report.update(best_loss=loss,best_epoch=epoch,net_sha256=hashlib.sha256(blob).hexdigest())
            (args.output/"weights.bin").write_bytes(blob)
            torch.save(net.state_dict(),args.output/"weights.pt")
        (args.output/"report.json").write_text(json.dumps(report,indent=2)+"\n")
        print(row,flush=True)
    record(0)
    a,b,_,_=train
    if args.quiet_only:
        a,b,ytrain=a[qtrain],b[qtrain],ytrain[qtrain]
    for epoch in range(1,args.epochs+1):
        for ix in torch.randperm(len(a)).split(256):
            opt.zero_grad(set_to_none=True)
            pred=net(a[ix],b[ix],qat=True)
            loss=F.smooth_l1_loss(pred/40,ytrain[ix]/40,beta=0.5)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(),2.0)
            opt.step()
            project(net)
        sched.step()
        record(epoch)
        if epoch-report["best_epoch"]>=3: break

if __name__=="__main__":
    main()

"""Translate Bullet Chess768 a1 inputs to Mero a8; select deployed integers by held-out loss."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import numpy as np
import torch
from .screlu import Network
from .screlu_integer import Reference
from .screlu_wire import COUNTS, pack, unpack
from .screlu_data import encode
from .features import flip, PADDING

def file_hash(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def convert(raw):
    length=sum(COUNTS)*2
    pad=(-length)%64
    if len(raw)!=length+pad or raw[length:]!=(b"bullet"*11)[:pad]:
        raise ValueError("unexpected Bullet export length or padding")
    ft,bias,head,out=np.split(np.frombuffer(raw[:length],dtype="<i2"),np.cumsum(COUNTS)[:-1])
    ft=ft.reshape(768,512)[np.arange(768)^56].reshape(-1)
    blob=pack([ft,bias,head,out])
    unpack(blob)
    return blob

@torch.no_grad()
def float_model(raw):
    values=np.frombuffer(raw,dtype="<f4")
    if len(values)!=sum(COUNTS): raise ValueError("unexpected float export length")
    ft,bias,head,out=np.split(values,np.cumsum(COUNTS)[:-1])
    m=Network()
    def tensor(a): return torch.from_numpy(a.copy())
    m.embed.weight[:768].copy_(tensor(ft.reshape(768,512)[np.arange(768)^56]))
    m.embed.weight[768].zero_()
    m.bias.copy_(tensor(bias))
    m.head.copy_(tensor(head.reshape(1024,8).T))
    m.out_bias.copy_(tensor(out))
    return m

def prepare(data):
    x,y,cp,wdl=[],[],[],[]
    if len(data)%32 or not data: raise ValueError("expected nonempty whole Bullet records")
    for occ,pcs,score,result in struct.iter_unpack("<Q16shB5x",data):
        stm=[]
        while occ:
            sq=(occ&-occ).bit_length()-1
            n=len(stm)
            pc=(pcs[n//2]>>(4*(n%2)))&15
            stm.append(((pc&7)+(6 if pc&8 else 0))*64+(sq^56))
            occ&=occ-1
        if not 2<=len(stm)<=32 or result>2: raise ValueError("bad record")
        other=list(map(flip,stm))
        pad=[PADDING]*(32-len(stm))
        x.append(stm+pad); y.append(other+pad)
        cp.append(score); wdl.append(result/2)
    return torch.tensor(x),torch.tensor(y),torch.tensor(cp),torch.tensor(wdl)

def select(directory,split,out,backend):
    meta=json.loads((split/"split.json").read_text())
    for name in ("train","valid"):
        if file_hash(split/(name+".bullet"))!=meta["groups"][name]["sha256"]:
            raise ValueError("split fingerprint changed")
    x,y,cp,wdl=prepare((split/"valid.bullet").read_bytes())
    mixed=0.35*wdl+0.65*torch.sigmoid(cp/400)
    checkpoints=sorted(directory.glob("mero-bullet-*"),key=lambda p:int(p.name.split("-")[-1]))
    if not checkpoints: raise ValueError("no saved checkpoints")
    net=float_model((checkpoints[-1]/"raw.bin").read_bytes())
    errors=[]
    with torch.no_grad():
        for line in (directory/"final-float-parity.tsv").read_text().splitlines():
            fen,expected=line.split("\t")
            (a,b),_,_=encode(fen)
            actual=net(torch.tensor([a]),torch.tensor([b])).item()
            errors.append(abs(actual-float(expected)))
    if len(errors)<16 or max(errors)>0.1: raise ValueError(f"float mapping failed: {errors}")
    report=dict(split=meta,backend=f"Bullet/{backend}",bullet_revision="5d70177680437b7c0ddf958bd4722d95afa78b0c",
                evaluation="minimum deployed mixed-target MSE on whole-game validation split; not Elo",
                float_probe_max_error_cp=max(errors),float_probes=len(errors),checkpoints=[])
    best=float("inf")
    for path in checkpoints:
        blob=convert((path/"quantised.bin").read_bytes())
        ref=Reference(blob)
        scores=torch.cat([ref(x[i:i+32],y[i:i+32]) for i in range(0,len(x),32)])
        prob=torch.sigmoid(scores/400)
        loss=(prob-mixed).square().mean().item()
        row=dict(superbatch=int(path.name.split("-")[-1]),mixed_mse=loss,
                 outcome_brier=(prob-wdl).square().mean().item(),mae_search_cp=(scores-cp).abs().float().mean().item())
        report["checkpoints"].append(row)
        if loss<best:
            best,chosen,chosen_blob=loss,path,blob
    out.mkdir(parents=True,exist_ok=False)
    (out/"weights.bin").write_bytes(chosen_blob)
    torch.save(float_model((chosen/"raw.bin").read_bytes()).state_dict(),out/"weights.pt")
    report.update(selected=chosen.name,net_sha256=file_hash(out/"weights.bin"),
                  upstream_quantised_sha256=file_hash(chosen/"quantised.bin"))
    (out/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("checkpoints","split","out"): p.add_argument(k,type=Path)
    p.add_argument("--backend",required=True,choices=("Metal","CUDA","ROCm"))
    a=p.parse_args()
    torch.set_num_threads(1)
    print(json.dumps(select(a.checkpoints,a.split,a.out,a.backend),indent=2))

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
from .screlu_wire import counts, pack, unpack
from .screlu_data import encode
from .features import flip, PADDING
from .publish import unpublished

def file_hash(p):
    with p.open("rb") as stream: return hashlib.file_digest(stream,"sha256").hexdigest()

def convert(raw,width=512):
    sizes=counts(width)
    length=sum(sizes)*2
    pad=(-length)%64
    if len(raw)!=length+pad or raw[length:]!=(b"bullet"*11)[:pad]:
        raise ValueError("unexpected Bullet export length or padding")
    ft,bias,head,out=np.split(np.frombuffer(raw[:length],dtype="<i2"),np.cumsum(sizes)[:-1])
    ft=ft.reshape(768,width)[np.arange(768)^56].reshape(-1)
    blob=pack([ft,bias,head,out],width=width)
    unpack(blob)
    return blob

@torch.no_grad()
def float_model(raw,width=512):
    values=np.frombuffer(raw,dtype="<f4")
    sizes=counts(width)
    if len(values)!=sum(sizes): raise ValueError("unexpected float export length")
    ft,bias,head,out=np.split(values,np.cumsum(sizes)[:-1])
    m=Network(width)
    def tensor(a): return torch.from_numpy(a.copy())
    m.embed.weight[:768].copy_(tensor(ft.reshape(768,width)[np.arange(768)^56]))
    m.embed.weight[768].zero_()
    m.bias.copy_(tensor(bias))
    m.head.copy_(tensor(head.reshape(2*width,8).T))
    m.out_bias.copy_(tensor(out))
    return m

def prepare(data):
    x,y,cp,wdl=[],[],[],[]
    if len(data)%32 or not data: raise ValueError("expected nonempty whole Bullet records")
    for occ,pcs,score,result in struct.iter_unpack("<Q16shB5x",data):
        if not 2<=occ.bit_count()<=32 or result>2: raise ValueError("bad board or WDL")
        stm=[]
        while occ:
            sq=(occ&-occ).bit_length()-1
            n=len(stm)
            pc=(pcs[n//2]>>(4*(n%2)))&15
            if (pc&7)>5: raise ValueError("unknown Bullet piece")
            stm.append(((pc&7)+(6 if pc&8 else 0))*64+(sq^56))
            occ&=occ-1
        other=list(map(flip,stm))
        pad=[PADDING]*(32-len(stm))
        x.append(stm+pad); y.append(other+pad)
        cp.append(score); wdl.append(result/2)
    return torch.tensor(x),torch.tensor(y),torch.tensor(cp),torch.tensor(wdl)

def select(directory,split,out,backend):
    with unpublished(out,"report.json") as staging:
        return _select(directory,split,staging,backend)

def _select(directory,split,out,backend):
    meta=json.loads((split/"split.json").read_text())
    for name in ("train","valid"):
        if file_hash(split/(name+".bullet"))!=meta["groups"][name]["sha256"]:
            raise ValueError("split fingerprint changed")
    x,y,cp,wdl=prepare((split/"valid.bullet").read_bytes())
    recipe_path=directory/"recipe.json"
    recipe=json.loads(recipe_path.read_text()) if recipe_path.exists() else dict(width=512,wdl_weight=0.35)
    width,weight=recipe["width"],recipe["wdl_weight"]
    if "train_rows" in recipe and recipe["train_rows"]!=meta["groups"]["train"]["positions"]:
        raise ValueError("trainer and split record counts disagree")
    mixed=weight*wdl+(1-weight)*torch.sigmoid(cp/400)
    checkpoints=sorted(directory.glob("mero-bullet-*"),key=lambda p:int(p.name.split("-")[-1]))
    if not checkpoints: raise ValueError("no saved checkpoints")
    net=float_model((checkpoints[-1]/"raw.bin").read_bytes(),width)
    errors=[]
    with torch.no_grad():
        for line in (directory/"final-float-parity.tsv").read_text().splitlines():
            fen,expected=line.split("\t")
            (a,b),_,_=encode(fen)
            actual=net(torch.tensor([a]),torch.tensor([b])).item()
            errors.append(abs(actual-float(expected)))
    if len(errors)<16 or max(errors)>0.1: raise ValueError(f"float mapping failed: {errors}")
    report=dict(split=meta,recipe=recipe,backend=f"Bullet/{backend}",bullet_revision="5d70177680437b7c0ddf958bd4722d95afa78b0c",
                evaluation="minimum deployed mixed-target MSE on whole-game validation split; not Elo",
                float_probe_max_error_cp=max(errors),float_probes=len(errors),checkpoints=[])
    best=float("inf")
    for path in checkpoints:
        blob=convert((path/"quantised.bin").read_bytes(),width)
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
    torch.save(float_model((chosen/"raw.bin").read_bytes(),width).state_dict(),out/"weights.pt")
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

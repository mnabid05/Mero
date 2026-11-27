"""Learn the score→outcome sigmoid temperature from training labels alone, never from a piece probe."""
import argparse
import json
from pathlib import Path
import hashlib
import numpy as np

def histogram(path):
    counts=np.zeros(65536,dtype=np.int64); sums=np.zeros(65536,dtype=np.int64)
    h=hashlib.sha256()
    with path.open("rb") as stream:
        while raw:=stream.read(32*65536):
            if len(raw)%32: raise ValueError("truncated record")
            h.update(raw)
            scores=np.ndarray((len(raw)//32,),dtype="<i2",buffer=raw,offset=24,strides=(32,)).astype(np.int32)
            wdl=np.ndarray(scores.shape,dtype="u1",buffer=raw,offset=26,strides=(32,))
            if np.any(wdl>2): raise ValueError("invalid outcome")
            counts+=np.bincount(scores+32768,minlength=65536)
            sums+=np.bincount(scores+32768,weights=wdl,minlength=65536).astype(np.int64)
    active=counts>0
    if not active.any(): raise ValueError("empty corpus")
    return (np.arange(-32768,32768,dtype=float)[active],counts[active],sums[active]/2),h.hexdigest()

def estimate(hist):
    x,count,sum_y=hist
    # Intercept fixed at zero for color antisymmetry. The derivative of the
    # fractional-label Bernoulli log loss is monotone in inverse temperature.
    def grad(b):
        return np.sum(x*(count/(1+np.exp(-np.clip(b*x,-60,60)))-sum_y))
    lo,hi=0.,1.
    if grad(lo)>=0 or grad(hi)<=0: raise ValueError("unidentifiable or degenerate slope")
    for _ in range(64):
        mid=(lo+hi)/2
        if grad(mid)>0: hi=mid
        else: lo=mid
    return 2/(lo+hi)

def logloss(hist,t):
    x,n,y=hist
    z=x/t
    return float(np.sum(n*np.logaddexp(0.,z)-y*z)/n.sum())

def measure(split):
    meta=json.loads((split/"split.json").read_text())
    hist={}
    for name in ("train","valid"):
        hist[name],digest=histogram(split/(name+".bullet"))
        if digest!=meta["groups"][name]["sha256"] or int(hist[name][1].sum())!=meta["groups"][name]["positions"]:
            raise ValueError("split does not match manifest")
    t=estimate(hist["train"])
    return dict(method="zero-intercept, fractional-outcome logistic maximum likelihood on training cp/WDL only",temperature_cp=t,
                split=meta["groups"],logloss={name:{"T400":logloss(h,400),"train_fit":logloss(h,t)} for name,h in hist.items()})

if __name__=="__main__":
    from .large_run import atomic
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("split",type=Path);p.add_argument("report",type=Path)
    a=p.parse_args()
    j=measure(a.split);atomic(a.report,j);print(json.dumps(j,indent=2))

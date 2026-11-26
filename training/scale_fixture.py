"""Produce untrained numeric test fixtures for inference parity, never for play."""
import argparse
import array
from pathlib import Path
from .screlu_wire import counts,pack

def fixture(width):
    rows=[]
    for count,period,offset in zip(counts(width),(7,17,19,23),(3,-64,9,11)):
        rows.append(array.array("h",((i*17+i//width*13)%period-offset for i in range(count))))
    return pack(rows,width=width)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("width",type=int,choices=(256,384)); p.add_argument("output",type=Path)
    a=p.parse_args()
    with a.output.open("xb") as out: out.write(fixture(a.width))

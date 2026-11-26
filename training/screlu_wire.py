"""Versioned little-endian wire format; no Torch required by a native build."""
import array
import hashlib
import struct
import sys

HEADER = struct.Struct("<8s6I")
DIMS = (768,512,8,255,64,400)
COUNTS = (768*512,512,8*1024,8)
MAGIC = b"MRSCREL1"

def pack(tensors):
    if len(tensors) != 4:
        raise ValueError("expected features, bias, bucket heads, output biases")
    payload = bytearray()
    for values,size in zip(tensors,COUNTS,strict=True):
        row = array.array("h",values)
        if row.itemsize != 2 or len(row) != size:
            raise ValueError("incorrect int16 tensor size")
        if sys.byteorder != "little": row.byteswap()
        payload.extend(row.tobytes())
    return HEADER.pack(MAGIC,*DIMS)+hashlib.sha256(payload).digest()+payload

def unpack(blob):
    if len(blob) != HEADER.size+32+2*sum(COUNTS) or HEADER.unpack_from(blob) != (MAGIC,*DIMS):
        raise ValueError("wrong SCReLU format, dimensions or length")
    payload = memoryview(blob)[HEADER.size+32:]
    if hashlib.sha256(payload).digest() != blob[HEADER.size:HEADER.size+32]:
        raise ValueError("SCReLU payload checksum mismatch")
    rows, offset = [], 0
    for size in COUNTS:
        row = array.array("h")
        row.frombytes(payload[offset:offset+2*size])
        if sys.byteorder != "little": row.byteswap()
        rows.append(row)
        offset += 2*size
    # Up to 64 occupied squares even in synthetic FEN diagnostics.
    ft,bias,_,_ = rows
    if any(abs(bias[i])+64*max(map(abs,ft[i::512])) > 32767 for i in range(512)):
        raise ValueError("unsafe int16 feature accumulator")
    return rows

def emit_header(blob,path):
    rows = unpack(blob)
    with path.open("w") as f:
        f.write("#pragma once\n#include <cstdint>\nnamespace mero_screlu_weights {\n")
        for name,row,cols in zip(("feature","bias","heads","out_bias"),rows,(512,512,1024,8)):
            multidim = len(row) != cols
            dims = (f"[{len(row)//cols}]" if multidim else "")+f"[{cols}]"
            f.write(f"alignas(64) inline constexpr std::int16_t {name}{dims} = {{\n")
            for k in range(0,len(row),cols):
                line = ",".join(map(str,row[k:k+cols]))
                f.write(("{"+line+"},\n") if multidim else line+"\n")
            f.write("};\n")
        f.write("}\n")

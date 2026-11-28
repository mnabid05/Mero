"""Versioned little-endian wire format; no Torch required by a native build."""
import array
import hashlib
import struct
import sys

HEADER = struct.Struct("<8s6I")
DIMS = (768,512,8,255,64,400)
COUNTS = (768*512,512,8*1024,8)
MAGIC = b"MRSCREL1"
RESIDUAL_MAGIC = b"MRSCRES1"
STANDALONE_MAGIC = b"MRSCNET2"

def counts(width):
    if width not in (256,384,512): raise ValueError("unsupported hidden width")
    return (768*width,width,8*2*width,8)

def width_of(blob):
    if len(blob)<HEADER.size: raise ValueError("short SCReLU header")
    return HEADER.unpack_from(blob)[2]

def pack(tensors, residual=False, width=512):
    if len(tensors) != 4:
        raise ValueError("expected features, bias, bucket heads, output biases")
    payload = bytearray()
    sizes=counts(width)
    if residual and width!=512: raise ValueError("legacy residual only supports width 512")
    for values,size in zip(tensors,sizes,strict=True):
        row = array.array("h",values)
        if row.itemsize != 2 or len(row) != size:
            raise ValueError("incorrect int16 tensor size")
        if sys.byteorder != "little": row.byteswap()
        payload.extend(row.tobytes())
    magic=STANDALONE_MAGIC if width!=512 else RESIDUAL_MAGIC if residual else MAGIC
    header=HEADER.pack(magic,768,width,*DIMS[2:])
    checksum=hashlib.sha256(header+payload if magic==STANDALONE_MAGIC else payload)
    return header+checksum.digest()+payload

def unpack(blob):
    width=width_of(blob)
    sizes=counts(width)
    if (len(blob) != HEADER.size+32+2*sum(sizes) or blob[:8] not in (MAGIC,RESIDUAL_MAGIC,STANDALONE_MAGIC)
            or (blob[:8]!=STANDALONE_MAGIC and width!=512)
            or HEADER.unpack_from(blob)[1:] != (768,width,*DIMS[2:])):
        raise ValueError("wrong SCReLU format, dimensions or length")
    payload = memoryview(blob)[HEADER.size+32:]
    digest=hashlib.sha256()
    if blob[:8]==STANDALONE_MAGIC: digest.update(blob[:HEADER.size])
    digest.update(payload)
    if digest.digest() != blob[HEADER.size:HEADER.size+32]:
        raise ValueError("SCReLU payload checksum mismatch")
    rows, offset = [], 0
    for size in sizes:
        row = array.array("h")
        row.frombytes(payload[offset:offset+2*size])
        if sys.byteorder != "little": row.byteswap()
        rows.append(row)
        offset += 2*size
    # Up to 64 occupied squares even in synthetic FEN diagnostics.
    ft,bias,_,_ = rows
    if any(abs(bias[i])+64*max(map(abs,ft[i::width])) > 32767 for i in range(width)):
        raise ValueError("unsafe int16 feature accumulator")
    if blob[:8]==RESIDUAL_MAGIC and (any(rows[3]) or any(
        rows[2][b*1024+i] != -rows[2][b*1024+512+i] for b in range(8) for i in range(512))):
        raise ValueError("residual must reverse exactly with the side to move")
    return rows

def emit_header(blob,path):
    rows = unpack(blob)
    width=width_of(blob)
    with path.open("w") as f:
        f.write("#pragma once\n#include <cstdint>\nnamespace mero_screlu_weights {\n")
        f.write("inline constexpr bool residual = "+("true" if blob[:8]==RESIDUAL_MAGIC else "false")+";\n")
        f.write(f"inline constexpr int width = {width};\n")
        f.write("inline constexpr bool standalone = "+("true" if blob[:8]==STANDALONE_MAGIC else "false")+";\n")
        for name,row,cols in zip(("feature","bias","heads","out_bias"),rows,(width,width,2*width,8)):
            multidim = len(row) != cols
            dims = (f"[{len(row)//cols}]" if multidim else "")+f"[{cols}]"
            f.write(f"alignas(64) inline constexpr std::int16_t {name}{dims} = {{\n")
            for k in range(0,len(row),cols):
                line = ",".join(map(str,row[k:k+cols]))
                f.write(("{"+line+"},\n") if multidim else line+"\n")
            f.write("};\n")
        f.write("}\n")

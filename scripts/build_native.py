#!/usr/bin/env python3
"""Build the optional C11 evaluation accelerator."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
from pathlib import Path


def output_name() -> str:
    system = platform.system()
    if system == "Darwin":
        return "libmwahaha_eval.dylib"
    if system == "Windows":
        return "mwahaha_eval.dll"
    return "libmwahaha_eval.so"


def build(output_dir: Path, compiler: str | None = None) -> Path:
    root = Path(__file__).resolve().parents[1]
    source = root / "native" / "evaluation.c"
    selected = compiler or os.environ.get("CC") or shutil.which("cc")
    if not selected:
        raise RuntimeError("No C compiler found; set CC to a C11 compiler")

    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / output_name()
    command = [
        selected,
        "-std=c11",
        "-O3",
        "-DNDEBUG",
        "-fvisibility=hidden",
        str(source),
        "-o",
        str(output),
    ]
    if platform.system() == "Darwin":
        command.insert(-2, "-dynamiclib")
    elif platform.system() != "Windows":
        command[5:5] = ["-shared", "-fPIC"]

    subprocess.run(command, check=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "build" / "native",
    )
    parser.add_argument("--compiler")
    args = parser.parse_args()
    output = build(args.output_dir, args.compiler)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

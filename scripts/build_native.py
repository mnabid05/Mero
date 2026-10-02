#!/usr/bin/env python3
"""Build the C11 evaluator and standalone C++20 UCI engine."""

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


def build(
    output_dir: Path,
    compiler: str | None = None,
    cxx_compiler: str | None = None,
    sanitize: bool = False,
) -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[1]
    source = root / "native" / "evaluation.c"
    engine_source = root / "native" / "engine.cpp"
    selected = compiler or os.environ.get("CC") or shutil.which("cc")
    selected_cxx = (
        cxx_compiler or os.environ.get("CXX") or shutil.which("c++")
    )
    if not selected:
        raise RuntimeError("No C compiler found; set CC to a C11 compiler")
    if not selected_cxx:
        raise RuntimeError("No C++ compiler found; set CXX to a C++20 compiler")
    if platform.system() == "Windows":
        raise RuntimeError("Native Windows builds are not implemented yet")

    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / output_name()
    object_file = output_dir / "evaluation.o"
    compile_c = [
        selected,
        "-std=c11",
        "-O3",
        "-DNDEBUG",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-fvisibility=hidden",
        "-fPIC",
        "-c",
        str(source),
        "-o",
        str(object_file),
    ]
    sanitizer_flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g"] if sanitize else []
    if sanitize:
        compile_c[compile_c.index("-O3")] = "-O1"
        compile_c.remove("-DNDEBUG")
    compile_c.extend(sanitizer_flags)
    subprocess.run(compile_c, check=True)

    link_library = [
        selected,
        "-shared",
        str(object_file),
        "-o",
        str(output),
    ]
    if platform.system() == "Darwin":
        link_library[1] = "-dynamiclib"
    link_library.extend(sanitizer_flags)
    subprocess.run(link_library, check=True)

    engine_output = output_dir / "mwahaha-engine"
    compile_engine = [
        selected_cxx,
        "-std=c++20",
        "-O3",
        "-DNDEBUG",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pthread",
        str(engine_source),
        str(object_file),
        "-o",
        str(engine_output),
    ]
    if sanitize:
        compile_engine[compile_engine.index("-O3")] = "-O1"
        compile_engine.remove("-DNDEBUG")
    compile_engine.extend(sanitizer_flags)
    subprocess.run(compile_engine, check=True)
    return output, engine_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "build" / "native",
    )
    parser.add_argument("--compiler")
    parser.add_argument("--cxx-compiler")
    parser.add_argument("--sanitize", action="store_true", help="enable address and undefined-behavior checks")
    args = parser.parse_args()
    library, engine = build(
        args.output_dir,
        args.compiler,
        args.cxx_compiler,
        args.sanitize,
    )
    print(library)
    print(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

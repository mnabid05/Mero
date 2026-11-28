#!/usr/bin/env python3
"""Build the C11 evaluator and standalone C++20 UCI engine."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
from pathlib import Path

RELEASE_WEIGHTS = Path(__file__).resolve().parents[1] / "training/checkpoints/mero-8.bin"
RELEASE_SHA256 = "2764a12afc0179e39c4292f560cb761f69f390ee99258ca76275d3c5aabb4134"
LOCAL_APPLE_SILICON = platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}


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
    screlu: Path | None = RELEASE_WEIGHTS,
    native_arch: bool = LOCAL_APPLE_SILICON,
    scalar_only: bool = False,
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
    if native_arch:
        compile_c.append("-march=native")
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
    if native_arch:
        compile_engine.append("-march=native")
    if screlu:
        import sys
        sys.path.insert(0, str(root))
        try:
            from training.screlu_wire import emit_header
            blob = screlu.read_bytes()
            if screlu.resolve() == RELEASE_WEIGHTS.resolve() and hashlib.sha256(blob).hexdigest() != RELEASE_SHA256:
                raise ValueError("Mero 8 release weights do not match the tested checkpoint")
            emit_header(blob, output_dir / "mero_screlu_weights.h")
        finally:
            sys.path.pop(0)
        compile_engine.extend(["-DMERO_SCRELU", "-I", str(output_dir.resolve())])
        if scalar_only:
            compile_engine.append("-DMERO_SCALAR_ONLY")
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
    arch=parser.add_mutually_exclusive_group()
    arch.add_argument("--screlu", type=Path, help="use an alternate SCReLU checkpoint instead of Mero 8")
    arch.add_argument("--release-control", action="store_true", help="opt in to Mero 7 evaluation; no SCReLU model")
    parser.add_argument("--native-arch", action=argparse.BooleanOptionalAction, default=LOCAL_APPLE_SILICON,
                        help="tune for the build machine (default on Apple Silicon)")
    parser.add_argument("--scalar-only", action="store_true", help="use the portable SCReLU kernel")
    parser.add_argument("--cxx-compiler")
    parser.add_argument("--sanitize", action="store_true", help="enable address and undefined-behavior checks")
    args = parser.parse_args()
    library, engine = build(
        args.output_dir,
        args.compiler,
        args.cxx_compiler,
        args.sanitize,
        None if args.release_control else (args.screlu or RELEASE_WEIGHTS),
        args.native_arch,
        args.scalar_only,
    )
    print(library)
    print(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

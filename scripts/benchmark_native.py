#!/usr/bin/env python3
"""Run repeatable node-limited benchmarks against the native UCI engine."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
from pathlib import Path


INFO_PATTERN = re.compile(
    r"\bdepth (?P<depth>\d+).*\bnodes (?P<nodes>\d+) "
    r"nps (?P<nps>\d+).*\btime (?P<time_ms>\d+)\b"
)


def parse_final_info(output: str) -> dict[str, int]:
    """Extract the last complete UCI search report from engine output."""
    matches = [INFO_PATTERN.search(line) for line in output.splitlines()]
    complete = [match for match in matches if match is not None]
    if not complete:
        raise ValueError("engine output did not contain a complete info line")
    return {key: int(value) for key, value in complete[-1].groupdict().items()}


def run_probe(engine: Path, nodes: int, threads: int, fen: str | None) -> dict[str, int]:
    position = f"position fen {fen}" if fen else "position startpos"
    commands = "\n".join(
        (
            "uci",
            "isready",
            f"setoption name Threads value {threads}",
            position,
            f"go nodes {nodes}",
            "quit",
            "",
        )
    )
    completed = subprocess.run(
        [str(engine)],
        input=commands,
        capture_output=True,
        check=True,
        text=True,
    )
    return parse_final_info(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "build"
        / "native"
        / "mwahaha-engine",
    )
    parser.add_argument("--nodes", type=int, default=1_000_000)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--fen")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    if args.nodes <= 0 or args.runs <= 0 or not 1 <= args.threads <= 64:
        parser.error("nodes and runs must be positive; threads must be in 1..64")

    probes = [
        run_probe(args.engine, args.nodes, args.threads, args.fen)
        for _ in range(args.runs)
    ]
    report = {
        "engine": str(args.engine),
        "nodes_requested": args.nodes,
        "threads": args.threads,
        "runs": probes,
        "median_nps": int(statistics.median(probe["nps"] for probe in probes)),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

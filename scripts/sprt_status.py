"""Summarize Fastchess's text log; never promote a candidate from a partial score."""
import argparse
import collections
import json
import re
from pathlib import Path

GAME = re.compile(r"^Finished game (\d+) \((.+?) vs (.+?)\): (1-0|0-1|1/2-1/2) \{(.+?)\}$")
DECISION = re.compile(r"^SPRT .* completed - (H[01]) was accepted")
LLR = re.compile(r"^LLR: (-?[\d.]+) .*?\((-?[\d.]+), (-?[\d.]+)\)")
FAULT = re.compile(r"forfeit|crash|stall|disconnect|illegal|loses on time|time forfe", re.I)

def summarize(lines, candidate="New", rounds=2000):
    games, faults, warnings = {}, [], collections.Counter()
    llr = decision = None
    finished = False
    for raw in lines:
        line = raw.strip()
        if m := GAME.match(line):
            number, white, black, outcome, reason = m.groups()
            if (candidate == white) == (candidate == black):
                raise ValueError(f"candidate missing or ambiguous: {line}")
            score = {"1-0":1, "0-1":0, "1/2-1/2":0.5}[outcome]
            key = int(number)
            if key in games:
                raise ValueError(f"duplicate game number: {key}")
            games[key] = score if candidate == white else 1-score
            if FAULT.search(reason):
                faults.append(dict(game=key, reason=reason))
        elif m := LLR.match(line):
            llr = tuple(map(float, m.groups()))
        elif m := DECISION.match(line):
            decision = m[1]
        elif line.startswith("Warning;"):
            warnings[line.partition(";")[2].strip().split(" - ")[0]] += 1
        elif line in ("Finished match", "Tournament finished"):
            finished = True
    n = len(games)
    outcome = "running"
    if finished:
        # Some harness revisions print H1 even if the round cap caused termination.
        # A boundary equal to a *rounded* LLR at the cap is not proof either.
        beyond = llr and ((decision == "H1" and (llr[0] > llr[2] or
                             (n < 2*rounds and llr[0] == llr[2]))) or
                          (decision == "H0" and (llr[0] < llr[1] or
                             (n < 2*rounds and llr[0] == llr[1]))))
        outcome = decision if beyond and n >= 2 else "inconclusive"
        if faults:
            outcome = "invalid: engine fault"
    wdl = collections.Counter(games.values())
    return dict(status=outcome, games=n, wins=wdl[1], draws=wdl[0.5], losses=wdl[0],
                reported_llr=llr[0] if llr else None, faults=faults,
                warnings=dict(warnings))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--candidate", default="New")
    parser.add_argument("--rounds", default=2000, type=int)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("rounds must be positive")
    with args.log.open() as stream:
        print(json.dumps(summarize(stream,args.candidate,args.rounds),indent=2))

if __name__ == "__main__":
    main()

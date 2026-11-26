"""Train and select a compact neural evaluator on held-out openings."""
import argparse
import json
from pathlib import Path
import torch

from .dataset import load_rows
from .fit import fit
from .loss import objective

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--widths", nargs="+", type=int, default=[32, 64, 96])
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1701)
    args = parser.parse_args()
    if min(args.widths + [args.epochs, args.threads]) < 1:
        parser.error("training dimensions must be positive")
    torch.set_num_threads(args.threads)
    train, valid, held = load_rows(args.database, args.seed)
    args.destination.mkdir(parents=True, exist_ok=True)
    report = dict(torch=str(torch.__version__), seed=args.seed, device="cpu",
                  train_rows=len(train[0]), validation_rows=len(valid[0]),
                  held_out_openings=held, epochs=args.epochs, trials=[],
                  prior_mae_cp=(valid[2]-valid[3]).abs().mean().item(),
                  prior_loss=objective(valid[2], valid[3]).item())
    best = float("inf")
    for width in args.widths:
        model, history = fit(train, valid, width, args.epochs, args.seed)
        selected = min(history, key=lambda epoch: epoch["loss"])
        report["trials"].append(dict(width=width, best=selected, history=history))
        if selected["loss"] < best:
            best = selected["loss"]
            report["selected_width"] = width
            torch.save(dict(width=width, state=model.state_dict()), args.destination / "best.pt")
        (args.destination / "training.json").write_text(json.dumps(report, indent=2)+"\n")

if __name__ == "__main__":
    main()

"""CLI.

  python -m factory plan     --n 5 --seed 1
  python -m factory generate --n 5 --seed 1 --out generated_tasks
  python -m factory generate --family duration --knobs '{"units":"wdhms",...}' --out demo_tasks
  python -m factory telemetry --runs runs --out pipeline_run.json --tasks generated_tasks
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config, pipeline, planner


def main() -> int:
    ap = argparse.ArgumentParser(prog="factory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--n", type=int, default=5); p.add_argument("--seed", type=int, default=1)
    p.add_argument("--ledger", type=Path)
    g = sub.add_parser("generate")
    g.add_argument("--n", type=int, default=5); g.add_argument("--seed", type=int, default=1)
    g.add_argument("--family"); g.add_argument("--knobs")
    g.add_argument("--ledger", type=Path, help="skip knob vectors already generated (fresh tasks)")
    g.add_argument("--out", type=Path, default=config.ROOT / "generated_tasks")
    g.add_argument("--runs", type=Path, default=config.ROOT / "runs")
    g.add_argument("--label", default="batch")
    t = sub.add_parser("telemetry")
    t.add_argument("--runs", type=Path, nargs="+", required=True)
    t.add_argument("--tasks", type=Path, required=True)
    t.add_argument("--out", type=Path, default=config.ROOT / "pipeline_run.json")
    a = ap.parse_args()

    if a.cmd == "plan":
        print(json.dumps(planner.plan(a.n, a.seed, a.ledger), indent=1))
        return 0
    if a.cmd == "generate":
        if a.family:
            from .families import REGISTRY
            knobs = json.loads(a.knobs) if a.knobs else planner.knob_space(REGISTRY[a.family])[0]
            plan = [(a.family, knobs)]
        else:
            plan = planner.plan(a.n, a.seed, a.ledger)
        s = pipeline.run_batch(plan, a.out, a.runs, a.label)
        if a.ledger:
            planner.record(a.ledger, plan)
        print(json.dumps({k: v for k, v in s.items()}, indent=1))
        return 0 if s["accepted"] == s["candidates"] else 1
    if a.cmd == "telemetry":
        rows = []
        shipped = {p.name for p in a.tasks.iterdir() if (p / "task.toml").exists()}
        for rd in a.runs:
            for rec in sorted(rd.glob("candidates/*/record.json")):
                r = json.loads(rec.read_text())
                if r["instance_id"] not in shipped:
                    continue
                rows.append({"instance_id": r["instance_id"], "model": r["model"],
                             "wall_seconds": r["wall_seconds"], "model_calls": r["model_calls"],
                             "attempts": len(r["attempts"]), "n_input_tokens": r["n_input_tokens"],
                             "n_output_tokens": r["n_output_tokens"], "n_cache_tokens": r["n_cache_tokens"],
                             "cost_usd": 0.0, "first_pass_valid": r["first_pass_valid"],
                             "run": rd.name, "record": str(rec.resolve().relative_to(config.ROOT))})
        a.out.write_text(json.dumps({"pipeline": f"{config.PIPELINE_NAME}/{config.PIPELINE_VERSION}",
                                     "tasks": rows}, indent=1) + "\n")
        print(f"wrote {len(rows)} rows -> {a.out}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Honest yield/cost report over EVERY attempted run (valid, failed, killed, unterminated).

    uv run python -m factory.report > evidence/YIELD_REPORT.md

Cost comes from the per-call usage in runs/<iid>/calls.jsonl (not only from summaries), so killed
and unfinished runs are counted too.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"


def row(run: Path) -> dict:
    calls = []
    if (run / "calls.jsonl").exists():
        for line in (run / "calls.jsonl").read_text().splitlines():
            try:
                calls.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    cost = sum(float((c.get("usage") or {}).get("cost") or 0) for c in calls)
    summ = json.loads((run / "summary.json").read_text()) if (run / "summary.json").exists() else None
    bench = json.loads((run / "benchmark.json").read_text()) if (run / "benchmark.json").exists() else None
    if summ is None:
        status = "killed/unterminated"
    elif summ.get("ok"):
        status = "VALID"
    else:
        status = f"rejected: {summ.get('failed_stage')}"
    if (run / "retired.json").exists():
        status += " (retired)"
    return {"iid": run.name, "status": status, "calls": len(calls), "cost": cost,
            "candidates": len(list(run.glob("candidate*"))),
            "prompts": (summ or {}).get("prompts_version", "?"),
            "bench": bench["resolve_at_3"] if bench else "",
            "lineage": ((summ or {}).get("lineage") or {}).get("replaces", "")}


def main() -> None:
    rows = [row(r) for r in sorted(RUNS.glob("pallets__click-*")) if r.is_dir()]
    total = sum(r["cost"] for r in rows)
    valid = [r for r in rows if r["status"].startswith("VALID")]
    first_pass = 0
    for r in valid:
        if r["candidates"] <= 1:
            first_pass += 1
    print("# Yield and cost report (every attempted run)\n")
    print(f"- Attempted runs: **{len(rows)}**")
    print(f"- Valid (passed every gate): **{len(valid)}**  · first-pass valid: **{first_pass}/{len(rows)}**")
    print(f"- Total generation cost from call logs: **${total:.2f}** ({sum(r['calls'] for r in rows)} model calls)")
    print(f"- Outcomes: " + ", ".join(f"{k}: {v}" for k, v in Counter(r['status'] for r in rows).most_common()))
    print("\n| run | status | prompts | candidates | calls | cost $ | Haiku resolve@3 | replaces |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['iid']} | {r['status']} | {r['prompts']} | {r['candidates']} | {r['calls']} | "
              f"{r['cost']:.2f} | {r['bench']} | {r['lineage']} |")
    print("\nKilled runs were stopped after an agent design review (Codex) found them unfair "
          "(self-contradictory rules / compatibility breaks) or likely easy (additive observers). "
          "Reviews only ever stopped runs; they never edited a generated task.")


if __name__ == "__main__":
    main()

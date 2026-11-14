#!/usr/bin/env python3
"""Benchmark generated tasks with terminus-2 + anthropic/claude-haiku-5-5 at k=3 (benchmark_guide.md).

- The provider key is read from the environment only (ANTHROPIC_API_KEY); it is never printed,
  logged or passed on the command line. Without it the script records "blocked" and exits 3.
- Every rollout is a fresh Harbor trial (fresh container from the task Dockerfile).
- resolve@k = resolved graded rollouts / graded rollouts, resolved = reward == 1.0.
- Infrastructure failures (reward null, environment/setup crash, API error / rate limit /
  truncation) are excluded and re-run (at most MAX_RERUNS per task); agent timeouts count as misses.
- All rollouts (including excluded ones) are kept; nothing is cherry-picked.
- Budget guard: stops before starting a task once the summed reported cost reaches BENCH_BUDGET_USD.

Usage:  python bench/run_benchmark.py generated_tasks/<iid> [...]   (order = priority)
Env:    ANTHROPIC_API_KEY (required), BENCH_BUDGET_USD (default 60), BENCH_K (default 3),
        HARBOR_ENV (e.g. "podman"; default: Harbor's default docker)
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = "anthropic/claude-haiku-5-5"
MODEL_DIR = "claude-haiku-5-5"
AGENT = "terminus-2"
K = int(os.environ.get("BENCH_K", "3"))
BUDGET = float(os.environ.get("BENCH_BUDGET_USD", "60"))
MAX_RERUNS = 3
INFRA_EXC = ("Environment", "Setup", "RateLimit", "APIError", "APIConnection", "ServiceUnavailable",
             "InternalServer", "Authentication", "ContextLength", "OutputLength", "Truncat", "BadRequest")


def classify(res: dict) -> tuple[str, float | None, str]:
    """-> (kind, reward, note) with kind in graded|infra."""
    exc = res.get("exception_info") or {}
    et = exc.get("exception_type", "") if exc else ""
    vr = (res.get("verifier_result") or {}).get("rewards") or {}
    reward = vr.get("reward")
    mi = (res.get("agent_info") or {}).get("model_info") or {}
    model_seen = f"{mi.get('provider', '')}/{mi.get('name', '')}".strip("/") if mi else ""
    if mi and MODEL.split("/")[-1] not in json.dumps(mi):
        return "infra", reward, f"model mismatch: {model_seen}"
    if et == "AgentTimeoutError":
        return "graded", reward if reward is not None else 0.0, "agent timeout (counts as miss)"
    if et and any(s in et for s in INFRA_EXC):
        return "infra", reward, f"infra exception {et}"
    if reward is None:
        return "infra", None, f"no reward ({et or 'verifier did not run'})"
    if et:
        return "graded", reward, f"graded with exception {et}"
    return "graded", reward, ""


def trials(job_root: Path) -> list[Path]:
    return sorted(p.parent for p in job_root.glob("*/*/result.json"))


def run_harbor(task: Path, k: int, out: Path) -> int:
    cmd = ["harbor", "run", "-p", str(task), "-a", AGENT, "-m", MODEL, "-k", str(k), "-n", str(k),
           "-o", str(out), "--no-delete", "-y"]
    if os.environ.get("HARBOR_ENV"):
        cmd += ["-e", os.environ["HARBOR_ENV"]]
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "harbor_cli.log", "a") as log:
        log.write(f"$ {' '.join(cmd)}\n")
        return subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode


def main(argv: list[str]) -> int:
    bench = ROOT / "bench"
    status = {"started": dt.datetime.now().isoformat(), "model": MODEL, "agent": AGENT, "k": K,
              "budget_usd": BUDGET, "tasks": argv}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        status["status"] = "blocked: ANTHROPIC_API_KEY not set (no organizer credential available)"
        (bench / "benchmark_status.json").write_text(json.dumps(status, indent=1))
        print(status["status"])
        return 3
    spent, rows = 0.0, []
    for t in argv:
        task = Path(t).resolve()
        iid = task.name
        if spent >= BUDGET:
            rows.append({"instance_id": iid, "status": "not run (budget guard)"})
            continue
        job = bench / "jobs" / iid
        graded, infra, attempt = [], [], 0
        need = K
        while need > 0 and attempt <= MAX_RERUNS:
            before = set(trials(job))
            run_harbor(task, need if attempt == 0 else 1, job)
            for tr in sorted(set(trials(job)) - before):
                res = json.loads((tr / "result.json").read_text())
                cost = (res.get("agent_result") or {}).get("cost_usd") or 0.0
                spent += cost
                kind, reward, note = classify(res)
                entry = {"trial": tr.name, "reward": reward, "note": note, "cost_usd": cost,
                         "task_checksum": res.get("task_checksum"),
                         "n_input_tokens": (res.get("agent_result") or {}).get("n_input_tokens"),
                         "n_output_tokens": (res.get("agent_result") or {}).get("n_output_tokens")}
                (graded if kind == "graded" else infra).append((tr, entry))
            need = K - len(graded)
            attempt += 1
        # Trajectory layout required by SUBMISSION.md 3c; only the first K graded rollouts count.
        tdir = ROOT / "trajectory" / iid / MODEL_DIR
        if tdir.exists():
            shutil.rmtree(tdir)
        for n, (tr, _) in enumerate(graded[:K], 1):
            shutil.copytree(tr, tdir / f"rollout_{n}", ignore=shutil.ignore_patterns("*.sock"))
        for n, (tr, _) in enumerate(infra, 1):
            shutil.copytree(tr, ROOT / "trajectory_excluded_infra" / iid / MODEL_DIR / f"excluded_{n}")
        counted = [e for _, e in graded[:K]]
        resolved = sum(1 for e in counted if e["reward"] == 1.0)
        rows.append({"instance_id": iid, "status": "ok" if len(counted) == K else "incomplete",
                     "graded": len(counted), "resolved": resolved,
                     "resolve_at_k": f"{resolved}/{len(counted)}",
                     "rewards": [e["reward"] for e in counted],
                     "infra_excluded": [e for _, e in infra], "rollouts": counted})
    status.update(status="done", spent_usd_reported=round(spent, 4), results=rows,
                  finished=dt.datetime.now().isoformat())
    (bench / "benchmark_results.json").write_text(json.dumps(status, indent=1))
    with open(bench / "benchmark_results.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["instance_id", "resolve@k", "rewards", "infra_excluded"])
        for r in rows:
            w.writerow([r["instance_id"], r.get("resolve_at_k", r["status"]), r.get("rewards", ""),
                        len(r.get("infra_excluded", []))])
    print(json.dumps({r["instance_id"]: r.get("resolve_at_k", r["status"]) for r in rows}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

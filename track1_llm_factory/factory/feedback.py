"""Difficulty feedback loop (plan v6.2 §3, pre-committed redesign path).

    uv run python -m factory.feedback loop          # watch, benchmark, record, redesign
    uv run python -m factory.feedback record <iid>  # just record a finished benchmark

1. Any run whose summary is ok (passed every gate) and has a package in generated_tasks/ is
   benchmarked once: terminus-2 + Haiku, k=3 (OPENROUTER_API_KEY from env only).
2. The result is written to runs/<iid>/benchmark.json (per-trial rewards, resolve@3).
3. If resolve@3 >= 2/3 and the task is not itself a replacement, it is RETIRED
   (runs/<iid>/retired.json) and its harder replacement is generated once:
   `generate --card <card> --seed <seed+100> --harder-than <iid>`. Only the COUNT feeds back —
   never the agent's trajectory or code. The replacement is benchmarked with fresh rollouts and is
   submitted if valid regardless of its own score; both results are disclosed (no post-hoc selection).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS, JOBS, OUT = ROOT / "runs", ROOT / "jobs", ROOT / "generated_tasks"
MODEL = os.environ.get("BENCH_MODEL", "openrouter/anthropic/claude-haiku-5.5")
K = int(os.environ.get("BENCH_K", "3"))
SKIP = {"pallets__click-types-0001"}  # pilot, benchmarked separately (3/3)


def log(msg: str) -> None:
    print(f"[feedback {time.strftime('%H:%M')}] {msg}", flush=True)


def rewards(iid: str) -> list[float]:
    out = []
    for gd in sorted((JOBS / f"hard-{iid}").glob("*/*/verifier/grading_details.json")):
        out.append(float(json.loads(gd.read_text())["reward"]))
    return out


def record(iid: str) -> dict:
    r = rewards(iid)
    solved = sum(1 for x in r if x == 1.0)
    rec = {"instance_id": iid, "model": MODEL, "k": K, "rewards": r,
           "resolve_at_3": f"{solved}/{len(r)}", "complete": len(r) == K,
           "recorded_at": time.strftime("%H:%M")}
    (RUNS / iid / "benchmark.json").write_text(json.dumps(rec, indent=1))
    return rec


def parse(iid: str) -> tuple[str, int]:
    body = iid[len("pallets__click-"):]
    card, seed = body.rsplit("-", 1)
    return card, int(seed)


def maybe_redesign(iid: str, rec: dict) -> None:
    summary = json.loads((RUNS / iid / "summary.json").read_text())
    solved = int(rec["resolve_at_3"].split("/")[0])
    if not rec["complete"] or solved < 2:
        log(f"{iid} resolve@3={rec['resolve_at_3']} → KEEP (stumps the benchmark model)")
        return
    if summary.get("lineage"):
        log(f"{iid} resolve@3={rec['resolve_at_3']} → is already a replacement; kept and disclosed (one redesign only)")
        return
    card, seed = parse(iid)
    new_seed = seed + 100
    (RUNS / iid / "retired.json").write_text(json.dumps(
        {"retired": iid, "reason": f"resolve@3={rec['resolve_at_3']}", "replacement_seed": new_seed}, indent=1))
    log(f"{iid} resolve@3={rec['resolve_at_3']} → RETIRED; generating harder replacement {card} seed {new_seed}")
    subprocess.Popen([sys.executable, "-m", "factory.generate", "--card", card, "--seed", str(new_seed),
                      "--harder-than", iid], cwd=ROOT,
                     stdout=open(ROOT / f"runs-{card}-{new_seed}.log", "w"), stderr=subprocess.STDOUT)


def loop() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY not set (environment only)")
    JOBS.mkdir(exist_ok=True)
    running: dict[str, subprocess.Popen] = {}
    while True:
        for s in sorted(RUNS.glob("pallets__click-*/summary.json")):
            iid = s.parent.name
            started = JOBS / f"hard-{iid}.started"
            if iid in SKIP or started.exists():
                continue
            try:
                ok = json.loads(s.read_text()).get("ok")
            except json.JSONDecodeError:
                continue
            if ok and (OUT / iid).is_dir():
                started.touch()
                log(f"BENCH START {iid}")
                running[iid] = subprocess.Popen(
                    ["harbor", "run", "-p", str(OUT / iid), "-a", "terminus-2", "-m", MODEL, "-k", str(K),
                     "-n", str(K), "-o", str(JOBS / f"hard-{iid}"), "--no-delete", "-y"],
                    cwd=ROOT, stdout=open(JOBS / f"hard-{iid}.log", "w"), stderr=subprocess.STDOUT)
        # also pick up benchmarks started outside the loop (marker present, no benchmark.json yet)
        for m in JOBS.glob("hard-*.started"):
            iid = m.name[len("hard-"):-len(".started")]
            done = (RUNS / iid / "benchmark.json").exists()
            proc = running.get(iid)
            if done or (proc and proc.poll() is None):
                continue
            if proc is None and len(rewards(iid)) < K:
                continue  # external run still in progress
            rec = record(iid)
            log(f"BENCH DONE {iid} rewards={rec['rewards']} resolve@3={rec['resolve_at_3']}")
            maybe_redesign(iid, rec)
            running.pop(iid, None)
        time.sleep(10)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "record":
        print(json.dumps(record(sys.argv[2]), indent=1))
    else:
        loop()

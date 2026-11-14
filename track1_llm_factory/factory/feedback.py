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
SKIP = {"pallets__click-types-0001"}
MAX_INFRA_RETRIES = int(os.environ.get("BENCH_MAX_INFRA_RETRIES", "2"))  # pilot, benchmarked separately (3/3)


def log(msg: str) -> None:
    print(f"[feedback {time.strftime('%H:%M')}] {msg}", flush=True)


def rewards(iid: str) -> list[float]:
    """Valid trial rewards from the NEWEST job dir only: model must match, no exception, reward set,
    and every trial must carry the same task checksum."""
    jobs = sorted(p for p in (JOBS / f"hard-{iid}").glob("*") if p.is_dir())
    if not jobs:
        return []
    out = []
    for res in sorted(jobs[-1].glob("*/result.json")):
        r = json.loads(res.read_text())
        agent = (r.get("config") or {}).get("agent") or {}
        gd = res.parent / "verifier" / "grading_details.json"
        if (agent.get("model_name") != MODEL or r.get("task_name") != iid or r.get("reward_valid") is not True
                or not r.get("task_checksum") or r.get("exception_info") or not gd.exists()):
            continue
        reward = json.loads(gd.read_text()).get("reward")
        if reward is None:
            continue
        out.append((r["task_checksum"], float(reward)))
    if len({c for c, _ in out}) > 1:
        log(f"{iid}: trials have different task checksums; treating as incomplete")
        return []
    return [x for _, x in out]


def _slot_busy(running: dict) -> bool:
    """Global one-job slot: any live process we started, OR any started marker (from any process,
    incl. before a restart) whose benchmark is not recorded yet and whose pid is alive/unknown."""
    if any(p.poll() is None for p in running.values()):
        return True
    for m in JOBS.glob("hard-*.started"):
        iid = m.name[len("hard-"):-len(".started")]
        if (RUNS / iid / "benchmark.json").exists():
            continue
        try:
            pid = json.loads(m.read_text() or "{}").get("pid")
        except json.JSONDecodeError:
            pid = None
        if pid is None:
            if (RUNS / iid / "benchmark_infra_failed.json").exists():
                continue
            if len(rewards(iid)) < K:
                return True  # external run of unknown pid still incomplete
            continue
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            continue
    return False


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
    new_iid = f"pallets__click-{card}-{new_seed:04d}"
    if (RUNS / new_iid).exists() or (OUT / new_iid).exists():
        log(f"{iid}: replacement {new_iid} already exists; refusing to overwrite (fail closed)")
        return
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
                if _slot_busy(running):
                    continue  # one k=3 job at a time globally (v6.2 container cap)
                log(f"BENCH START {iid}")
                try:
                    proc = subprocess.Popen(
                        ["harbor", "run", "-p", str(OUT / iid), "-a", "terminus-2", "-m", MODEL, "-k", str(K),
                     "-n", str(K), "-o", str(JOBS / f"hard-{iid}"), "--no-delete", "-y"],
                    cwd=ROOT, stdout=open(JOBS / f"hard-{iid}.log", "w"), stderr=subprocess.STDOUT)
                except OSError as e:
                    log(f"BENCH SPAWN FAILED {iid}: {e}")
                    continue
                running[iid] = proc
                rf = JOBS / f"hard-{iid}.retries"
                tries = int(rf.read_text()) if rf.exists() else 0
                started.write_text(json.dumps({"pid": proc.pid, "started": time.strftime("%H:%M"), "infra_retries": tries}))
        # finished benchmarks (ours or external/pre-restart): record ONLY at exactly K valid trials
        for m in JOBS.glob("hard-*.started"):
            iid = m.name[len("hard-"):-len(".started")]
            if (RUNS / iid / "benchmark.json").exists():
                continue
            proc = running.get(iid)
            if proc and proc.poll() is None:
                continue
            try:
                meta = json.loads(m.read_text() or "{}")
            except json.JSONDecodeError:
                meta = {}
            pid = meta.get("pid")
            if proc is None and pid:
                try:
                    os.kill(pid, 0)
                    continue  # still running (started before a restart)
                except OSError:
                    pass
            n_valid = len(rewards(iid))
            if n_valid < K:
                if proc is None and not pid:
                    continue  # external run of unknown pid: wait
                tries = int(meta.get("infra_retries", 0))
                running.pop(iid, None)
                if tries < MAX_INFRA_RETRIES:
                    log(f"BENCH INFRA {iid}: {n_valid}/{K} valid trials → infra failure, retry {tries + 1}/{MAX_INFRA_RETRIES}")
                    m.unlink()
                    (JOBS / f"hard-{iid}.retries").write_text(str(tries + 1))
                else:
                    log(f"BENCH INFRA {iid}: {n_valid}/{K} valid after {tries} retries → give up (no verdict, no redesign)")
                    m.write_text(json.dumps(dict(meta, gave_up=True, pid=None)))
                    (RUNS / iid / "benchmark_infra_failed.json").write_text(json.dumps({"valid_trials": n_valid}))
                continue
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

"""Generate -> materialise -> curate -> package -> gate, with full provenance per attempt."""
from __future__ import annotations

import ast
import datetime as dt
import json
import shutil
import subprocess
import time
from pathlib import Path

from . import config, container, curate, gates, package, repo
from .families import REGISTRY

MAX_ATTEMPTS = 2


def f2p_ids(draft) -> list[str]:
    ids = []
    for path, body in sorted(draft.test_files.items()):
        for n in ast.parse(body).body:
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"):
                ids.append(f"{path}::{n.name}")
    return ids


def code_version() -> str:
    p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=config.ROOT, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "factory"], cwd=config.ROOT,
                           capture_output=True, text=True).stdout.strip()
    return (p.stdout.strip() or "untracked") + ("+dirty" if dirty else "")


def run_candidate(family: str, knobs: dict, out_dir: Path, run_dir: Path, cov: dict) -> dict:
    t0 = time.time()
    mod = REGISTRY[family]
    draft = mod.build(knobs)
    iid = package.instance_id(draft)
    cdir = run_dir / "candidates" / iid
    if cdir.exists():
        shutil.rmtree(cdir)
    cdir.mkdir(parents=True)
    record = {"instance_id": iid, "family": family, "knobs": knobs, "axes": draft.axes,
              "generator": "deterministic blueprint (no LLM)", "model": "none", "model_calls": 0,
              "n_input_tokens": 0, "n_output_tokens": 0, "n_cache_tokens": 0,
              "base_commit": config.BASE_COMMIT, "code_version": code_version(),
              "attempts": [], "repairs": [], "human_edits_after_generation": []}
    # raw first-pass artefacts
    raw = cdir / "raw_draft"
    raw.mkdir()
    (raw / "instruction.md").write_text(draft.instruction)
    for p, b in draft.test_files.items():
        (raw / Path(p).name).write_text(b)

    drop_p2p: set[str] = set()
    pkg = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        adir = cdir / f"attempt_{attempt}"
        adir.mkdir()
        res: list[dict] = []
        verdict, reason = "rejected", ""
        try:
            gold, test_patch = repo.gold_and_test_patches(draft)
            base_tree = repo.export_base(Path(str(adir / "base_tree")))
            touched = curate.touched_symbols(gold, draft.focus_symbols, base_tree)
            shutil.rmtree(base_tree, ignore_errors=True)
            p2p, why = curate.select_p2p(cov, touched, set(draft.test_files))
            p2p = [n for n in p2p if n not in drop_p2p]
            (adir / "p2p_rationale.json").write_text(json.dumps(why, indent=1))
            f2p = f2p_ids(draft)
            pkg = package.write(draft, gold, test_patch, f2p, p2p, adir / "package")

            res.append(gates.structure(pkg))
            res.append(gates.base_health(cov))
            res.append(gates.grounding(draft, gold, touched))
            res.append(gates.novelty(draft, adir))
            res.append(gates.fairness(draft, f2p))
            res.append(gates.isolation(pkg, draft, gold))

            g = container.grade(pkg, gold, adir / "run_gold")
            n = container.grade(pkg, None, adir / "run_nop")
            res.append(gates.gold_gate(g, f2p, p2p))
            res.append(gates.nop_gate(n, f2p, p2p))

            # Auto-repair: a curated P2P test that is not green at base is a curation fault, not a
            # task fault: drop it and re-run. A P2P test green at base but red under gold is a gold
            # regression and rejects the candidate.
            bad_base = [x for x in p2p if n.get("statuses", {}).get(x) != "PASSED"]
            gold_regr = [x for x in p2p if x not in bad_base and g.get("statuses", {}).get(x) != "PASSED"]
            if bad_base and attempt < MAX_ATTEMPTS:
                drop_p2p |= set(bad_base)
                record["repairs"].append({"attempt": attempt, "action": "drop non-green P2P", "tests": bad_base})
                verdict, reason = "retry", "P2P not green at base"
                raise _Retry()
            if gold_regr:
                reason = f"gold regresses curated tests: {gold_regr[:5]}"

            muts = {}
            for m in draft.mutants:
                muts[m.name] = container.grade(pkg, repo.mutant_patch(draft, m), adir / f"run_mutant_{m.name}")
            res.append(gates.mutation_gate(muts, f2p, p2p))
            (adir / "mutants.json").write_text(json.dumps(
                {m.name: m.description for m in draft.mutants}, indent=1))

            _dump(adir, "gold.diff", gold)
            _dump(adir, "tests.diff", test_patch)
            fdir = adir / "full_suite"
            fdir.mkdir(exist_ok=True)
            full = container.run(container.full_suite_script(),
                                 mounts={str(adir.resolve()): "/sol:ro", str(fdir.resolve()): "/out"})
            (fdir / "container.log").write_text(f"exit={full.returncode}\n--- stdout\n{full.stdout[-20000:]}\n"
                                                f"--- stderr\n{full.stderr[-20000:]}")
            flog = fdir / "pytest.log"
            res.append(gates.full_suite_gate(full, flog.read_text(errors="replace") if flog.exists() else None))
            failed = [r["gate"] for r in res if not r["ok"]]
            if not failed and not reason:
                verdict, reason = "accepted", "all gates passed"
            else:
                reason = reason or f"failed gates: {failed}"
        except _Retry:
            pass
        except repo.GroundingError as e:
            res.append(gates._res("grounding", False, "static", error=str(e)))
            reason = f"grounding: {e}"
        except Exception as e:  # recorded, never swallowed silently
            res.append(gates._res("pipeline_error", False, "pipeline", error=repr(e)[:500]))
            reason = f"pipeline error: {e!r}"[:300]
        (adir / "gates.json").write_text(json.dumps(res, indent=1))
        record["attempts"].append({"attempt": attempt, "verdict": verdict, "reason": reason,
                                   "gates": {r["gate"]: r["ok"] for r in res}})
        if verdict != "retry":
            break

    final = record["attempts"][-1]
    record["status"] = final["verdict"]
    record["first_pass_valid"] = len(record["attempts"]) == 1 and final["verdict"] == "accepted"
    record["wall_seconds"] = round(time.time() - t0, 1)
    if final["verdict"] == "accepted" and pkg is not None:
        dest = out_dir / iid
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(pkg, dest)
        record["package"] = str(dest)
    (cdir / "record.json").write_text(json.dumps(record, indent=1))
    return record


class _Retry(Exception):
    pass


def _dump(d: Path, name: str, body: str) -> Path:
    p = d / name
    p.write_text(body)
    return p


def run_batch(plan: list[tuple[str, dict]], out_dir: Path, runs_root: Path, label: str) -> dict:
    config.WORK.mkdir(parents=True, exist_ok=True)
    run_id = dt.datetime.now().strftime("%Y%m%dT%H%M%S") + f"_{label}"
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    repo.ensure_upstream()
    container.ensure_image(run_dir / "image_build.log")
    cov = curate.base_coverage(config.WORK / f"cov_{container.image_tag().split(':')[1]}")
    (run_dir / "plan.json").write_text(json.dumps(plan, indent=1))
    records = [run_candidate(f, k, out_dir, run_dir, cov) for f, k in plan]
    summary = {"run_id": run_id, "pipeline": f"{config.PIPELINE_NAME}/{config.PIPELINE_VERSION}",
               "base_commit": config.BASE_COMMIT, "image": container.image_tag(),
               "candidates": len(records),
               "accepted": sum(r["status"] == "accepted" for r in records),
               "first_pass_valid": sum(r["first_pass_valid"] for r in records),
               "wall_seconds": round(time.time() - t0, 1),
               "records": [{k: r[k] for k in ("instance_id", "family", "knobs", "status",
                                              "first_pass_valid", "wall_seconds")}
                           | {"attempts": len(r["attempts"]),
                              "failed_gates": [g for g, ok in r["attempts"][-1]["gates"].items() if not ok],
                              "reason": r["attempts"][-1]["reason"]} for r in records]}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary

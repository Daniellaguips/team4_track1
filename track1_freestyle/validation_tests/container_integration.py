"""Container integration check of the hardened gates on an isolated copy of one V1 task.

Needs a working container engine (T1_ENGINE=docker|podman) and network for the first image build.
Never writes into generated_tasks/, runs/ or evidence/: the task is copied to T1_WORK and all
output goes to evidence_v2/integration/<timestamp>/.

  T1_ENGINE=docker python validation_tests/container_integration.py \
      pallets__click-duration-param-type-9f8a40 bounds_exclusive
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from factory import config, container, gates  # noqa: E402


def main(task: str, mutant: str | None) -> int:
    src = ROOT / "generated_tasks" / task
    out = ROOT / "evidence_v2" / "integration" / (dt.datetime.now().strftime("%Y%m%dT%H%M%S") + f"_{task}")
    out.mkdir(parents=True)
    config.WORK.mkdir(parents=True, exist_ok=True)
    pkg = config.WORK / "integration_copy" / task
    if pkg.exists():
        shutil.rmtree(pkg)
    shutil.copytree(src, pkg)

    tag = container.ensure_image(out / "image_build.log")
    f2p = json.loads((pkg / "tests/fail_to_pass.json").read_text())
    p2p = json.loads((pkg / "tests/pass_to_pass.json").read_text())
    gold = (pkg / "solution/patch.diff").read_text()
    res = [gates.gold_gate(container.grade(pkg, gold, out / "run_gold"), f2p, p2p),
           gates.nop_gate(container.grade(pkg, None, out / "run_nop"), f2p, p2p)]
    if mutant:
        attempt = ROOT / "runs/20261114T115550_batch5/candidates" / task / "attempt_1"
        diff = (attempt / f"run_mutant_{mutant}" / "applied.diff").read_text()
        res.append(gates.mutation_gate({mutant: container.grade(pkg, diff, out / f"run_mutant_{mutant}")},
                                       f2p, p2p))
    sol = out / "sol"
    sol.mkdir()
    (sol / "gold.diff").write_text(gold)
    (sol / "tests.diff").write_text((pkg / "tests/test_patch.diff").read_text())
    fdir = out / "full_suite"
    fdir.mkdir()
    full = container.run(container.full_suite_script(),
                         mounts={str(sol.resolve()): "/sol:ro", str(fdir.resolve()): "/out"})
    (fdir / "container.log").write_text(f"exit={full.returncode}\n--- stdout\n{full.stdout}\n--- stderr\n{full.stderr}")
    flog = fdir / "pytest.log"
    res.append(gates.full_suite_gate(full, flog.read_text() if flog.exists() else None))

    summary = {"task_copy_of": str(src.relative_to(ROOT)), "image": tag, "engine": config.ENGINE,
               "gates": {r["gate"]: r["ok"] for r in res}, "note": "new run, not historical evidence"}
    (out / "gates.json").write_text(json.dumps(res, indent=1, default=str))
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return 0 if all(summary["gates"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))

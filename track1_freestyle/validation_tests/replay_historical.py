"""Re-classify saved historical gate runs with the current gate logic (offline, no containers).

This reads files written by earlier container runs; it does not re-execute anything. Output is a
comparison of the historical gate verdicts (gates.json) with what the current gates decide.

  python validation_tests/replay_historical.py runs/20261114T115550_batch5 dev_runs/* > out.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from factory import container, gates  # noqa: E402


def replay_attempt(adir: Path) -> dict | None:
    pkgs = sorted((adir / "package").glob("*/tests/fail_to_pass.json"))
    if not pkgs or not (adir / "run_gold").exists():
        return None
    tdir = pkgs[0].parent
    f2p = json.loads((tdir / "fail_to_pass.json").read_text())
    p2p = json.loads((tdir / "pass_to_pass.json").read_text())
    hist = {g["gate"]: g["ok"] for g in json.loads((adir / "gates.json").read_text())} \
        if (adir / "gates.json").exists() else {}
    gold = gates.gold_gate(container.read_result(adir / "run_gold"), f2p, p2p)
    out = {"historical": {k: hist.get(k) for k in ("gold", "nop", "mutation", "full_suite_under_gold")},
           "replayed": {"gold": gold["ok"]}, "problems": {"gold": gold["detail"]["problems"]}}
    if (adir / "run_nop").exists():
        nop = gates.nop_gate(container.read_result(adir / "run_nop"), f2p, p2p)
        out["replayed"]["nop"] = nop["ok"]
        out["problems"]["nop"] = nop["detail"]["problems"]
        out["nop_not_failed"] = nop["detail"]["not_failed"]
    muts = {d.name[len("run_mutant_"):]: container.read_result(d) for d in sorted(adir.glob("run_mutant_*"))}
    if muts:
        mg = gates.mutation_gate(muts, f2p, p2p)
        out["replayed"]["mutation"] = mg["ok"]
        out["mutant_verdicts"] = mg["detail"]["verdicts"]
        out["problems"]["mutation"] = {m: v["problems"] for m, v in mg["detail"]["per_mutant"].items()
                                       if v["problems"]}
    out["note"] = "full_suite_under_gold not replayable: historical runs kept only the last 3 output lines"
    return out


def main(argv: list[str]) -> int:
    report = {}
    for run in argv:
        for adir in sorted(Path(run).glob("candidates/*/attempt_*")):
            r = replay_attempt(adir)
            if r is not None:
                report[str(adir.relative_to(ROOT) if adir.is_absolute() else adir)] = r
    json.dump(report, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

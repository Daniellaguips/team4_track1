"""Container integration check of the hardened gates on an isolated copy of one V1 task.

Needs a working container engine (T1_ENGINE=docker|podman) and network for the first image build.
Never writes into generated_tasks/, runs/ or evidence/: the task is copied to T1_WORK and all
output goes to evidence_v2/integration/<timestamp>_<task>/.

Every case other than ``gold``, ``nop`` and the historical behavioural mutant is a deliberately
corrupted TEST FIXTURE built from the isolated copy. Each case records the hardened verdict, the
expected verdict, and what the V1 decision logic would have concluded from the same run.

  T1_ENGINE=docker python validation_tests/container_integration.py \
      pallets__click-duration-param-type-9f8a40 bounds_exclusive
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from factory import config, container, gates  # noqa: E402

V1_FULL_SUITE_CMD = "cd {app} && git apply {sol}/gold.diff && git apply {sol}/tests.diff && {pytest} 2>&1 | tail -3"


def v1_gold_ok(r):
    return r.get("reward") == 1.0 and r["f2p_passed"] == r["f2p_total"] and r["p2p_passed"] == r["p2p_total"]


def v1_nop_ok(r):
    return r.get("reward") == 0.0 and r["f2p_passed"] == 0 and r["p2p_passed"] == r["p2p_total"]


def v1_killed(r):
    return r.get("reward") is not None and r["f2p_passed"] < r["f2p_total"]


def v1_full_suite_ok(p):
    tail = (p.stdout or "").strip().splitlines()[-3:]
    return p.returncode == 0 and not re.search(r"(\d+) failed", "\n".join(tail))


# ------------------------------------------------------------------ fixture builders (pure text)
def _hunks_of(diff: str, path: str) -> tuple[int, int]:
    """Line range [start, end) of the file section for ``path`` in a unified diff."""
    lines = diff.splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if l.startswith(f"+++ b/{path}"))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("diff --git")), len(lines))
    return start, end


def replace_added_line(diff: str, path: str, pred, new: str) -> str:
    """Replace the first added line of ``path`` matching ``pred`` (hunk line counts unchanged)."""
    lines = diff.splitlines(keepends=True)
    s, e = _hunks_of(diff, path)
    for i in range(s + 1, e):
        if lines[i].startswith("+") and pred(lines[i][1:]):
            lines[i] = "+" + new + "\n"
            return "".join(lines)
    raise ValueError(f"no matching added line in {path}")


UNAPPLIABLE_HUNK = """diff --git a/tests/conftest.py b/tests/conftest.py
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -1,1 +1,1 @@
-T1_FIXTURE_LINE_THAT_IS_NOT_IN_THE_FILE
+T1_FIXTURE_REPLACEMENT
"""


def corrupt_context(diff: str) -> str:
    """Make ``git apply`` refuse the patch: corrupt the first context line, or (for a patch that
    only creates files) prepend a hunk whose removed line is not in the file. ``git apply`` is
    atomic, so nothing of the patch is applied."""
    lines = diff.splitlines(keepends=True)
    for i, l in enumerate(lines):
        if l.startswith(" ") and l.strip():
            lines[i] = " T1_FIXTURE_CORRUPTED_CONTEXT_LINE\n"
            return "".join(lines)
    return UNAPPLIABLE_HUNK + diff


def feature_test_file(test_patch: str) -> str:
    return re.findall(r"^\+\+\+ b/(tests/\S+\.py)", test_patch, re.M)[0]


def gold_src_file(gold: str) -> str:
    return re.findall(r"^\+\+\+ b/(src/\S+\.py)", gold, re.M)[0]


# ------------------------------------------------------------------ runner
class Run:
    def __init__(self, out: Path):
        self.out = out
        self.cases = []

    def record(self, name, kind, fixture, expected, verdict, v1, detail):
        self.cases.append({"case": name, "kind": kind, "test_fixture": fixture, "expected": expected,
                           "hardened": verdict, "as_expected": verdict == expected, "v1_logic": v1,
                           "detail": detail})
        print(f"{name:42s} expected={expected!s:9s} hardened={verdict!s:9s} v1={v1}")


def copy_pkg(src: Path, name: str) -> Path:
    pkg = config.WORK / "integration_copy" / name
    if pkg.exists():
        shutil.rmtree(pkg)
    shutil.copytree(src, pkg)
    return pkg


def run_full_suite(sol_files: dict[str, str], out: Path, v1: bool = False) -> tuple:
    sol = out / "sol"
    fdir = out / "full_suite"
    sol.mkdir(parents=True)
    fdir.mkdir()
    for k, v in sol_files.items():
        (sol / k).write_text(v)
    script = (V1_FULL_SUITE_CMD.format(app="/app", sol="/sol", pytest=container.FULL_SUITE_PYTEST) if v1
              else container.full_suite_script())
    (out / "command.sh").write_text(script)
    p = container.run(script, mounts={str(sol.resolve()): "/sol:ro", str(fdir.resolve()): "/out"})
    (out / "container.log").write_text(f"exit={p.returncode}\n--- stdout\n{p.stdout}\n--- stderr\n{p.stderr}")
    flog = fdir / "pytest.log"
    return p, (flog.read_text() if flog.exists() else None)


def log_facts(log: str | None) -> dict:
    if log is None:
        return {"saved_log": False}
    ls = log.splitlines()
    return {"saved_log": True, "lines": len(ls), "bytes": len(log.encode()),
            "ends_with_pytest_summary": gates.pytest_summary(log) is not None,
            "has_failures_or_errors_section": any(re.match(r"^=+ (FAILURES|ERRORS) =+$", l) for l in ls),
            "last_line": ls[-1] if ls else ""}


def main(task: str, mutant: str | None) -> int:
    src = ROOT / "generated_tasks" / task
    out = ROOT / "evidence_v2" / "integration" / (dt.datetime.now().strftime("%Y%m%dT%H%M%S") + f"_{task}")
    out.mkdir(parents=True)
    config.WORK.mkdir(parents=True, exist_ok=True)
    tag = container.ensure_image(out / "image_build.log")
    R = Run(out)

    pkg = copy_pkg(src, task)
    f2p = json.loads((pkg / "tests/fail_to_pass.json").read_text())
    p2p = json.loads((pkg / "tests/pass_to_pass.json").read_text())
    gold = (pkg / "solution/patch.diff").read_text()
    tpatch = (pkg / "tests/test_patch.diff").read_text()
    tfile, sfile = feature_test_file(tpatch), gold_src_file(gold)

    def grade(p, patch, name):
        return container.grade(p, patch, out / "grade" / name)

    # 1. real gold / nop on the unmodified isolated copy
    r = grade(pkg, gold, "gold")
    g = gates.gold_gate(r, f2p, p2p)
    R.record("gold", "gold", False, "accept", "accept" if g["ok"] else "reject", v1_gold_ok(r), g)
    r = grade(pkg, None, "nop")
    g = gates.nop_gate(r, f2p, p2p)
    R.record("nop_baseline", "nop", False, "accept", "accept" if g["ok"] else "reject", v1_nop_ok(r), g)

    # 2. FIXTURE: expected F2P id that does not exist (missing test) -> nop must not count it as absent
    fx = copy_pkg(src, task + "__fixture_missing_f2p")
    bad_f2p = f2p + [f"{tfile}::test_t1_fixture_does_not_exist"]
    (fx / "tests/fail_to_pass.json").write_text(json.dumps(bad_f2p, indent=2))
    r = grade(fx, None, "fixture_missing_f2p_nop")
    g = gates.nop_gate(r, bad_f2p, p2p)
    R.record("fixture_missing_f2p__nop", "nop", True, "reject", "accept" if g["ok"] else "reject",
             "accept" if v1_nop_ok(r) else "reject", g)

    # 3. FIXTURE: feature test file fails to collect (module-level SyntaxError)
    fx = copy_pkg(src, task + "__fixture_collection_error")
    broken_tests = replace_added_line(tpatch, tfile, lambda l: l.startswith(("import ", "from ")),
                                      "import (  # T1 TEST FIXTURE: deliberate collection error")
    (fx / "tests/test_patch.diff").write_text(broken_tests)
    r = grade(fx, None, "fixture_collection_error_nop")
    g = gates.nop_gate(r, f2p, p2p)
    R.record("fixture_collection_error__nop", "nop", True, "reject", "accept" if g["ok"] else "reject",
             "accept" if v1_nop_ok(r) else "reject", g)
    r = grade(fx, gold, "fixture_collection_error_gold")
    g = gates.gold_gate(r, f2p, p2p)
    R.record("fixture_collection_error__gold", "gold", True, "reject", "accept" if g["ok"] else "reject",
             "accept" if v1_gold_ok(r) else "reject", g)

    # 4. behavioural mutant (historical, real) -> killed
    results = {}
    if mutant:
        attempt = ROOT / "runs/20261114T115550_batch5/candidates" / task / "attempt_1"
        results[mutant] = grade(pkg, (attempt / f"run_mutant_{mutant}" / "applied.diff").read_text(),
                                f"mutant_{mutant}")
        v = gates.mutant_verdict(results[mutant], f2p, p2p)
        R.record(f"mutant_{mutant}", "mutant", False, "killed", v["verdict"],
                 "killed" if v1_killed(results[mutant]) else "survived", v)

    # 5. FIXTURE mutant: gold with a SyntaxError in the source -> invalid, never "killed"
    syn = replace_added_line(gold, sfile, lambda l: l.strip() != "",
                             "def t1_fixture_broken(:  # T1 TEST FIXTURE: deliberate syntax error")
    results["fixture_syntax_error"] = r = grade(pkg, syn, "mutant_fixture_syntax_error")
    v = gates.mutant_verdict(r, f2p, p2p)
    R.record("fixture_mutant_syntax_error", "mutant", True, "invalid", v["verdict"],
             "killed" if v1_killed(r) else "survived", v)

    # 6. FIXTURE mutant: patch does not apply -> stage failure, invalid
    corrupt = corrupt_context(gold)
    results["fixture_patch_does_not_apply"] = r = grade(pkg, corrupt, "mutant_fixture_patch_fail")
    v = gates.mutant_verdict(r, f2p, p2p)
    v["container_exit"], v["stage_fail"] = r["exit"], r["stage_fail"]
    R.record("fixture_mutant_patch_does_not_apply", "mutant", True, "invalid", v["verdict"],
             "killed" if v1_killed(r) else "survived", v)
    g = gates.mutation_gate(results, f2p, p2p)
    (out / "mutation_gate.json").write_text(json.dumps(g, indent=1, default=str))

    # 7. full suite (gold + feature tests, entire existing suite)
    def fs(name, files, expected, fixture):
        d = out / "full_suite" / name
        p, log = run_full_suite(files, d)
        g = gates.full_suite_gate(p, log)
        R.record(f"full_suite__{name}", "full_suite", fixture, expected, "accept" if g["ok"] else "reject",
                 None, {**g, "log": log_facts(log)})
        R.cases[-1]["container_exit"] = p.returncode
        return p, g

    fs("gold", {"gold.diff": gold, "tests.diff": tpatch}, "accept", False)
    failing = replace_added_line(tpatch, tfile, lambda l: l.lstrip().startswith("assert "),
                                 "    assert False, 'T1 TEST FIXTURE: deliberate failure'")
    fs("fixture_failing_test", {"gold.diff": gold, "tests.diff": failing}, "reject", True)
    fs("fixture_collection_error", {"gold.diff": gold, "tests.diff": broken_tests}, "reject", True)
    fs("fixture_gold_does_not_apply", {"gold.diff": corrupt, "tests.diff": tpatch}, "reject", True)
    fs("fixture_tests_do_not_apply", {"gold.diff": gold, "tests.diff": corrupt_context(tpatch)}, "reject", True)

    # 8. the V1 full-suite command on the same fixtures (pytest piped through tail, no pipefail)
    for name, tests in (("fixture_failing_test", failing), ("fixture_collection_error", broken_tests)):
        d = out / "full_suite" / f"v1_command_on_{name}"
        p, _ = run_full_suite({"gold.diff": gold, "tests.diff": tests}, d, v1=True)
        R.cases.append({"case": f"v1_full_suite_command__{name}", "kind": "full_suite",
                        "test_fixture": True, "container_exit": p.returncode,
                        "v1_logic": "accept" if v1_full_suite_ok(p) else "reject",
                        "stdout_tail": (p.stdout or "").strip().splitlines()[-3:],
                        "note": "V1 command: pytest piped through tail under bash without pipefail"})
        print(f"{R.cases[-1]['case']:42s} container_exit={p.returncode} v1={R.cases[-1]['v1_logic']}")

    versions = {
        "engine": config.ENGINE,
        "engine_version": subprocess.run([config.ENGINE, "version", "--format", "{{.Server.Version}}"],
                                         capture_output=True, text=True).stdout.strip(),
        "image": tag, "python_host": sys.version.split()[0],
    }
    summary = {"task_copy_of": str(src.relative_to(ROOT)), "versions": versions,
               "note": "new run, not historical evidence; cases with test_fixture=true are deliberate corruptions "
                       "of isolated copies under T1_WORK, never of generated_tasks/",
               "all_as_expected": all(c.get("as_expected", True) for c in R.cases),
               "cases": [{k: c.get(k) for k in ("case", "test_fixture", "expected", "hardened", "v1_logic",
                                                "container_exit")} for c in R.cases]}
    (out / "cases.json").write_text(json.dumps(R.cases, indent=1, default=str))
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({"out": str(out.relative_to(ROOT)), "all_as_expected": summary["all_as_expected"]}))
    return 0 if summary["all_as_expected"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))

"""Regression tests for gold / nop / mutation / full-suite acceptance.

All graded runs are SYNTHETIC (see conftest.py): real pytest + the real template grade.py/parser.py
on made-up modules. ``v1_*`` functions are the acceptance conditions copied verbatim from tag
``v1-preservation-point`` so each defect is shown against the logic it replaces.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import sh, write_tree
from factory import container, gates


# ---------------------------------------------------------------- V1 logic (for comparison only)
def v1_gold_ok(r):
    return r.get("reward") == 1.0 and r["f2p_passed"] == r["f2p_total"] and r["p2p_passed"] == r["p2p_total"]


def v1_nop_ok(r):
    return r.get("reward") == 0.0 and r["f2p_passed"] == 0 and r["p2p_passed"] == r["p2p_total"]


def v1_killed(r):
    return r.get("reward") is not None and r["f2p_passed"] < r["f2p_total"]


def v1_full_suite_ok(p):
    tail = (p.stdout or "").strip().splitlines()[-3:]
    return p.returncode == 0 and not re.search(r"(\d+) failed", "\n".join(tail))


V1_FULL_SUITE_CMD = "cd {app} && git apply {sol}/gold.diff && git apply {sol}/tests.diff && {pytest} 2>&1 | tail -3"


# ---------------------------------------------------------------- synthetic project
CONFTEST = "# makes the project root importable\n"
LIB_BASE = "def old(x):\n    return x + 1\n"
LIB_GOLD = LIB_BASE + "\n\ndef shout(s):\n    return s.upper() + '!'\n"
FEATURE_TESTS = """\
import mylib


def test_shout_basic():
    assert mylib.shout("hi") == "HI!"


def test_shout_empty():
    assert mylib.shout("") == "!"
"""
OLD_TESTS = """\
import mylib


def test_old():
    assert mylib.old(1) == 2
"""
F2P = ["tests/test_feature.py::test_shout_basic", "tests/test_feature.py::test_shout_empty"]
P2P = ["tests/test_old.py::test_old"]


def project(lib=LIB_GOLD, feature=FEATURE_TESTS, old=OLD_TESTS, **extra):
    files = {"conftest.py": CONFTEST, "mylib.py": lib, "tests/test_old.py": old, **extra}
    if feature is not None:
        files["tests/test_feature.py"] = feature
    return files


# ---------------------------------------------------------------- gold / nop: correct cases
def test_gold_correct_is_accepted(grade):
    r = grade(project(), F2P, P2P)
    g = gates.gold_gate(r, F2P, P2P)
    assert g["ok"], g["detail"]["problems"]
    assert g["detail"]["f2p_status_counts"] == {"PASSED": 2}
    assert v1_gold_ok(r)


def test_nop_correct_is_accepted(grade):
    r = grade(project(lib=LIB_BASE), F2P, P2P)
    g = gates.nop_gate(r, F2P, P2P)
    assert g["ok"], g["detail"]["problems"]
    assert g["detail"]["f2p_status_counts"] == {"FAILED": 2}
    assert g["detail"]["f2p_all_reported"] is True


# ---------------------------------------------------------------- nop: masquerading failures
def test_nop_rejects_missing_f2p_record(grade):
    f2p = F2P + ["tests/test_feature.py::test_shout_unicode"]  # expected but never collected
    r = grade(project(lib=LIB_BASE), f2p, P2P)
    g = gates.nop_gate(r, f2p, P2P)
    assert v1_nop_ok(r), "V1 accepted a run in which an expected F2P test never ran"
    assert not g["ok"]
    assert g["detail"]["f2p_all_reported"] is False
    assert g["detail"]["not_failed"] == {"tests/test_feature.py::test_shout_unicode": "MISSING"}


def test_nop_rejects_absent_feature_test_file(grade):
    r = grade(project(lib=LIB_BASE, feature=None), F2P, P2P,
              graded_files=["tests/test_feature.py", "tests/test_old.py"])
    assert v1_nop_ok(r)
    g = gates.nop_gate(r, F2P, P2P)
    assert not g["ok"] and g["detail"]["f2p_status_counts"] == {"MISSING": 2}


def test_nop_rejects_collection_import_error(grade):
    broken = "from mylib import shout\n\n" + FEATURE_TESTS.replace("import mylib\n", "")
    r = grade(project(lib=LIB_BASE, feature=broken), F2P, P2P)
    assert v1_nop_ok(r), "V1 accepted a collection ImportError as 'feature absent'"
    g = gates.nop_gate(r, F2P, P2P)
    assert not g["ok"]
    assert any("collection/import errors" in p for p in g["detail"]["problems"])
    assert any("error(s)" in p for p in g["detail"]["problems"])


def test_nop_rejects_setup_error(grade):
    feature = FEATURE_TESTS.replace("def test_shout_basic():", "def test_shout_basic(no_such_fixture):")
    r = grade(project(lib=LIB_BASE, feature=feature), F2P, P2P)
    assert v1_nop_ok(r)
    g = gates.nop_gate(r, F2P, P2P)
    assert not g["ok"]
    assert g["detail"]["not_failed"] == {"tests/test_feature.py::test_shout_basic": "ERROR"}


def test_nop_rejects_already_passing_f2p(grade):
    lib = LIB_BASE + "\n\ndef shout(s):\n    return 'HI!' if s else ''\n"
    r = grade(project(lib=lib), F2P, P2P)
    g = gates.nop_gate(r, F2P, P2P)
    assert not v1_nop_ok(r) and not g["ok"]
    assert g["detail"]["not_failed"] == {"tests/test_feature.py::test_shout_basic": "PASSED"}


def test_nop_rejects_p2p_regression(grade):
    r = grade(project(lib="def old(x):\n    return x\n"), F2P, P2P)
    g = gates.nop_gate(r, F2P, P2P)
    assert not v1_nop_ok(r) and not g["ok"]
    assert g["detail"]["p2p_not_passed"] == {"tests/test_old.py::test_old": "FAILED"}


# ---------------------------------------------------------------- duplicate / inconsistent records
TEARDOWN_ERROR = """\
import pytest


@pytest.fixture
def bad_teardown():
    yield
    raise RuntimeError("teardown broke")
"""


def test_pass_plus_teardown_error_is_inconsistent(grade):
    old = OLD_TESTS.replace("def test_old():", "def test_old(bad_teardown):")
    files = project(old=old)
    files["conftest.py"] = CONFTEST + TEARDOWN_ERROR
    r = grade(files, F2P, P2P)
    assert sorted(s for n, s in r["records"] if n == P2P[0]) == ["ERROR", "PASSED"]
    g = gates.gold_gate(r, F2P, P2P)
    assert not g["ok"]
    assert g["detail"]["p2p_status_counts"] == {"INCONSISTENT(ERROR+PASSED)": 1}


def test_repeated_identical_records_are_rejected(grade):
    r = grade(project(), F2P, P2P)
    r["records"] = r["records"] + [r["records"][0]]
    assert v1_gold_ok(r)
    assert any("repeated identical" in p for p in gates.gold_gate(r, F2P, P2P)["detail"]["problems"])


# ---------------------------------------------------------------- totals and expected lists
def test_tampered_grader_totals_are_rejected(grade):
    r = grade(project(), F2P, P2P)
    r["f2p_total"] = r["f2p_passed"] = 1  # e.g. a fail_to_pass.json that lost an id
    assert v1_gold_ok(r)
    g = gates.gold_gate(r, F2P, P2P)
    assert not g["ok"] and any("grader totals" in p for p in g["detail"]["problems"])


def test_duplicate_expected_ids_are_rejected(grade):
    f2p = F2P + [F2P[0]]  # grade.py dedups via set(), so its totals would look fine
    r = grade(project(), f2p, P2P)
    assert v1_gold_ok(r)
    assert any("duplicate ids in expected F2P" in p for p in gates.gold_gate(r, f2p, P2P)["detail"]["problems"])


def test_overlapping_f2p_p2p_is_rejected(grade):
    p2p = P2P + [F2P[0]]
    r = grade(project(), F2P, p2p)
    assert any("both F2P and P2P" in p for p in gates.gold_gate(r, F2P, p2p)["detail"]["problems"])


def test_parser_dropping_records_is_detected(grade):
    r = grade(project(), F2P, P2P)
    r["records"] = [x for x in r["records"] if x[0] != "tests/test_old.py::test_old"]
    r["p2p_total"] = r["p2p_passed"] = 0
    g = gates.gold_gate(r, F2P, [])
    assert not g["ok"]
    assert any("disagree with pytest summary" in p for p in g["detail"]["problems"])


def test_missing_grading_result_and_bad_verifier_exit(tmp_path):
    (tmp_path / "container.log").write_text("exit=0\n--- stdout\nTEST_SH_EXIT=1\n")
    r = container.read_result(tmp_path)
    assert r["reward"] is None and r["test_sh_exit"] == 1
    for gate in (gates.gold_gate, gates.nop_gate):
        assert not gate(r, F2P, P2P)["ok"]


def test_patch_apply_failure_is_reported(tmp_path):
    (tmp_path / "container.log").write_text("exit=91\n--- stdout\nT1_STAGE_FAIL=apply_patch\n")
    r = container.read_result(tmp_path)
    p = gates.classify_run(r, F2P, P2P)["problems"]
    assert any("apply_patch" in x for x in p)


# ---------------------------------------------------------------- mutants
LAZY_FEATURE_TESTS = """\
def test_shout_basic():
    from feature import shout
    assert shout("hi") == "HI!"


def test_shout_empty():
    from feature import shout
    assert shout("") == "!"
"""
FEATURE_GOLD = "def shout(s):\n    return s.upper() + '!'\n"


def test_mutant_behavioural_failure_is_killed(grade):
    r = grade(project(lib=LIB_BASE + "\n\ndef shout(s):\n    return s.upper()\n"), F2P, P2P)
    v = gates.mutant_verdict(r, F2P, P2P)
    assert v["verdict"] == "killed" and v1_killed(r)
    assert v["f2p_failed"] == F2P


def test_mutant_survivor_is_reported(grade):
    r = grade(project(), F2P, P2P)
    assert gates.mutant_verdict(r, F2P, P2P)["verdict"] == "survived"
    assert not gates.mutation_gate({"same_as_gold": r}, F2P, P2P)["ok"]


def test_mutant_syntax_error_at_import_is_invalid(grade):
    r = grade(project(lib=LIB_GOLD + "\ndef broken(:\n"), F2P, P2P)
    assert v1_killed(r), "V1 counted a SyntaxError that breaks collection as a kill"
    v = gates.mutant_verdict(r, F2P, P2P)
    assert v["verdict"] == "invalid"
    assert any("collection/import errors" in p for p in v["problems"])


def test_mutant_lazy_import_syntax_error_is_invalid(grade):
    files = project(feature=LAZY_FEATURE_TESTS, **{"feature.py": FEATURE_GOLD + "\ndef broken(:\n"})
    r = grade(files, F2P, P2P)
    assert r["statuses"][F2P[0]] == "FAILED" and v1_killed(r), \
        "the failure is a call-phase FAILED, so V1 counted it as a kill"
    v = gates.mutant_verdict(r, F2P, P2P)
    assert v["verdict"] == "invalid"
    assert v["failed_by_import_or_syntax_error"] == {n: ["SyntaxError"] for n in F2P}


def test_mutant_lazy_import_behavioural_failure_is_killed(grade):
    files = project(feature=LAZY_FEATURE_TESTS, **{"feature.py": "def shout(s):\n    return s + '!'\n"})
    r = grade(files, F2P, P2P)
    v = gates.mutant_verdict(r, F2P, P2P)
    assert v["verdict"] == "killed" and v["f2p_failed"] == [F2P[0]]


def test_mutant_that_did_not_apply_is_invalid(tmp_path):
    (tmp_path / "container.log").write_text("exit=91\n--- stdout\nT1_STAGE_FAIL=apply_patch\n")
    r = container.read_result(tmp_path)
    assert gates.mutant_verdict(r, F2P, P2P)["verdict"] == "invalid" and not v1_killed(r)


def test_mutation_gate_needs_every_mutant_killed(grade):
    killed = grade(project(lib=LIB_BASE + "\n\ndef shout(s):\n    return s.upper()\n"), F2P, P2P)
    invalid = grade(project(lib=LIB_GOLD + "\ndef broken(:\n"), F2P, P2P)
    g = gates.mutation_gate({"a": killed, "b": invalid}, F2P, P2P)
    assert not g["ok"] and g["detail"]["verdicts"] == {"a": "killed", "b": "invalid"}
    assert v1_killed(killed) and v1_killed(invalid)
    assert gates.mutation_gate({"a": killed}, F2P, P2P)["ok"]
    assert not gates.mutation_gate({}, F2P, P2P)["ok"]


# ---------------------------------------------------------------- full suite
def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def full_suite_case(tmp: Path, gold_lib=LIB_GOLD, feature=FEATURE_TESTS, gold_diff=None):
    """A git repo at 'base' plus gold.diff/tests.diff produced by real git, as in the pipeline."""
    app, sol, out = tmp / "app", tmp / "sol", tmp / "out"
    sol.mkdir()
    out.mkdir()
    write_tree(app, {"conftest.py": CONFTEST, "mylib.py": LIB_BASE, "tests/test_old.py": OLD_TESTS})
    _git(app, "init", "-q")
    _git(app, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(app, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    (app / "mylib.py").write_text(gold_lib)
    gd = subprocess.run(["git", "diff"], cwd=app, capture_output=True, text=True).stdout
    _git(app, "checkout", "-q", "--", "mylib.py")
    (sol / "gold.diff").write_text(gold_diff if gold_diff is not None else gd)
    (app / "tests/test_feature.py").write_text(feature)
    _git(app, "add", "-N", "tests/test_feature.py")
    td = subprocess.run(["git", "diff"], cwd=app, capture_output=True, text=True).stdout
    _git(app, "rm", "-q", "--cached", "tests/test_feature.py")
    (app / "tests/test_feature.py").unlink()
    (sol / "tests.diff").write_text(td)
    return app, sol, out


PYTEST = f"{sys.executable} -m pytest -q -p no:cacheprovider --color=no tests"


def run_new(app, sol, out, pytest_cmd=PYTEST):
    p = sh(container.full_suite_script(app=str(app), sol=str(sol), out=str(out), pytest=pytest_cmd), app)
    log = (out / "pytest.log").read_text() if (out / "pytest.log").exists() else None
    return p, gates.full_suite_gate(p, log)


def run_v1(app, sol, pytest_cmd=PYTEST):
    return sh(V1_FULL_SUITE_CMD.format(app=app, sol=sol, pytest=pytest_cmd), app)


def _reset(app):
    _git(app, "checkout", "-q", "--", ".")
    _git(app, "clean", "-qfd")


def test_full_suite_success(tmp_path):
    app, sol, out = full_suite_case(tmp_path)
    p, g = run_new(app, sol, out)
    assert g["ok"], g["detail"]["problems"]
    assert g["detail"]["pytest_exit"] == 0 and g["detail"]["summary"]["passed"] == 3
    assert "3 passed" in (out / "pytest.log").read_text()
    assert any("3 passed" in line for line in g["detail"]["tail"])


@pytest.mark.parametrize("case", ["collection_error", "zero_tests", "crash"])
def test_full_suite_failure_hidden_by_tail_is_caught(tmp_path, case):
    feature, cmd = FEATURE_TESTS, PYTEST
    if case == "collection_error":
        feature = "import does_not_exist\n" + FEATURE_TESTS
    elif case == "zero_tests":
        cmd = PYTEST + " -k no_such_test_name"
    elif case == "crash":
        feature = FEATURE_TESTS + "\n\ndef test_zz_crash():\n    import os, signal\n    os.kill(os.getpid(), signal.SIGKILL)\n"
    app, sol, out = full_suite_case(tmp_path, feature=feature)
    v1 = run_v1(app, sol, cmd)
    assert v1.returncode == 0 and v1_full_suite_ok(v1), f"V1 accepted {case}: {v1.stdout[-300:]}"
    _reset(app)
    p, g = run_new(app, sol, out, cmd)
    assert not g["ok"]
    assert p.returncode != 0 and g["detail"]["pytest_exit"] != 0
    assert (out / "pytest.log").exists()


def test_full_suite_test_failure(tmp_path):
    app, sol, out = full_suite_case(tmp_path, gold_lib=LIB_BASE + "\n\ndef shout(s):\n    return s\n")
    p, g = run_new(app, sol, out)
    assert not g["ok"] and g["detail"]["pytest_exit"] == 1
    assert g["detail"]["summary"]["failed"] == 2


@pytest.mark.parametrize("which", ["gold", "tests"])
def test_full_suite_patch_failure_is_propagated(tmp_path, which):
    app, sol, out = full_suite_case(tmp_path)
    (sol / f"{which}.diff").write_text("this is not a diff\n")
    p, g = run_new(app, sol, out)
    assert not g["ok"] and p.returncode in (91, 92)
    assert g["detail"]["problems"][0] == f"stage failed: apply_{which}"
    assert g["detail"]["pytest_exit"] is None


def test_full_suite_unwritable_log_is_propagated(tmp_path):
    app, sol, out = full_suite_case(tmp_path)
    p, g = run_new(app, sol, out / "missing_dir")
    assert not g["ok"] and p.returncode != 0


def test_full_suite_script_has_no_bash_only_syntax():
    s = container.full_suite_script()
    assert "pipefail" not in s and "[[" not in s and "PIPESTATUS" not in s and "|" not in s.replace("||", "")


# ---------------------------------------------------------------- summary-line parsing
@pytest.mark.parametrize("line,expect", [
    ("================= 16 failed, 1315 passed, 23 skipped in 3.93s ==================",
     {"failed": 16, "passed": 1315, "skipped": 23, "errors": 0}),
    ("2450 passed, 24 skipped, 31000 deselected, 1 xfailed in 6.06s", {"passed": 2450, "xfailed": 1}),
    ("=== 1 passed, 1 error in 0.02s ===", {"passed": 1, "errors": 1}),
    ("==== 3 passed, 2 warnings in 65.23s (0:01:05) ====", {"passed": 3, "warnings": 2}),
    ("============================ no tests ran in 0.01s =============================",
     {"no_tests_ran": True, "passed": 0}),
])
def test_pytest_summary_parsing(line, expect):
    s = gates.pytest_summary("noise\n" + line + "\n")
    assert {k: s[k] for k in expect} == expect


def test_pytest_summary_absent_when_killed():
    assert gates.pytest_summary("tests/test_x.py ....\n") is None

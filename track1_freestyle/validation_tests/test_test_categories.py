"""Test-category handling: F2P, upstream P2P and newly authored compatibility tests.

SYNTHETIC FIXTURES (see conftest.py): real pytest + the real template grade.py/parser.py on made-up
modules. ``tests/test_compat.py`` plays the role of an authored compatibility test (passes at base
and under gold); ``tests/test_old.py`` plays an upstream regression test.
"""
from __future__ import annotations

import json
import re

import pytest
from conftest import ROOT
from test_validation_gates import F2P, FEATURE_TESTS, LIB_BASE, LIB_GOLD, OLD_TESTS, P2P, v1_killed

from factory import gates, package, pipeline, planner
from factory.families import PLANNED, REGISTRY
from factory.model import Draft

COMPAT_TESTS = """\
import mylib


def test_old_still_increments():
    assert mylib.old(41) == 42
"""
AUTHORED = ["tests/test_compat.py::test_old_still_increments"]
P2P_ALL = P2P + AUTHORED


def project(lib=LIB_GOLD, compat=COMPAT_TESTS):
    return {"conftest.py": "", "mylib.py": lib, "tests/test_old.py": OLD_TESTS,
            "tests/test_feature.py": FEATURE_TESTS, "tests/test_compat.py": compat}


def draft(**kw):
    base = dict(family="x", slug="x", title="x", knobs={}, instruction="", gold_edits=[],
                test_files={"tests/test_feature.py": FEATURE_TESTS}, focus_symbols=[], mutants=[],
                novelty_probes=[], novelty_queries=[], axes={},
                compat_test_files={"tests/test_compat.py": COMPAT_TESTS})
    base.update(kw)
    return Draft(**base)


def test_ids_are_split_by_file_category():
    d = draft()
    assert pipeline.f2p_ids(d) == F2P
    assert pipeline.authored_p2p_ids(d) == AUTHORED


def test_authored_compat_tests_pass_nop_and_gold_as_p2p(grade):
    nop = grade(project(lib=LIB_BASE), F2P, P2P_ALL)
    gold = grade(project(), F2P, P2P_ALL)
    assert gates.nop_gate(nop, F2P, P2P_ALL)["ok"]
    assert gates.gold_gate(gold, F2P, P2P_ALL)["ok"]
    assert (nop["reward"], gold["reward"]) == (0.0, 1.0)


def test_baseline_passing_test_cannot_be_forced_into_f2p(grade):
    f2p = F2P + AUTHORED
    nop = grade(project(lib=LIB_BASE), f2p, P2P)
    g = gates.nop_gate(nop, f2p, P2P)
    assert not g["ok"]
    assert g["detail"]["not_failed"] == {AUTHORED[0]: "PASSED"}


def test_compat_test_failing_at_base_is_rejected(grade):
    broken = COMPAT_TESTS.replace("== 42", "== 0")
    nop = grade(project(lib=LIB_BASE, compat=broken), F2P, P2P_ALL)
    g = gates.nop_gate(nop, F2P, P2P_ALL)
    assert not g["ok"] and g["detail"]["p2p_not_passed"] == {AUTHORED[0]: "FAILED"}


def test_compat_violation_gets_no_full_reward_and_counts_as_killed(grade):
    # Implements the feature correctly but changes existing behaviour pinned only by the authored test.
    lib = LIB_GOLD.replace("return x + 1", "return x + 1 if x != 41 else 0")
    r = grade(project(lib=lib), F2P, P2P_ALL)
    assert r["f2p_passed"] == r["f2p_total"] and r["reward"] == 0.0
    v = gates.mutant_verdict(r, F2P, P2P_ALL, AUTHORED)
    assert v["verdict"] == "killed"
    assert v["killed_by"] == {"p2p_authored": AUTHORED}
    assert not v1_killed(r), "V1 counted only F2P failures, so this mutant would have survived"


def test_upstream_p2p_failure_is_labelled_upstream(grade):
    lib = LIB_GOLD.replace("return x + 1", "return x + 2")
    r = grade(project(lib=lib, compat=COMPAT_TESTS.replace("== 42", "== 43")), F2P, P2P_ALL)
    v = gates.mutant_verdict(r, F2P, P2P_ALL, AUTHORED)
    assert v["verdict"] == "killed" and v["killed_by"] == {"p2p_upstream": P2P}


def test_compat_failure_from_import_error_is_invalid_not_killed(grade):
    compat = COMPAT_TESTS.replace("def test_old_still_increments():\n",
                                  "def test_old_still_increments():\n    from mylib import gone  # noqa: F401\n")
    r = grade(project(compat=compat), F2P, P2P_ALL)
    v = gates.mutant_verdict(r, F2P, P2P_ALL, AUTHORED)
    assert v["verdict"] == "invalid"
    assert v["failed_by_import_or_syntax_error"] == {AUTHORED[0]: ["ImportError"]}


COV = {"status": {P2P[0]: "PASSED", "tests/test_flaky.py::test_x": "FAILED"}}
PATCH = "--- /dev/null\n+++ b/tests/test_feature.py\n--- /dev/null\n+++ b/tests/test_compat.py\n"


def test_category_gate_accepts_a_clean_partition():
    g = gates.test_categories(draft(), F2P, P2P, AUTHORED, COV, PATCH)
    assert g["ok"], g["detail"]["problems"]
    assert g["detail"]["counts"] == {"f2p": 2, "p2p_upstream": 1, "p2p_authored": 1}


@pytest.mark.parametrize("f2p,upstream,authored,patch,needle", [
    (F2P + AUTHORED, P2P, AUTHORED, PATCH, "F2P ids outside their files"),
    (F2P, P2P, AUTHORED + [F2P[0]], PATCH, "authored P2P ids outside their files"),
    (F2P, P2P + AUTHORED, AUTHORED, PATCH, "upstream/authored overlap"),
    (F2P, P2P, AUTHORED, PATCH + "+++ b/tests/test_old.py\n", "files the test patch adds or edits"),
    (F2P, ["tests/test_flaky.py::test_x"], AUTHORED, PATCH, "not PASSED in the base suite run"),
], ids=["compat_in_f2p", "feature_in_authored", "authored_called_upstream", "upstream_edited_by_patch",
        "upstream_not_green_at_base"])
def test_category_gate_rejects_mislabelled_tests(f2p, upstream, authored, patch, needle):
    g = gates.test_categories(draft(), f2p, upstream, authored, COV, patch)
    assert not g["ok"] and any(needle in p for p in g["detail"]["problems"]), g["detail"]["problems"]


def test_package_records_provenance_only_for_authored_tests(tmp_path):
    prov = {"upstream_regression": P2P, "authored_compatibility": AUTHORED}
    pkg = package.write(draft(), "", "", F2P, P2P_ALL, tmp_path / "a", prov)
    assert json.loads((pkg / "tests/p2p_provenance.json").read_text()) == prov
    assert json.loads((pkg / "tests/pass_to_pass.json").read_text()) == P2P_ALL
    v1_like = package.write(draft(compat_test_files={}), "", "", F2P, P2P, tmp_path / "b")
    assert not (v1_like / "tests/p2p_provenance.json").exists()


def test_v1_batch_plan_is_unchanged_by_the_new_family():
    saved = json.loads((ROOT / "runs/20261114T115550_batch5/plan.json").read_text())
    assert [list(x) for x in planner.plan(5, 2026)] == saved
    assert "collisions" in REGISTRY and "collisions" not in PLANNED


def test_v1_blueprints_have_no_authored_compat_tests():
    for fam in PLANNED:
        mod = REGISTRY[fam]
        d = mod.build(planner.knob_space(mod)[0])
        assert d.compat_test_files == {}


def test_collision_blueprint_categories():
    d = REGISTRY["collisions"].build({"scope": "diagnostics"})
    f2p, authored = pipeline.f2p_ids(d), pipeline.authored_p2p_ids(d)
    assert f2p and authored and not set(f2p) & set(authored)
    assert all(n.startswith("tests/test_command_collection_providers.py::") for n in f2p)
    assert all(n.startswith("tests/test_command_collection_compat.py::") for n in authored)
    # Feature tests import only stdlib, pytest and click at module level, so at base they fail
    # inside their own call instead of erroring at collection.
    body = d.test_files["tests/test_command_collection_providers.py"]
    imports = re.findall(r"^(?:import|from) (\S+)", body, re.M)
    assert set(imports) <= {"warnings", "pytest", "click", "click.testing"}

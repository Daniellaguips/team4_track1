"""Helpers for the validation-gate regression tests.

SYNTHETIC FIXTURES: every graded run here is produced by running real pytest on small, made-up
test modules in a temporary directory and grading the output with the factory's real template
``grade.py`` + ``parser.py``. They exercise the acceptance logic; they are not Harbor evidence and
do not involve click or any V1 task.
"""
from __future__ import annotations

import json
import os
import runpy
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from factory import config, container  # noqa: E402

PYTEST_FLAGS = "-rA --tb=short -p no:cacheprovider -p no:randomly --color=no --continue-on-collection-errors"


def write_tree(base: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(body))


def grade_synthetic(tmp: Path, files: dict[str, str], f2p: list[str], p2p: list[str],
                    graded_files: list[str] | None = None) -> dict:
    """Run pytest on ``files`` exactly as a task's run_script.sh does, grade with the real
    grade.py/parser.py, and load the result the way container.grade does."""
    app, tdir, out = tmp / "app", tmp / "pkg_tests", tmp / "run"
    write_tree(app, files)
    tdir.mkdir()
    for name in ("grade.py", "parser.py"):
        shutil.copy(config.TEMPLATES / name, tdir / name)
    (tdir / "fail_to_pass.json").write_text(json.dumps(f2p))
    (tdir / "pass_to_pass.json").write_text(json.dumps(p2p))
    (tdir / "test_patch.diff").write_text("")
    targets = graded_files or sorted({n.split("::")[0] for n in f2p + p2p})
    (tdir / "run_script.sh").write_text(
        f'cd "{app}"\nPRESENT=""\nfor f in {" ".join(targets)}; do [ -e "$f" ] && PRESENT="$PRESENT $f"; done\n'
        f'"{sys.executable}" -m pytest $PRESENT {PYTEST_FLAGS}\n')
    vdir = out / "verifier"
    vdir.mkdir(parents=True)
    g = runpy.run_path(str(tdir / "grade.py"), run_name="synthetic_grade")["main"].__globals__
    g["APP"], g["REWARD_DIR"] = str(app), str(vdir)
    env_path = os.environ["PATH"]
    os.environ["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env_path}"
    try:
        g["main"]()
    finally:
        os.environ["PATH"] = env_path
    (out / "container.log").write_text("exit=0 secs=0.0\n--- stdout\nTEST_SH_EXIT=0\n--- stderr\n")
    return container.read_result(out)


@pytest.fixture
def grade(tmp_path):
    n = {"i": 0}

    def _grade(files, f2p, p2p, **kw):
        n["i"] += 1
        d = tmp_path / f"case{n['i']}"
        d.mkdir()
        return grade_synthetic(d, files, f2p, p2p, **kw)
    return _grade


TEST_SH = os.environ.get("T1_TEST_SH", "/bin/sh")


def sh(script: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run under a POSIX shell (T1_TEST_SH, e.g. /bin/dash) to show the scripts need no bash
    features or pipefail."""
    return subprocess.run([TEST_SH, "-c", script], cwd=cwd, capture_output=True, text=True)

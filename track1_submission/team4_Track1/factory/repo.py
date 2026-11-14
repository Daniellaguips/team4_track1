"""Upstream checkout, anchored edits and diff production (host side, plain git)."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config
from .model import Edit


class GroundingError(Exception):
    pass


def sh(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def ensure_upstream() -> Path:
    """Full-history clone of upstream (needed for novelty checks against live main)."""
    up = config.UPSTREAM
    if not (up / ".git").exists():
        up.parent.mkdir(parents=True, exist_ok=True)
        sh(["git", "clone", "--quiet", config.REPO_URL, str(up)])
    else:
        sh(["git", "fetch", "--quiet", "origin"], cwd=up, check=False)
    sh(["git", "cat-file", "-e", config.BASE_COMMIT + "^{commit}"], cwd=up)
    return up


def export_base(dest: Path) -> Path:
    """Materialise the base commit as a fresh single-commit git tree (mirrors the Dockerfile)."""
    up = ensure_upstream()
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(["git", "archive", config.BASE_COMMIT], cwd=up, check=True,
                             capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
    for c in (["git", "init", "--quiet"], ["git", "config", "user.email", "bench@local"],
              ["git", "config", "user.name", "bench"], ["git", "add", "-A"],
              ["git", "commit", "--quiet", "-m", "base"]):
        sh(c, cwd=dest)
    return dest


def apply_edits(tree: Path, edits: list[Edit] | tuple[Edit, ...]) -> None:
    for e in edits:
        fp = tree / e.path
        if not fp.exists():
            if e.mode == "create":
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(e.text)
                continue
            raise GroundingError(f"{e.path}: file does not exist at base")
        src = fp.read_text()
        n = src.count(e.anchor)
        if n != 1:
            raise GroundingError(f"{e.path}: anchor occurs {n} times (need exactly 1): {e.anchor[:60]!r}")
        if e.mode == "after":
            new = src.replace(e.anchor, e.anchor + e.text)
        elif e.mode == "before":
            new = src.replace(e.anchor, e.text + e.anchor)
        elif e.mode == "replace":
            new = src.replace(e.anchor, e.text)
        else:
            raise ValueError(e.mode)
        fp.write_text(new)


def diff_of(tree: Path) -> str:
    sh(["git", "add", "-A"], cwd=tree)
    out = sh(["git", "diff", "--cached", "--no-color", "--no-ext-diff"], cwd=tree).stdout
    sh(["git", "reset", "--quiet"], cwd=tree)
    return out


def make_patch(edits, test_files: dict[str, str] | None = None) -> tuple[str, Path]:
    """Return (diff, tree) for base + edits (+ new test files). Caller removes the tree."""
    tree = Path(tempfile.mkdtemp(prefix="t1tree_", dir=str(config.WORK)))
    export_base(tree)
    apply_edits(tree, edits)
    for rel, body in (test_files or {}).items():
        p = tree / rel
        if p.exists():
            raise GroundingError(f"feature test file {rel} already exists at base")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return diff_of(tree), tree


def gold_and_test_patches(draft) -> tuple[str, str]:
    gold, t1 = make_patch(draft.gold_edits)
    shutil.rmtree(t1, ignore_errors=True)
    tests, t2 = make_patch([], draft.test_files)
    shutil.rmtree(t2, ignore_errors=True)
    return gold, tests


def mutant_patch(draft, mutant) -> str:
    """Gold edits followed by the mutant's edits (anchors resolved on the gold tree)."""
    diff, tree = make_patch(list(draft.gold_edits) + list(mutant.edits))
    shutil.rmtree(tree, ignore_errors=True)
    return diff


def touched_line_ranges(diff: str) -> dict[str, list[tuple[int, int]]]:
    """Old-side line ranges (inclusive) per file of a unified diff."""
    import re
    out: dict[str, list[tuple[int, int]]] = {}
    cur = None
    for ln in diff.splitlines():
        if ln.startswith("--- a/"):
            cur = ln[6:]
        elif ln.startswith("--- /dev/null"):
            cur = None
        m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+", ln)
        if m and cur:
            start, n = int(m.group(1)), int(m.group(2) or 1)
            out.setdefault(cur, []).append((start, start + max(n, 1) - 1))
    return out

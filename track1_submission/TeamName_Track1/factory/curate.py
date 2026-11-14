"""Programmatic regression (PASS_TO_PASS) curation from per-test coverage at the base commit.

1. Once per base: run the full existing suite in the task image under coverage with per-test
   contexts (pytest-cov ``--cov-context=test``) and keep the pass/fail status of every test.
2. Per task: the touched symbols are the functions/methods enclosing every gold hunk (old side)
   plus the blueprint's declared focus symbols (the existing code the feature extends or mirrors).
3. For every touched symbol take the tests that execute the most of its lines; union, cap, keep
   only tests that pass at base. Each selected test records *why* it was selected.
"""
from __future__ import annotations

import ast
import json
import re
import sqlite3
from pathlib import Path

from . import config, container, repo

COV_TOOLS = "coverage==7.17.3 pytest-cov==7.1.0"
SAFE_ID = re.compile(r"^tests/[\w/]+\.py::[\w]+(\[[\w.\-]+\])?$")


def base_coverage(cache: Path) -> dict:
    """Returns {"status": {nodeid: status}, "lines": {file: {line: [nodeids]}}} (cached)."""
    idx = cache / "coverage_index.json"
    if idx.exists():
        return json.loads(idx.read_text())
    cache.mkdir(parents=True, exist_ok=True)
    cmd = (f"set -e; /app/.venv/bin/pip install --quiet {COV_TOOLS} >/out/pip.log 2>&1; "
           "/app/.venv/bin/pip freeze > /out/freeze.txt; cd /app; set +e; "
           "python -m pytest -p no:cacheprovider -rA --color=no -q --cov=click --cov-branch "
           "--cov-context=test --cov-report= tests > /out/pytest.log 2>&1; "
           "echo PYTEST_EXIT=$? >> /out/pytest.log; cp .coverage /out/coverage.sqlite")
    p = container.run(cmd, mounts={str(cache.resolve()): "/out"}, network=True, timeout=3600)
    (cache / "container.log").write_text(p.stdout[-5000:] + p.stderr[-5000:])
    if not (cache / "coverage.sqlite").exists():
        raise RuntimeError("coverage run failed; see " + str(cache / "container.log"))

    import importlib.util
    spec = importlib.util.spec_from_file_location("t1parser", config.TEMPLATES / "parser.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)  # type: ignore
    log = (cache / "pytest.log").read_text(errors="replace")
    status = {r.name: r.status.name for r in mod.parse_test_output(log, "")}

    db = sqlite3.connect(cache / "coverage.sqlite")
    files = {fid: path for fid, path in db.execute("select id, path from file")}
    ctxs = {cid: c for cid, c in db.execute("select id, context from context")}
    lines: dict[str, dict[int, set[str]]] = {}
    rows = db.execute("select file_id, context_id, fromno, tono from arc").fetchall()
    for fid, cid, a, b in rows:
        c = ctxs.get(cid, "")
        if not c or "|" not in c:
            continue
        nodeid = c.split("|", 1)[0]
        path = files[fid]
        m = re.search(r"/(src/click/.+\.py)$", path)
        if not m:
            continue
        rel = m.group(1)
        d = lines.setdefault(rel, {})
        for ln in (a, b):
            if ln > 0:
                d.setdefault(ln, set()).add(nodeid)
    out = {"status": status,
           "lines": {f: {str(k): sorted(v) for k, v in d.items()} for f, d in lines.items()},
           "tools": COV_TOOLS,
           "n_tests": len(status),
           "n_passed": sum(1 for s in status.values() if s == "PASSED")}
    idx.write_text(json.dumps(out))
    return out


def _symbols(src: str) -> dict[str, tuple[int, int]]:
    """Qualname -> (first, last) line of every function/method/class."""
    tree = ast.parse(src)
    out: dict[str, tuple[int, int]] = {}

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                q = f"{prefix}{ch.name}"
                out[q] = (ch.lineno, ch.end_lineno or ch.lineno)
                walk(ch, q + ".")
    walk(tree, "")
    return out


def touched_symbols(gold_diff: str, focus: list[str], base_tree: Path) -> dict[str, dict]:
    res: dict[str, dict] = {}
    for f, ranges in repo.touched_line_ranges(gold_diff).items():
        if not f.startswith("src/"):
            continue
        syms = _symbols((base_tree / f).read_text())
        for lo, hi in ranges:
            best = None
            for q, (a, b) in syms.items():
                if a <= hi and lo <= b and not q.count(".") < 0:
                    if best is None or (b - a) < (syms[best][1] - syms[best][0]):
                        best = q
            if best and not _is_class_only(best, syms, lo, hi):
                res[f"{f}::{best}"] = {"lines": syms[best], "reason": "encloses gold hunk"}
    for fs in focus:
        f, q = fs.split("::", 1)
        syms = _symbols((base_tree / f).read_text())
        if q not in syms:
            raise repo.GroundingError(f"focus symbol {fs} does not exist at base")
        res.setdefault(fs, {"lines": syms[q], "reason": "declared focus symbol (feature extends it)"})
    return res


def _is_class_only(q, syms, lo, hi) -> bool:
    # A hunk that only adds a new top-level class/function between existing ones is not a
    # modification of the neighbour it happens to touch through diff context lines.
    a, b = syms[q]
    return lo < a or hi > b


def select_p2p(cov: dict, touched: dict[str, dict], exclude_files: set[str]) -> tuple[list[str], dict]:
    status = cov["status"]
    picked: dict[str, list[str]] = {}
    per_symbol: dict[str, list[str]] = {}
    for sym, info in touched.items():
        f = sym.split("::", 1)[0]
        a, b = info["lines"]
        flines = cov["lines"].get(f, {})
        score: dict[str, int] = {}
        for ln in range(a, b + 1):
            for nid in flines.get(str(ln), []):
                score[nid] = score.get(nid, 0) + 1
        ranked = sorted((n for n in score if status.get(n) == "PASSED" and SAFE_ID.match(n)
                         and n.split("::")[0] not in exclude_files),
                        key=lambda n: (-score[n], n))
        chosen = ranked[: config.P2P_PER_SYMBOL]
        per_symbol[sym] = chosen
        for n in chosen:
            picked.setdefault(n, []).append(sym)
    ordered = sorted(picked, key=lambda n: (-len(picked[n]), n))[: config.P2P_CAP]
    rationale = {n: picked[n] for n in sorted(ordered)}
    return sorted(ordered), {"per_symbol": per_symbol, "why": rationale,
                             "touched": {k: {"lines": list(v["lines"]), "reason": v["reason"]}
                                         for k, v in touched.items()}}

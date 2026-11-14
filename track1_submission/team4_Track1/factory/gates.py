"""Validation gates. Each returns {"gate", "ok", "kind", "detail"}; kind says how it was checked
("static" = file inspection, "container" = executed in the task image, "network" = live upstream)."""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

from . import config, container, repo


def _res(gate, ok, kind, **detail):
    return {"gate": gate, "ok": bool(ok), "kind": kind, "detail": detail}


# ---------------------------------------------------------------- structure
def structure(pkg: Path) -> dict:
    spec = importlib.util.spec_from_file_location("cs", config.ROOT / "vendor/harness/check_structure.py")
    cs = importlib.util.module_from_spec(spec); spec.loader.exec_module(cs)  # type: ignore
    errs, warns = cs.check(str(pkg))
    cfg = tomllib.loads((pkg / "task.toml").read_text())
    ok = not errs and cfg["metadata"]["base_commit"] == config.BASE_COMMIT \
        and cfg["environment"]["docker_image"] == ""
    return _res("structure", ok, "static", errors=errs, warnings=warns)


# ---------------------------------------------------------------- base health
def base_health(cov: dict) -> dict:
    failed = [n for n, s in cov["status"].items() if s in ("FAILED", "ERROR")]
    return _res("base_health", not failed and cov["n_passed"] > 0, "container",
                passed=cov["n_passed"], failed=failed, collected=cov["n_tests"],
                note="full existing suite at base_commit inside the task image")


# ---------------------------------------------------------------- grounding
def grounding(draft, gold: str, touched: dict) -> dict:
    files = re.findall(r"^\+\+\+ b/(\S+)", gold, re.M)
    new_files = re.findall(r"^--- /dev/null\n\+\+\+ b/(\S+)", gold, re.M)
    modified = [f for f in files if f not in new_files]
    ok = bool(modified) and all(f.startswith("src/click/") for f in files) and bool(touched)
    return _res("grounding", ok, "static", modified_existing_files=modified, new_files=new_files,
                anchors=len(draft.gold_edits), touched_symbols=sorted(touched),
                note="every gold edit is anchored on text that occurs exactly once at base")


# ---------------------------------------------------------------- novelty
def novelty(draft, evidence_dir: Path) -> dict:
    up = repo.ensure_upstream()
    main = subprocess.run(["git", "rev-parse", "origin/main"], cwd=up, capture_output=True, text=True).stdout.strip()
    hits, blocking = {}, []

    def grep(ref, probe):
        g = subprocess.run(["git", "grep", "-h", "-E", probe, ref, "--", "src"], cwd=up,
                           capture_output=True, text=True).stdout
        return {l.strip() for l in g.splitlines()}

    for probe in draft.novelty_probes:
        at_base, at_main = grep(config.BASE_COMMIT, probe), grep(main, probe)
        lg = subprocess.run(["git", "log", "--oneline", f"{config.BASE_COMMIT}..{main}", "-G", probe,
                             "--", "src"], cwd=up, capture_output=True, text=True).stdout.strip()
        hits[probe] = {"base": sorted(at_base)[:5], "main": sorted(at_main)[:5],
                       "commits_after_base_touching": lg.splitlines()[:5]}
        # A probe line that exists on main but not at base means upstream added it after base.
        if at_base or (at_main - at_base):
            blocking.append(probe)
    gh = []
    for q in draft.novelty_queries:
        url = ("https://api.github.com/search/issues?per_page=5&q="
               + urllib.parse.quote(f'repo:pallets/click is:pr "{q}"'))
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "t1-factory"}),
                                        timeout=15) as r:
                data = json.load(r)
            gh.append({"query": q, "total": data.get("total_count"),
                       "items": [{"n": i["number"], "title": i["title"], "state": i["state"],
                                  "merged": bool(i.get("pull_request", {}).get("merged_at"))}
                                 for i in data.get("items", [])]})
        except Exception as e:  # rate limit / offline: recorded, not silently passed
            gh.append({"query": q, "error": str(e)[:200]})
    (evidence_dir / "novelty.json").write_text(json.dumps({"main": main, "git": hits, "github_prs": gh}, indent=1))
    merged_hits = [i for g in gh for i in g.get("items", []) if i.get("merged")]
    return _res("novelty", not blocking, "network", upstream_main=main, blocking=blocking,
                github_merged_pr_hits_for_manual_review=merged_hits,
                github_checked=all("error" not in g for g in gh),
                scope="git grep of src/ at base and origin/main, git log -G base..main, GitHub PR search")


# ---------------------------------------------------------------- fairness lint
def fairness(draft, f2p: list[str]) -> dict:
    ins = draft.instruction
    norm_ins = re.sub(r"\s+", " ", ins)
    req_ids = set(re.findall(r"\*\*R(\d+)\b", ins))
    problems, used = [], set()
    tree = ast.parse("\n".join(draft.test_files.values()))
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]:
        doc = ast.get_docstring(fn) or ""
        ids = set(re.findall(r"R(\d+)", doc))
        if not ids:
            problems.append(f"{fn.name}: no requirement reference")
        for i in ids - req_ids:
            problems.append(f"{fn.name}: references missing R{i}")
        used |= ids
    for i in sorted(req_ids - used, key=int):
        problems.append(f"R{i} is not exercised by any test")
    # Every message-like literal asserted on must be derivable: built only from spec text, digits,
    # quoted input values, and values the test itself supplies (help strings, command names).
    in_assert = {id(c) for a in ast.walk(tree) if isinstance(a, ast.Assert) for c in ast.walk(a)}
    inputs = [c.value for c in ast.walk(tree) if isinstance(c, ast.Constant) and isinstance(c.value, str)
              and id(c) not in in_assert]
    inputs += [n.name.replace("_", "-") for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    corpus = norm_ins + " \x00 " + " \x00 ".join(re.sub(r"\s+", " ", x) for x in inputs)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            for c in ast.walk(node.test):
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    for line in c.value.splitlines():
                        s = line.strip()
                        if len(s) >= 12 and " " in s and not _derivable(re.sub(r"\s+", " ", s), corpus):
                            problems.append(f"asserted text not in spec: {s[:70]!r}")
                elif isinstance(c, ast.JoinedStr):
                    for part in c.values:
                        if isinstance(part, ast.Constant):
                            for frag in re.split(r"\s{2,}|\n", part.value):
                                f = frag.strip()
                                if len(f) >= 12 and not _derivable(re.sub(r"\s+", " ", f), corpus):
                                    problems.append(f"asserted f-string fragment not in spec: {f[:70]!r}")
    # Public names the tests touch on click / keyword arguments they pass must be named in the spec.
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "click":
            if node.attr not in ins and node.attr not in _BASE_CLICK_API:
                problems.append(f"click.{node.attr} not named in spec")
        if isinstance(node, ast.keyword) and node.arg and node.arg not in ins and node.arg not in _COMMON_KW:
            problems.append(f"keyword {node.arg}= not named in spec")
    return _res("fairness_lint", not problems, "static", problems=problems,
                requirements=sorted(req_ids, key=int), n_tests=len(f2p))


def _derivable(lit: str, spec: str) -> bool:
    """True if ``lit`` splits into pieces that are each: a spec/test-input substring of >= 8 chars,
    a whole test-supplied value, a digit run, a quoted input value, or punctuation/whitespace."""
    q = re.compile(r"'[^'\s]{1,24}'")
    lit, spec = q.sub("'Q'", lit), q.sub("'Q'", spec)
    n = len(lit)
    ok = [False] * (n + 1)
    ok[0] = True
    for i in range(n):
        if not ok[i]:
            continue
        m = re.match(r"\d+|'Q'|[\s.,:;'\"()/]+", lit[i:])
        if m:
            ok[i + m.end()] = True
        for j in range(i + 1, n + 1):
            piece = lit[i:j]
            if (len(piece) >= 8 and piece in spec) or _is_input_piece(piece, spec):
                ok[j] = True
    return ok[n]


def _is_input_piece(piece: str, corpus: str) -> bool:
    # Short pieces are only accepted when they are a whole test-supplied value.
    p = piece.strip()
    return bool(p) and (f"\x00 {p} \x00" in corpus or corpus.endswith(f"\x00 {p}"))


_BASE_CLICK_API = {"command", "option", "argument", "echo", "group", "testing", "types", "Group", "Command",
                   "Option", "Context", "BadParameter", "UsageError", "Abort", "pass_context", "Choice",
                   "IntRange", "ParamType", "prompt", "confirm"}
_COMMON_KW = {"type", "default", "input", "catch_exceptions", "is_flag", "hidden", "help", "envvar", "prompt",
              "cls", "name", "chain", "invoke_without_command", "required", "env", "standalone_mode",
              "short_help", "multiple", "min", "max", "kw", "context_settings", "token_normalize_func",
              "minutes", "hours", "seconds", "microseconds", "count", "prog_name", "terminal_width"}


# ---------------------------------------------------------------- isolation
def isolation(pkg: Path, draft, gold: str) -> dict:
    ins = (pkg / "instruction.md").read_text()
    problems = []
    tnames = re.findall(r"def (test_\w+)", "\n".join(draft.test_files.values()))
    for n in tnames:
        if n in ins:
            problems.append(f"instruction names test {n}")
    for f in draft.test_files:
        if f in ins or Path(f).name in ins:
            problems.append(f"instruction names test file {f}")
    for w in ("patch.diff", "fail_to_pass", "pass_to_pass", "solve.sh", "grade.py"):
        if w in ins:
            problems.append(f"instruction mentions {w}")
    added = [l[1:].strip() for l in gold.splitlines() if l.startswith("+") and not l.startswith("+++")]
    added = [l for l in added if len(l) > 25 and not l.startswith(("#", '"""', ":param"))]
    leaked = [l for l in added if l in ins]
    if len(leaked) > 2:
        problems.append(f"instruction quotes {len(leaked)} gold lines")
    df = (pkg / "environment" / "Dockerfile").read_text()
    if re.search(r"^\s*(COPY|ADD)\b", df, re.M):
        problems.append("Dockerfile copies files from the package context")
    probe = container.run(
        "test ! -e /solution && test ! -e /tests && "
        + " && ".join(f"test ! -e /app/{f}" for f in draft.test_files)
        + " && test $(git -C /app rev-list --count HEAD) = 1 && git -C /app status --porcelain | wc -l")
    if probe.returncode != 0 or probe.stdout.strip() != "0":
        problems.append(f"image probe failed: exit={probe.returncode} out={probe.stdout.strip()[:200]}")
    return _res("isolation", not problems, "static+container", problems=problems,
                checks=["no test names/paths or harness files in spec", "spec quotes <=2 gold lines",
                        "Dockerfile copies nothing from the package", "image has no /solution, /tests, "
                        "feature test files; /app is one commit (no upstream history); clean tree"])


# ---------------------------------------------------------------- execution gates
def gold_gate(r: dict) -> dict:
    ok = r.get("reward") == 1.0 and r["f2p_passed"] == r["f2p_total"] and r["p2p_passed"] == r["p2p_total"]
    return _res("gold", ok, "container", **_summ(r))


def nop_gate(r: dict, f2p: list[str]) -> dict:
    st = r.get("statuses", {})
    # Absence must come from the missing feature, not from a broken harness: the P2P set is fully
    # green and every feature test was collected and reported (FAILED, not missing/ERROR at import).
    collected = all(n in st for n in f2p)
    ok = (r.get("reward") == 0.0 and r["f2p_passed"] == 0 and r["p2p_passed"] == r["p2p_total"])
    return _res("nop", ok, "container", f2p_all_reported=collected, **_summ(r),
                f2p_status_counts=_counts([st.get(n, "MISSING") for n in f2p]))


def mutation_gate(results: dict[str, dict]) -> dict:
    killed = {m: (r.get("reward") is not None and r["f2p_passed"] < r["f2p_total"]) for m, r in results.items()}
    return _res("mutation", all(killed.values()) and bool(killed), "container",
                killed=killed, score=f"{sum(killed.values())}/{len(killed)}",
                per_mutant={m: _summ(r) for m, r in results.items()})


def full_suite_gate(p: subprocess.CompletedProcess) -> dict:
    tail = (p.stdout or "").strip().splitlines()[-3:]
    m = re.search(r"(\d+) failed", "\n".join(tail))
    ok = p.returncode == 0 and not m
    return _res("full_suite_under_gold", ok, "container", tail=tail,
                note="entire existing suite + feature tests with gold applied (extra, not graded)")


def _summ(r):
    return {k: r.get(k) for k in ("reward", "f2p_passed", "f2p_total", "p2p_passed", "p2p_total", "secs")}


def _counts(xs):
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out

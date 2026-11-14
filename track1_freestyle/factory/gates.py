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
    tree = ast.parse("\n".join([*draft.test_files.values(), *draft.compat_test_files.values()]))
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
    all_tests = {**draft.test_files, **draft.compat_test_files}
    tnames = re.findall(r"def (test_\w+)", "\n".join(all_tests.values()))
    for n in tnames:
        if n in ins:
            problems.append(f"instruction names test {n}")
    for f in all_tests:
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
        + " && ".join(f"test ! -e /app/{f}" for f in all_tests)
        + " && test $(git -C /app rev-list --count HEAD) = 1 && git -C /app status --porcelain | wc -l")
    if probe.returncode != 0 or probe.stdout.strip() != "0":
        problems.append(f"image probe failed: exit={probe.returncode} out={probe.stdout.strip()[:200]}")
    return _res("isolation", not problems, "static+container", problems=problems,
                checks=["no test names/paths or harness files in spec", "spec quotes <=2 gold lines",
                        "Dockerfile copies nothing from the package", "image has no /solution, /tests, "
                        "feature test files; /app is one commit (no upstream history); clean tree"])


# ---------------------------------------------------------------- execution gates
# pytest's final line, e.g. "==== 16 failed, 1315 passed, 23 skipped in 3.93s ====" or
# "==== no tests ran in 0.01s ====". -q runs print it without the "=" padding.
_PYTEST_FINAL = re.compile(r"^=*\s*((?:\d+ \w+(?:, )?)+|no tests ran) in [\d.]+s(?: \([^)]*\))?\s*=*$")
_RUN_MARKERS = {"internal_error": re.compile(r"^INTERNALERROR>", re.M),
                "interrupted": re.compile(r"^!+ .*Interrupted", re.M),
                "collection_error": re.compile(r"^_+ ERROR collecting ", re.M)}
PYTEST_EXIT = {0: "ok", 1: "tests failed", 2: "interrupted", 3: "internal error", 4: "usage error",
               5: "no tests collected"}


def pytest_summary(log: str | None) -> dict | None:
    """Counts from the last pytest summary line plus crash markers; None if there is no summary."""
    if not log:
        return None
    final = None
    for line in log.splitlines():
        m = _PYTEST_FINAL.match(line.strip())
        if m:
            final = m.group(1)
    if final is None:
        return None
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0, "xpassed": 0}
    for n, word in re.findall(r"(\d+) (\w+)", final):
        word = {"error": "errors", "warning": "warnings"}.get(word, word)
        counts[word] = counts.get(word, 0) + int(n)
    counts["no_tests_ran"] = final == "no tests ran"
    counts["markers"] = sorted(k for k, rx in _RUN_MARKERS.items() if rx.search(log))
    return counts


_FAIL_HEADER = re.compile(r"^_{3,} (.+?) _{3,}$")
_EXC_LINE = re.compile(r"^E\s+([A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt))\b")
# A feature test "failing" with one of these is reporting broken code, not rejected behaviour.
IMPORT_CLASS = {"SyntaxError", "IndentationError", "TabError", "ImportError", "ModuleNotFoundError"}


def failure_exceptions(log: str | None) -> dict[str, set[str]]:
    """Exception type names raised in each block of pytest's FAILURES section, keyed by the block
    header (the nodeid after the file, with '::' shown as '.')."""
    out: dict[str, set[str]] = {}
    if not log:
        return out
    inside, cur = False, None
    for line in log.splitlines():
        if re.match(r"^=+ FAILURES =+$", line):
            inside = True
            continue
        if inside and re.match(r"^=+ .* =+$", line):
            break
        if not inside:
            continue
        m = _FAIL_HEADER.match(line)
        if m:
            cur = out.setdefault(m.group(1), set())
        elif cur is not None:
            e = _EXC_LINE.match(line)
            if e:
                cur.add(e.group(1).rsplit(".", 1)[-1])
            elif re.match(r"^E\s+assert\b", line):
                cur.add("AssertionError")
    return out


def _failure_key(nodeid: str) -> str:
    return nodeid.split("::", 1)[-1].replace("::", ".")


def classify_run(r: dict, f2p: list[str], p2p: list[str]) -> dict:
    """Per-test statuses for the expected F2P/P2P ids, recomputed from raw parser records, plus every
    reason the run cannot be trusted as a test verdict (``problems``)."""
    problems = []
    for label, ids in (("F2P", f2p), ("P2P", p2p)):
        dup = sorted({n for n in ids if ids.count(n) > 1})
        if dup:
            problems.append(f"duplicate ids in expected {label} list: {dup[:5]}")
    if not f2p:
        problems.append("expected F2P list is empty")
    overlap = sorted(set(f2p) & set(p2p))
    if overlap:
        problems.append(f"ids in both F2P and P2P: {overlap[:5]}")
    if r.get("stage_fail"):
        problems.append(f"stage failed before tests ran: {r['stage_fail']}")
    if r.get("reward") is None:
        problems.append(f"no grading result ({r.get('error', 'reward is null')})")
    if "test_sh_exit" in r and r["test_sh_exit"] != 0 and not r.get("stage_fail"):
        problems.append(f"verifier entry point exit status {r['test_sh_exit']}")

    records = r.get("records")
    if records is None:  # legacy result without raw records
        records = list(r.get("statuses", {}).items())
    if not records and r.get("reward") is not None:
        problems.append("parser produced no test records")
    by_name: dict[str, list[str]] = {}
    for n, s in records:
        by_name.setdefault(n, []).append(s)
    exact_dups = sorted(n for n, ss in by_name.items() if len(ss) != len(set(ss)))
    if exact_dups:
        problems.append(f"repeated identical test records: {exact_dups[:5]}")
    file_errors = sorted(n for n, ss in by_name.items() if "::" not in n and "ERROR" in ss)
    if file_errors:
        problems.append(f"collection/import errors: {file_errors[:5]}")

    def status(n):
        ss = sorted(set(by_name.get(n, [])))
        if not ss:
            return "MISSING"
        return ss[0] if len(ss) == 1 else "INCONSISTENT(" + "+".join(ss) + ")"

    f2p_st = {n: status(n) for n in dict.fromkeys(f2p)}
    p2p_st = {n: status(n) for n in dict.fromkeys(p2p)}

    if r.get("reward") is not None:
        summ = pytest_summary(r.get("pytest_log"))
        if "pytest_log" in r and summ is None:
            problems.append("no pytest summary line (crashed, killed, or never ran)")
        if summ:
            if summ["no_tests_ran"]:
                problems.append("pytest ran no tests")
            if summ["errors"]:
                problems.append(f"pytest reported {summ['errors']} error(s) (collection/setup/teardown)")
            if summ["markers"]:
                problems.append(f"pytest run markers: {summ['markers']}")
            n_pass = sum(1 for _, s in records if s == "PASSED")
            n_fail = sum(1 for _, s in records if s == "FAILED")
            if (n_pass, n_fail) != (summ["passed"] + summ["xpassed"], summ["failed"]):
                problems.append(f"parser records ({n_pass} passed, {n_fail} failed) disagree with pytest "
                                f"summary ({summ['passed'] + summ['xpassed']} passed, {summ['failed']} failed)")
        # Recompute the grade.py contract from the records and the expected lists.
        fp = sum(s == "PASSED" for s in f2p_st.values())
        pp = sum(s == "PASSED" for s in p2p_st.values())
        ft, pt = len(f2p_st), len(p2p_st)
        reward = 0.0 if pt and pp < pt else 1.0 if ft and fp >= ft else (round(fp / ft, 4) if ft else 0.0)
        want = {"reward": reward, "f2p_passed": fp, "f2p_total": ft, "p2p_passed": pp, "p2p_total": pt}
        got = {k: r.get(k) for k in want}
        if got != want:
            problems.append(f"grader totals {got} disagree with recomputation {want}")
    return {"problems": problems, "f2p": f2p_st, "p2p": p2p_st,
            "f2p_status_counts": _counts(f2p_st.values()), "p2p_status_counts": _counts(p2p_st.values())}


def gold_gate(r: dict, f2p: list[str], p2p: list[str]) -> dict:
    c = classify_run(r, f2p, p2p)
    ok = (not c["problems"] and r.get("reward") == 1.0
          and all(s == "PASSED" for s in c["f2p"].values()) and all(s == "PASSED" for s in c["p2p"].values()))
    return _res("gold", ok, "container", **_summ(r), problems=c["problems"],
                f2p_status_counts=c["f2p_status_counts"], p2p_status_counts=c["p2p_status_counts"])


def nop_gate(r: dict, f2p: list[str], p2p: list[str]) -> dict:
    # Absence must come from the missing feature, not from a broken harness: every feature test was
    # collected and FAILED in its own call (not missing, ERROR, skipped or reported twice), the
    # P2P set is fully green, and the run itself is healthy.
    c = classify_run(r, f2p, p2p)
    f2p_all_reported = all(s != "MISSING" for s in c["f2p"].values())
    ok = (not c["problems"] and r.get("reward") == 0.0
          and all(s == "FAILED" for s in c["f2p"].values()) and all(s == "PASSED" for s in c["p2p"].values()))
    return _res("nop", ok, "container", f2p_all_reported=f2p_all_reported, **_summ(r),
                problems=c["problems"], f2p_status_counts=c["f2p_status_counts"],
                p2p_status_counts=c["p2p_status_counts"],
                not_failed={n: s for n, s in c["f2p"].items() if s != "FAILED"},
                p2p_not_passed={n: s for n, s in c["p2p"].items() if s != "PASSED"})


def mutant_verdict(r: dict, f2p: list[str], p2p: list[str], authored: list[str] | tuple = ()) -> dict:
    """killed: a healthy run in which a collected F2P or P2P test FAILED behaviourally (the grader
    cannot give such a run 1.0). invalid: the run cannot be read as a behavioural verdict (patch did
    not apply, import/syntax/collection error, crash). ``authored`` names the P2P ids that are newly
    authored compatibility tests, so ``killed_by`` can tell them apart from upstream regression tests."""
    c = classify_run(r, f2p, p2p)
    bad = {n: s for n, s in {**c["f2p"], **c["p2p"]}.items() if s not in ("PASSED", "FAILED")}
    exc = failure_exceptions(r.get("pytest_log"))
    failed = sorted(n for n, s in c["f2p"].items() if s == "FAILED")
    p2p_failed = sorted(n for n, s in c["p2p"].items() if s == "FAILED")
    broken = {n: sorted(exc.get(_failure_key(n), set()) & IMPORT_CLASS) for n in failed + p2p_failed}
    broken = {n: e for n, e in broken.items() if e}
    killed_by = {"f2p": [n for n in failed if n not in broken],
                 "p2p_authored": [n for n in p2p_failed if n not in broken and n in authored],
                 "p2p_upstream": [n for n in p2p_failed if n not in broken and n not in authored]}
    if c["problems"] or bad:
        v = "invalid"
    elif any(killed_by.values()):
        v = "killed"
    elif broken:
        v = "invalid"
    else:
        v = "survived"
    return {"verdict": v, "problems": c["problems"], "non_verdict_tests": dict(list(bad.items())[:10]),
            "killed_by": {k: x for k, x in killed_by.items() if x},
            "f2p_failed": failed, "failed_by_import_or_syntax_error": broken,
            "p2p_failed": p2p_failed, **_summ(r)}


def mutation_gate(results: dict[str, dict], f2p: list[str], p2p: list[str],
                  authored: list[str] | tuple = ()) -> dict:
    per = {m: mutant_verdict(r, f2p, p2p, authored) for m, r in results.items()}
    killed = {m: v["verdict"] == "killed" for m, v in per.items()}
    return _res("mutation", all(killed.values()) and bool(killed), "container",
                killed=killed, score=f"{sum(killed.values())}/{len(killed)}",
                verdicts={m: v["verdict"] for m, v in per.items()}, per_mutant=per)


def test_categories(draft, f2p: list[str], upstream: list[str], authored: list[str], cov: dict,
                    test_patch: str) -> dict:
    """The three test categories stay what they claim to be: F2P ids come only from the feature
    test files; authored compatibility ids come only from the compatibility files and are graded as
    P2P; upstream P2P ids are pre-existing tests (in no file the test patch creates or edits, and
    PASSED in the base-commit suite run). Whether each test really fails or passes at base is
    checked by the nop gate."""
    problems = []
    feature, compat = set(draft.test_files), set(draft.compat_test_files)
    patched = set(re.findall(r"^\+\+\+ b/(\S+)", test_patch, re.M))
    fname = lambda n: n.split("::", 1)[0]  # noqa: E731
    if feature & compat:
        problems.append(f"files are both feature and compatibility tests: {sorted(feature & compat)}")
    for label, ids, allowed in (("F2P", f2p, feature), ("authored P2P", authored, compat)):
        stray = [n for n in ids if fname(n) not in allowed]
        if stray:
            problems.append(f"{label} ids outside their files: {stray[:5]}")
    if compat and not authored:
        problems.append("compatibility files declare no test functions")
    for a, b, label in ((f2p, upstream, "F2P/upstream"), (f2p, authored, "F2P/authored"),
                        (upstream, authored, "upstream/authored")):
        if set(a) & set(b):
            problems.append(f"{label} overlap: {sorted(set(a) & set(b))[:5]}")
    not_preexisting = [n for n in upstream if fname(n) in patched]
    if not_preexisting:
        problems.append(f"upstream P2P ids in files the test patch adds or edits: {not_preexisting[:5]}")
    not_green = [n for n in upstream if cov["status"].get(n) != "PASSED"]
    if not_green:
        problems.append(f"upstream P2P ids not PASSED in the base suite run: {not_green[:5]}")
    return _res("test_categories", not problems, "static", problems=problems,
                counts={"f2p": len(f2p), "p2p_upstream": len(upstream), "p2p_authored": len(authored)},
                note="authored compatibility tests are graded as pass-to-pass but are not upstream tests")


def full_suite_gate(p: subprocess.CompletedProcess, log: str | None) -> dict:
    """``p`` ran ``container.full_suite_script()``; ``log`` is the complete pytest output it saved."""
    out = p.stdout or ""
    problems = []
    stage = re.findall(r"^T1_STAGE_FAIL=(\w+)\s*$", out, re.M)
    if stage:
        problems.append(f"stage failed: {stage[-1]}")
    rc = re.findall(r"^T1_PYTEST_EXIT=(\d+)\s*$", out, re.M)
    pytest_exit = int(rc[-1]) if rc else None
    if pytest_exit is None and not stage:
        problems.append("pytest exit status not recorded (script did not reach pytest)")
    elif pytest_exit not in (None, 0):
        problems.append(f"pytest exit {pytest_exit} ({PYTEST_EXIT.get(pytest_exit, 'unknown')})")
    if p.returncode != 0:
        problems.append(f"container exit {p.returncode}")
    summ = pytest_summary(log)
    if pytest_exit is not None:
        if summ is None:
            problems.append("no pytest summary line in saved log")
        else:
            if summ["no_tests_ran"] or not summ["passed"]:
                problems.append("no passing tests")
            if summ["failed"] or summ["errors"]:
                problems.append(f"{summ['failed']} failed, {summ['errors']} error(s)")
            if summ["markers"]:
                problems.append(f"pytest run markers: {summ['markers']}")
    tail = (log or "").strip().splitlines()[-3:]
    return _res("full_suite_under_gold", not problems, "container", pytest_exit=pytest_exit,
                container_exit=p.returncode, summary=summ, problems=problems, tail=tail,
                note="entire existing suite + feature tests with gold applied (extra, not graded)")


def _summ(r):
    return {k: r.get(k) for k in ("reward", "f2p_passed", "f2p_total", "p2p_passed", "p2p_total", "secs")}


def _counts(xs):
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out

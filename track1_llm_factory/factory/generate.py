"""Task factory (plan v6.2): `uv run python -m factory.generate --card types --seed 1 [--replay]`.

Stages: pick blueprint -> design frozen contract (LLM) -> novelty (code) -> spec + gold (LLM) ->
tests written BLIND from the spec (LLM) -> fairness: rule coverage + verbatim literals (code) and a
blind judge (LLM) -> soundness + mutation + selfcheck (factory.check, docker/Harbor) -> targeted
repairs (max 2) -> package + telemetry. `--replay` rebuilds from logged responses with no API calls.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

from . import llm, prompts
from .cards import CARDS

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = ROOT / "upstream-click"
BASE_COMMIT = "cf19179e8e2fd54c601378cec9e0d21bb12b6fb1"
OUT = ROOT / "generated_tasks"
RUNS = ROOT / "runs"
MAX_REPAIRS = int(__import__('os').environ.get('FACTORY_MAX_REPAIRS', '2'))
MIN_RULES, MAX_RULES = 10, 12
MIN_GOLD_FILES = int(__import__('os').environ.get('FACTORY_MIN_GOLD_FILES', '3'))
MIN_GOLD_ADDED = int(__import__('os').environ.get('FACTORY_MIN_GOLD_ADDED', '150'))
DENYLIST = ["click-option-group", "cloup", "click-extra", "click-aliases", "click-didyoumean",
            "click-default-group"]


def sh(cmd, cwd=None, check=True) -> str:
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))}\n{r.stdout}\n{r.stderr}")
    return r.stdout


class Calls:
    """Live calls are logged. --replay serves logged responses in order (no API use); if the log
    runs out, the run continues live and appends (resume)."""

    def __init__(self, tel: llm.Telemetry, replay: bool):
        self.tel, self.i = tel, 0
        log = tel.run_dir / "calls.jsonl"
        self.recorded = [json.loads(l) for l in log.read_text().splitlines()] if replay and log.exists() else []

    def __call__(self, stage: str, system: str, user: str) -> str:
        if self.i < len(self.recorded):
            rec = self.recorded[self.i]
            self.i += 1
            assert rec["stage"] == stage, f"replay mismatch: {rec['stage']} != {stage}"
            return rec["response"]
        model = __import__("os").environ.get("JUDGE_MODEL") if stage == "fairness_judge" else None
        return llm.call(self.tel, stage, system, user, model=model)


# ---------- repo helpers ----------
def fresh_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    sh(["git", "-C", UPSTREAM, "worktree", "prune"])
    sh(["git", "-C", UPSTREAM, "worktree", "add", "--detach", "--force", path, BASE_COMMIT])


def ground(card: dict, tree: Path) -> str:
    return prompts.SYSTEM_HEADER + "".join(
        f"\n===== {rel} =====\n{(tree / rel).read_text()}" for rel in card["ground"])


EDIT_RE = re.compile(r'<edit file="([^"]+)">\s*<search>\n?(.*?)</search>\s*<replace>\n?(.*?)</replace>\s*</edit>', re.S)


def parse_sections(text: str) -> dict:
    out = {}
    m = re.search(r"<instruction_md>\s*(.*?)</instruction_md>", text, re.S)
    if m:
        out["instruction"] = m.group(1).strip() + "\n"
    edits = EDIT_RE.findall(re.sub(r"<test_file.*?</test_file>", "", text, flags=re.S))
    if edits:
        out["edits"] = edits
    m = re.search(r'<test_file path="([^"]+)">\s*(.*?)</test_file>', text, re.S)
    if m:
        code = m.group(2).strip()
        code = re.sub(r"^```(?:python)?\n|\n```$", "", code)
        out["test_path"], out["test_code"] = m.group(1), code + "\n"
    return out


def apply_edits(tree: Path, edits) -> None:
    for rel, search, replace in edits:
        if not rel.startswith("src/click/"):
            raise ValueError(f"edit outside src/click: {rel}")
        f = tree / rel
        if not f.exists():
            if search.strip():
                raise ValueError(f"{rel} does not exist; to CREATE a new file use an empty <search></search> block")
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(replace)
            continue
        src = f.read_text()
        n = src.count(search)
        if n != 1:
            import difflib
            first = next((l for l in search.splitlines() if l.strip()), "")
            near = difflib.get_close_matches(first, src.splitlines(), n=3, cutoff=0.4)
            ctx = ""
            if near:
                lines = src.splitlines()
                i = lines.index(near[0])
                ctx = "\nACTUAL text near the closest match in the pinned file:\n" + "\n".join(lines[max(0, i - 3): i + 12])
            raise ValueError(f"gold edit search block in {rel} matched {n} times (must be exactly 1):\n{search[:400]}{ctx}")
        f.write_text(src.replace(search, replace))


# ---------- mechanical fairness ----------
def rule_coverage(test_code: str, instruction: str, n_rules: int) -> list[str]:
    problems = []
    names = re.findall(r"^def (test_\w+)", test_code, re.M)
    in_spec = {int(m) for m in re.findall(r"\bR(\d+)\b", instruction)}
    covered = set()
    for name in names:
        m = re.match(r"test_r(\d+)_", name)
        if not m:
            problems.append(f"test {name} does not start with test_r<N>_")
            continue
        covered.add(int(m.group(1)))
        if int(m.group(1)) not in in_spec:
            problems.append(f"test {name} cites R{m.group(1)}, which is not in the statement")
    missing = sorted(set(range(1, n_rules + 1)) - covered)
    if missing:
        problems.append("rules with no test: " + ", ".join(f"R{i}" for i in missing))
    return problems


def expected_literals(test_code: str) -> set[str]:
    """String literals used as EXPECTED output/messages: `"x" in <...>`, `== "x"` against output,
    and pytest.raises(..., match="x"). Input fixtures are not collected."""
    lits: set[str] = set()
    try:
        tree = ast.parse(test_code)
    except SyntaxError as e:
        raise ValueError(f"test file does not parse: {e}") from None
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = node.left, node.comparators[0]
            if isinstance(node.ops[0], ast.In) and isinstance(left, ast.Constant) and isinstance(left.value, str):
                lits.add(left.value)
            if isinstance(node.ops[0], ast.Eq):
                for a, b in ((left, right), (right, left)):
                    if isinstance(b, ast.Constant) and isinstance(b.value, str) and "output" in ast.unparse(a):
                        lits.add(b.value)
        if isinstance(node, ast.keyword) and node.arg == "match" and isinstance(node.value, ast.Constant):
            lits.add(str(node.value.value))
    # messages only: computed values (numbers, reprs without words) are not required verbatim
    return {l.strip() for l in lits if len(l.strip()) >= 6 and re.search(r"[A-Za-z]{3}", l)}


def statement_leakage(instruction: str) -> list[str]:
    """Mechanical gate for v6.5: <=3 examples (code blocks), no expected-output table, no private
    click names. (Mechanism prose is judged by the LLM fairness judge.)"""
    out = []
    blocks = re.findall(r"```", instruction)
    if len(blocks) // 2 > 3:
        out.append(f"statement has {len(blocks)//2} code examples (max 3)")
    ex = re.split(r"(?im)^#+\s*examples?\b", instruction)
    if len(ex) > 1 and re.search(r"^\|.*\|\s*$", ex[-1], re.M):
        out.append("statement has an examples table (only syntax examples allowed)")
    priv = sorted(set(re.findall(r"`[^`]*\b(_[a-z][a-z0-9_]+)\b[^`]*`", instruction)))
    if priv:
        out.append(f"statement leaks private names: {priv[:5]}")
    return out


def _existing_click_text(text: str) -> bool:
    """Output click ALREADY produces is existing public behavior, not a hidden requirement: allow a
    literal if its whole first line occurs in the pinned click source, or it is click's standard
    usage line ('Usage: <prog> ...'). Anything else must be stated in the instruction."""
    line = text.split("\n")[0].strip()
    if re.match(r"^Usage: \S+", line):
        return True
    if len(line) < 6:
        return False
    return subprocess.run(["git", "-C", str(UPSTREAM), "grep", "-q", "-F", line, BASE_COMMIT, "--", "src/click"]).returncode == 0


def literal_check(test_code: str, instruction: str) -> list[str]:
    flat = " ".join(instruction.split())
    out = []
    for lit in sorted(expected_literals(test_code)):
        probe = re.sub(r"\\(.)", r"\1", lit)  # unescape regex in match=
        if " ".join(probe.split()) not in flat and " ".join(lit.split()) not in flat \
                and not _existing_click_text(probe):
            out.append(f"expected text not stated verbatim in the statement: {lit!r}")
    return out


_STOP = {"click", "self", "None", "True", "False", "kwargs", "param", "value", "return", "tuple",
         "list", "dict", "bool", "float", "Sequence", "Iterable", "Callable", "Optional", "typing",
         "default", "decls", "param_decls", "string", "property", "readonly", "method", "attribute",
         "exported", "implemented", "accept", "accepts", "through", "extra", "context_settings"}


def novelty_hits(design: dict) -> list[str]:
    """A feature is novel if the NEW identifiers it introduces (kwargs, attributes, methods,
    classes) are not already defined upstream. Existing classes it extends (Context, Command,
    to_info_dict, ...) are expected to exist and are ignored. Rejected only if fewer than 2 of its
    identifiers are new, i.e. the API already exists."""
    idents = set()
    for entry in design.get("public_api", []):
        for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]{4,}", entry):
            if tok not in _STOP and not tok.startswith("__"):
                idents.add(tok)
    new, existing = [], []
    for tok in sorted(idents):
        out = sh(["git", "-C", UPSTREAM, "grep", "-n", "-w", "-F", tok, "origin/main", "--", "src/click"], check=False)
        (existing if out.strip() else new).append(tok)
    (RUNS / "_novelty_last.json").write_text(json.dumps({"new": new, "existing": existing}, indent=1))
    hits = []
    if len(new) < 2:
        hits.append(f"not novel: only {new} are new; already upstream: {existing[:12]}")
    text = json.dumps(design).lower()
    return hits + [f"denylisted library mentioned: {d}" for d in DENYLIST if d in text]


# ---------- pipeline ----------
def build(card_id: str, seed: int, replay: bool = False, harder_than: str | None = None) -> dict:
    from . import check

    card = CARDS[card_id]
    iid = f"pallets__click-{card_id}-{seed:04d}"
    run_dir = RUNS / iid
    if harder_than and not replay and (run_dir.exists() or (OUT / iid).exists()):
        raise SystemExit(f"{iid} already exists; a redesign never overwrites a run (fail closed)")
    if not replay and run_dir.exists():
        shutil.rmtree(run_dir)
    tel = llm.Telemetry(run_dir)
    ask = Calls(tel, replay)
    tree = run_dir / "repo"
    fresh_tree(tree)
    system = ground(card, tree)

    design_prompt = prompts.DESIGN.format(
        card=card_id, shape=card["shape"], blueprint=card.get("blueprint", "model's choice"), seed=seed)
    lineage = None
    if harder_than:
        # Plan v6.2 §3 redesign path: the benchmark verdict (a COUNT only — never Haiku's trajectory or
        # code) retires the original; this replacement is submitted if valid regardless of its own k=3.
        prev = RUNS / harder_than
        prev_design = json.loads((prev / "design.json").read_text())
        verdict = json.loads((prev / "benchmark.json").read_text())
        lineage = {"replaces": harder_than, "replaced_resolve_at_3": verdict["resolve_at_3"]}
        design_prompt += prompts.HARDER.format(
            feature=prev_design.get("feature"), resolved=verdict["resolve_at_3"],
            rules="\n".join(f"- {r.get('id')}: {r.get('text')}" for r in prev_design.get("rules", [])),
            prior_files=prior_files(harder_than))
    dfile = __import__("os").environ.get("FACTORY_DESIGN_FILE")
    if dfile:
        # Repaired contract supplied from a reviewed design (disclosed manual/agent intervention).
        design = json.loads(Path(dfile).read_text())
        lineage = dict(lineage or {}, design_from=dfile)
    else:
        design = llm.extract_json(ask("design", system, design_prompt))
    (run_dir / "design.json").write_text(json.dumps(design, indent=1))
    n_rules = len(design.get("rules", []))
    gate = novelty_hits(design)
    if not MIN_RULES <= n_rules <= MAX_RULES:
        gate.append(f"{n_rules} rules (need {MIN_RULES}-{MAX_RULES})")
    if gate:
        return finish(tel, iid, card_id, seed, {"ok": False, "stage": "design/novelty", "report": "; ".join(gate)})

    design_txt = json.dumps(design, indent=1)
    pkg = parse_sections(ask("spec_gold", system, prompts.SPEC_GOLD.format(design=design_txt)))
    test_path = f"{card['test_dir']}/test_{re.sub(r'[^a-z0-9]+', '_', design['feature'].lower()).strip('_')}.py"
    if "instruction" in pkg:
        pkg.update(parse_sections(ask("tests_blind", system, prompts.TESTS.format(
            instruction=pkg["instruction"], test_path=test_path))))

    result: dict = {}
    for attempt in range(1 + MAX_REPAIRS):
        tel.attempts += 1
        snap = run_dir / f"candidate{attempt}"
        snap.mkdir(exist_ok=True)
        (snap / "package.json").write_text(json.dumps(pkg, indent=1))
        result = evaluate(pkg, design, card, tree, iid, run_dir, ask, check, harder=bool(harder_than))
        (snap / "result.json").write_text(json.dumps(_trim(result), indent=1))
        if result.get("ok") or attempt == MAX_REPAIRS:
            break
        previous = "".join(f'<edit file="{f}">\n<search>\n{s}</search>\n<replace>\n{r}</replace>\n</edit>\n'
                           for f, s, r in pkg.get("edits", []))
        previous += f'<test_file path="{pkg.get("test_path", test_path)}">\n{pkg.get("test_code", "")}</test_file>'
        fix = parse_sections(ask("repair", system, prompts.REPAIR.format(
            stage=result.get("stage"), report=str(result.get("report"))[:6000], design=design_txt,
            instruction=pkg.get("instruction", ""), previous=previous)))
        pkg.update(fix)
    if lineage:
        result = dict(result, lineage=lineage)
    return finish(tel, iid, card_id, seed, result)


def evaluate(pkg, design, card, tree, iid, run_dir, ask, check, harder: bool = False) -> dict:
    try:
        for k in ("instruction", "edits", "test_code"):
            if k not in pkg:
                raise ValueError(f"model output missing {k}")
        fresh_tree(tree)
        apply_edits(tree, pkg["edits"])
        problems = rule_coverage(pkg["test_code"], pkg["instruction"], len(design["rules"]))
        names = re.findall(r"^def (test_\w+)", pkg["test_code"], re.M)
        combos = [n for n in names if re.match(r"test_r\d+_combo_", n)]
        if names and len(combos) * 3 < len(names):
            problems.append(f"only {len(combos)}/{len(names)} test functions are test_r<N>_combo_*; need >= 1/3")
        added = sum(1 for l in sh(["git", "-C", tree, "diff"]).splitlines() if l.startswith("+") and not l.startswith("+++"))
        files = [l[6:] for l in sh(["git", "-C", tree, "diff", "--name-only"]).splitlines() for l in ["+++ b/" + l]]
        if MIN_GOLD_FILES and len(files) < MIN_GOLD_FILES:
            problems.append(f"gold touches {len(files)} files {files} (< {MIN_GOLD_FILES}); cross-module lever not met")
        problems += statement_leakage(pkg["instruction"])
        if harder:
            problems += harder_targets(design, files)
        for n in combos:
            body = pkg["test_code"].split(f"def {n}", 1)[1].split("\ndef ", 1)[0]
            if not re.search(r"#\s*decided by R\d+", body):
                problems.append(f"{n} lacks a '# decided by R<N>' comment")
        if added < MIN_GOLD_ADDED:
            problems.append(f"gold adds only {added} lines (< {MIN_GOLD_ADDED}); the design must be larger")
        problems += literal_check(pkg["test_code"], pkg["instruction"])
        if problems:
            return {"ok": False, "stage": "fairness/mechanical", "report": "\n".join(problems)}
        audit = llm.extract_json(ask("fairness_judge", "You are a strict reviewer.", prompts.FAIRNESS.format(
            instruction=pkg["instruction"], tests=pkg["test_code"])))
        if audit.get("unstated"):
            return {"ok": False, "stage": "fairness/judge",
                    "report": "tests depend on unstated behavior:\n- " + "\n- ".join(audit["unstated"])}
        task_dir = write_package(iid, tree, pkg)
        return check.verify(task_dir, [], card["p2p"])
    except Exception as e:  # noqa: BLE001 — every failure becomes a repair diagnostic
        return {"ok": False, "stage": "build", "report": f"{type(e).__name__}: {str(e)[:3500]}"}


def harder_targets(design: dict, files: list[str]) -> list[str]:
    """Mechanical enforcement of the redesign's absolute targets (prompts.HARDER)."""
    out = []
    src = [f for f in files if f.startswith("src/")]
    if len(src) < 4:
        out.append(f"redesign target: gold must change >= 4 src files, got {len(src)}: {src}")
    rules = design.get("rules", [])
    def refs_other(r):
        own = str(r.get("id"))
        blob = f"{r.get('text', '')} {r.get('precedence', '')}"
        return any(x != own for x in re.findall(r"\bR\d+\b", blob))
    inter = sum(1 for r in rules if refs_other(r))
    if inter < 5:
        out.append(f"redesign target: >= 5 rules must state an interaction with another rule, got {inter}")
    keep = sum(1 for r in rules if re.search(r"byte-identical|unchanged|identical to (the )?current", json.dumps(r), re.I))
    if keep < 2:
        out.append(f"redesign target: >= 2 rules must change existing behavior with byte-identical guarantees, got {keep}")
    return out


def prior_files(prev_iid: str) -> str:
    """Non-agent evidence for the redesign prompt: which src files the retired gold changed."""
    patch = OUT / prev_iid / "solution" / "patch.diff"
    if not patch.exists():
        return "unknown"
    files = sorted(set(re.findall(r"^\+\+\+ b/(\S+)", patch.read_text(), re.M)))
    return f"{len(files)} files: {', '.join(files)}"


def write_package(iid: str, tree: Path, pkg: dict) -> Path:
    task = OUT / iid
    if task.exists():
        shutil.rmtree(task)
    (task / "solution").mkdir(parents=True)
    (task / "tests").mkdir()
    (task / "instruction.md").write_text(pkg["instruction"])
    gold = sh(["git", "-C", tree, "diff"])
    if not gold.strip():
        raise ValueError("gold patch is empty")
    (task / "solution" / "patch.diff").write_text(gold)
    tf = tree / pkg["test_path"]
    tf.parent.mkdir(parents=True, exist_ok=True)
    tf.write_text(pkg["test_code"])
    sh(["git", "-C", tree, "add", "-N", pkg["test_path"]])
    (task / "tests" / "test_patch.diff").write_text(sh(["git", "-C", tree, "diff", "--", pkg["test_path"]]))
    sh(["git", "-C", tree, "reset", "-q"])
    tf.unlink()
    (task / "task.toml").write_text(TASK_TOML.format(iid=iid, base=BASE_COMMIT))
    return task


def _trim(result: dict) -> dict:
    """Keep result files valid JSON: summarize long id lists instead of truncating the text."""
    r = dict(result)
    for k in ("f2p_ids", "p2p_ids"):
        if isinstance(r.get(k), list):
            r[k + "_count"] = len(r[k])
            r[k] = r[k][:20]
    if isinstance(r.get("report"), str):
        r["report"] = r["report"][:8000]
    return r


def finish(tel, iid, card_id, seed, result) -> dict:
    s = tel.summary(iid)
    s.update(ok=bool(result.get("ok")), failed_stage=None if result.get("ok") else result.get("stage"),
             card=card_id, seed=seed, prompts_version=prompts.VERSION, lineage=result.get("lineage"))
    (tel.run_dir / "summary.json").write_text(json.dumps(s, indent=1))
    (tel.run_dir / "final_result.json").write_text(json.dumps(_trim(result), indent=1))
    f = ROOT / "pipeline_run.json"
    data = json.loads(f.read_text()) if f.exists() else {"pipeline": "click-task-factory/0.2", "tasks": []}
    data["tasks"] = [t for t in data["tasks"] if t["instance_id"] != iid] + [s]
    f.write_text(json.dumps(data, indent=1))
    if not result.get("ok") and (OUT / iid).exists():
        shutil.move(str(OUT / iid), str(tel.run_dir / "rejected_package"))
    return s


TASK_TOML = """[metadata]
name = "{iid}"
instance_id = "{iid}"
task = "swe-feature-implementation"
source_repo = "pallets/click"
base_commit = "{base}"
license = "BSD-3-Clause"
language = "en"
programming_language = "python"

[environment]
docker_image = ""
build_timeout_sec = 3600.0
cpus = 2
workdir = "/app"
memory_mb = 4096
network_mode = "public"

[agent]
timeout_sec = 900.0

[verifier]
environment_mode = "shared"
timeout_sec = 900.0

[rollout_baseline.oracle]
reward = 1.0
[rollout_baseline.nop]
reward = 0.0
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", required=True, choices=sorted(CARDS))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--replay", action="store_true", help="rebuild from logged responses, no API calls")
    ap.add_argument("--harder-than", help="run id whose benchmark was >=2/3: generate its harder replacement")
    a = ap.parse_args()
    print(json.dumps(build(a.card, a.seed, a.replay, a.harder_than), indent=1))


if __name__ == "__main__":
    main()

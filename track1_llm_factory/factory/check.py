"""Deterministic renderer and validation gate for generated Click task packages.

The model is allowed to write the spec, gold patch, test patch, and wrong
implementations.  This module owns everything that decides whether those artifacts
are a valid Harbor task: verifier plumbing, exact pytest node-id discovery, base and
gold checks, mutation checks, structure validation, and Harbor selfcheck.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "reference" / "pallets__click-0001-bytesize"
DEFAULT_KIT = Path("/Users/daniella/Downloads/Innodata Hackathon/Track 1 - Coding")
KIT = Path(os.environ.get("INNODATA_TRACK1_KIT", DEFAULT_KIT))
IMAGE = os.environ.get("FACTORY_DOCKER_IMAGE", "click-base:8.5.1")
MIN_F2P = int(os.environ.get("FACTORY_MIN_F2P", "30"))
DOCKER_TIMEOUT = int(os.environ.get("FACTORY_DOCKER_TIMEOUT", "600"))
MAX_REPORT = 3500

_SUMMARY = re.compile(
    r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\s+"
    r"(\S+?\.py(?:::[^\[\s]+)*(?:\[.*?\](?=\s+-\s|$))?)"
    r"(?:\s+-\s.*)?$"
)
_SUMMARY_START = re.compile(r"^=+\s*short test summary info\s*=+$")
_SUMMARY_END = re.compile(
    r"^=+.*\b(passed|failed|error|errors|no tests ran|skipped)\b.*=+$"
)
_COLLECT_ERR = re.compile(r"^ERROR\s+(\S+\.py)\b")
_STATUS = {
    "PASSED": "PASSED",
    "XPASS": "PASSED",
    "FAILED": "FAILED",
    "XFAIL": "SKIPPED",
    "SKIPPED": "SKIPPED",
    "ERROR": "ERROR",
}


@dataclass
class Run:
    returncode: int
    tests: dict[str, str]
    stdout: str
    stderr: str
    patch_error: bool = False

    @property
    def excerpt(self) -> str:
        return _short(self.stdout + "\n" + self.stderr)


class CheckFailure(RuntimeError):
    def __init__(self, stage: str, report: str):
        super().__init__(report)
        self.stage = stage
        self.report = _short(report)


def _short(value: str) -> str:
    value = value.replace("\x00", "").strip()
    if len(value) <= MAX_REPORT:
        return value
    return value[: MAX_REPORT - 80] + "\n... [diagnostics truncated by checker]"


def _safe_rel(raw: str) -> str:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise CheckFailure("render", f"unsafe repository-relative test path: {raw!r}")
    return path.as_posix()


def _new_test_paths(test_patch: Path) -> list[str]:
    paths: list[str] = []
    for line in test_patch.read_text(errors="replace").splitlines():
        if not line.startswith("+++ b/"):
            continue
        rel = _safe_rel(line[6:].strip())
        if rel.startswith("tests/") and rel.endswith(".py") and rel not in paths:
            paths.append(rel)
    if not paths:
        raise CheckFailure("render", "test_patch.diff adds no Python test path under tests/")
    return paths


def _render_run_script(paths: Iterable[str]) -> str:
    entries = "\n".join(f"  {shlex.quote(_safe_rel(p))}" for p in dict.fromkeys(paths))
    return f"""#!/usr/bin/env bash
# Generated deterministic verifier runner. Keep absent paths out so nop still runs P2P.
set -uo pipefail
cd /app
PY=/app/.venv/bin/python
[ -x "$PY" ] || PY="$(command -v python)"
ALL=(
{entries}
)
PRESENT=()
for f in "${{ALL[@]}}"; do [ -e "$f" ] && PRESENT+=("$f"); done
[ "${{#PRESENT[@]}}" -eq 0 ] && {{ echo "no graded test files present"; exit 2; }}
"$PY" -m pytest "${{PRESENT[@]}}" -rA --tb=short -p no:cacheprovider --color=no --continue-on-collection-errors
"""


def _copy_plumbing(task_dir: Path, p2p_files: list[str]) -> list[str]:
    required = [
        task_dir / "instruction.md",
        task_dir / "task.toml",
        task_dir / "solution" / "patch.diff",
        task_dir / "tests" / "test_patch.diff",
    ]
    missing = [str(p.relative_to(task_dir)) for p in required if not p.is_file()]
    if missing:
        raise CheckFailure("render", "missing model artifacts: " + ", ".join(missing))

    tests = task_dir / "tests"
    solution = task_dir / "solution"
    environment = task_dir / "environment"
    tests.mkdir(parents=True, exist_ok=True)
    solution.mkdir(parents=True, exist_ok=True)
    environment.mkdir(parents=True, exist_ok=True)
    for name in ("grade.py", "parser.py", "test.sh"):
        shutil.copy2(TEMPLATE / "tests" / name, tests / name)
    shutil.copy2(TEMPLATE / "solution" / "solve.sh", solution / "solve.sh")
    shutil.copy2(TEMPLATE / "environment" / "Dockerfile", environment / "Dockerfile")

    new_tests = _new_test_paths(tests / "test_patch.diff")
    safe_p2p = [_safe_rel(p) for p in p2p_files]
    (tests / "run_script.sh").write_text(_render_run_script([*safe_p2p, *new_tests]))
    for executable in (tests / "test.sh", tests / "run_script.sh", solution / "solve.sh"):
        executable.chmod(0o755)
    return new_tests


def _parse_pytest(stdout: str, stderr: str) -> dict[str, str]:
    all_lines = (stdout + "\n" + stderr).splitlines()
    summary: list[str] = []
    inside = False
    for raw in all_lines:
        line = raw.strip()
        if _SUMMARY_START.match(line):
            inside = True
            continue
        if inside and _SUMMARY_END.match(line):
            inside = False
            continue
        if inside:
            summary.append(line)
    lines = summary or [line.strip() for line in all_lines]

    found: dict[str, str] = {}
    for line in lines:
        match = _SUMMARY.match(line)
        if match:
            found[match.group(2)] = _STATUS[match.group(1)]
            continue
        collect = _COLLECT_ERR.match(line)
        if collect:
            found[collect.group(1)] = "ERROR"
    return found


def _pytest_command(files: list[str] | None) -> str:
    if files is None:
        return "bash /task/tests/run_script.sh"
    quoted = " ".join(shlex.quote(_safe_rel(p)) for p in files)
    return (
        "/app/.venv/bin/python -m pytest "
        + quoted
        + " -rA --tb=short -p no:cacheprovider --color=no --continue-on-collection-errors"
    )


def _docker_run(
    task_dir: Path,
    *,
    gold: bool,
    mutation: Path | None = None,
    reverse_mutation: bool = False,
    mutation_script: Path | None = None,
    files: list[str] | None = None,
) -> Run:
    mounts = ["-v", f"{task_dir.resolve()}:/task:ro"]
    if mutation is not None:
        mounts += ["-v", f"{mutation.resolve()}:/mutation.diff:ro"]
    if mutation_script is not None:
        mounts += ["-v", f"{mutation_script.resolve()}:/mutation.py:ro"]

    script = ["set -uo pipefail", "cd /app"]
    if gold:
        script += [
            "git apply --check /task/solution/patch.diff || { echo CHECKER_PATCH_ERROR:gold >&2; exit 90; }",
            "git apply /task/solution/patch.diff",
        ]
    if mutation is not None:
        reverse = "-R " if reverse_mutation else ""
        script += [
            f"git apply {reverse}--check /mutation.diff || {{ echo CHECKER_PATCH_ERROR:mutation >&2; exit 91; }}",
            f"git apply {reverse}/mutation.diff",
        ]
    if mutation_script is not None:
        script += [
            "/app/.venv/bin/python /mutation.py || { echo CHECKER_MUTATION_ERROR:semantic >&2; exit 91; }"
        ]
    script += [
        "git apply --check /task/tests/test_patch.diff || { echo CHECKER_PATCH_ERROR:tests >&2; exit 92; }",
        "git apply /task/tests/test_patch.diff",
        _pytest_command(files),
    ]
    command = ["docker", "run", "--rm", *mounts, IMAGE, "bash", "-lc", "\n".join(script)]
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=DOCKER_TIMEOUT)
    except FileNotFoundError as exc:
        raise CheckFailure("docker", "docker executable not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise CheckFailure("docker", f"docker pytest state timed out after {DOCKER_TIMEOUT}s") from exc
    patch_error = "CHECKER_PATCH_ERROR:" in proc.stderr or "CHECKER_MUTATION_ERROR:" in proc.stderr
    return Run(
        proc.returncode,
        _parse_pytest(proc.stdout, proc.stderr),
        proc.stdout,
        proc.stderr,
        patch_error,
    )


def _ids_for_path(statuses: dict[str, str], path: str) -> list[str]:
    path = path.rstrip("/")
    if path.endswith(".py"):
        return [node for node in statuses if node == path or node.startswith(path + "::")]
    return [node for node in statuses if node.startswith(path + "/")]


def _require_state_parsed(name: str, run: Run) -> None:
    if run.patch_error:
        raise CheckFailure(name, run.excerpt)
    if not run.tests:
        raise CheckFailure(name, f"pytest produced no parseable test results\n{run.excerpt}")


def _derive_ids(
    base: Run, gold: Run, new_tests: list[str], p2p_files: list[str]
) -> tuple[list[str], list[str]]:
    _require_state_parsed("base", base)
    _require_state_parsed("gold", gold)

    new_ids = sorted({node for path in new_tests for node in _ids_for_path(gold.tests, path)})
    if not new_ids:
        raise CheckFailure("gold", "gold run collected no tests from generated test file")
    gold_bad = [node for node in new_ids if gold.tests.get(node) != "PASSED"]
    if gold_bad:
        raise CheckFailure("gold", "generated tests not green under gold: " + ", ".join(gold_bad[:20]))

    f2p = sorted(
        node
        for node in new_ids
        if base.tests.get(node) == "FAILED" and gold.tests.get(node) == "PASSED"
    )
    if len(f2p) < MIN_F2P:
        base_counts: dict[str, int] = {}
        for node in new_ids:
            status = base.tests.get(node, "MISSING")
            base_counts[status] = base_counts.get(status, 0) + 1
        raise CheckFailure(
            "base",
            f"only {len(f2p)} FAIL-at-base/PASS-at-gold tests; require {MIN_F2P}; "
            f"base generated-test statuses={base_counts}\n{base.excerpt}",
        )

    p2p: set[str] = set()
    for path in p2p_files:
        base_ids = set(_ids_for_path(base.tests, path))
        gold_ids = set(_ids_for_path(gold.tests, path))
        if not base_ids or not gold_ids:
            raise CheckFailure("p2p", f"curated P2P path produced no tests in both states: {path}")
        bad = sorted(
            node
            for node in base_ids
            if base.tests.get(node) == "PASSED"
            and gold.tests.get(node, "MISSING") in {"FAILED", "ERROR", "MISSING"}
        )
        if bad:
            raise CheckFailure("p2p", f"curated P2P path is not green in base+gold: {path}: {bad[:20]}")
        p2p.update(
            node
            for node in base_ids & gold_ids
            if base.tests.get(node) == "PASSED" and gold.tests.get(node) == "PASSED"
        )
    if not p2p:
        raise CheckFailure("p2p", "no curated P2P node IDs discovered")
    return f2p, sorted(p2p)


def _semantic_mutations(patch: Path) -> list[tuple[str, str, str, str]]:
    """Find bounded source-level mutations in lines introduced by the gold patch.

    A mutation changes behavior while keeping the module syntactically valid.  It is
    accepted only after the Docker run proves imports/collection and P2P stay green.
    """
    path = ""
    found: list[tuple[str, str, str, str]] = []
    for raw in patch.read_text(errors="replace").splitlines():
        if raw.startswith("+++ b/"):
            path = _safe_rel(raw[6:])
            continue
        if not path or not raw.startswith("+") or raw.startswith("+++"):
            continue
        old = raw[1:]
        replacements: list[tuple[str, str]] = []
        if " < " in old and " <= " not in old:
            replacements.append(("lt-to-lte", old.replace(" < ", " <= ", 1)))
        if " > " in old and " >= " not in old:
            replacements.append(("gt-to-gte", old.replace(" > ", " >= ", 1)))
        if " <= " in old:
            replacements.append(("lte-to-lt", old.replace(" <= ", " < ", 1)))
        if " >= " in old:
            replacements.append(("gte-to-gt", old.replace(" >= ", " > ", 1)))
        if "return True" in old:
            replacements.append(("true-to-false", old.replace("return True", "return False", 1)))
        if "return False" in old:
            replacements.append(("false-to-true", old.replace("return False", "return True", 1)))
        if " == " in old:
            replacements.append(("eq-to-ne", old.replace(" == ", " != ", 1)))
        elif " != " in old:
            replacements.append(("ne-to-eq", old.replace(" != ", " == ", 1)))
        number = re.search(r"(?<![\w.])([1-9][0-9]*)(?![\w.])", old)
        if number and not old.lstrip().startswith(("import ", "from ")):
            value = int(number.group(1))
            changed = value - 1 if value > 1 else value + 1
            replacements.append(
                ("integer-boundary", old[: number.start(1)] + str(changed) + old[number.end(1) :])
            )
        return_value = re.match(r"^(\s*)return\s+(.+)$", old)
        if return_value and return_value.group(2) not in {"None", "True", "False"}:
            replacements.append(("return-to-none", return_value.group(1) + "return None"))
        string = re.search(r"(['\"])([^'\"\n]+)\1", old)
        if string:
            replacements.append(
                (
                    "string-constant",
                    old[: string.end(2)] + "__mutated__" + old[string.end(2) :],
                )
            )
        if re.match(r"^\s+(?:raise\b|[A-Za-z_][\w.]*\s*\(|[A-Za-z_]\w*\s*=)", old):
            indent = old[: len(old) - len(old.lstrip())]
            replacements.append(("statement-to-pass", indent + "pass"))
        for label, new in replacements:
            if new != old:
                found.append((label, path, old, new))
    return found[:12]


def _gold_hunks(patch: Path) -> list[str]:
    """Return standalone per-hunk patches suitable for reversing after gold."""
    hunks: list[str] = []
    headers: list[str] = []
    current: list[str] | None = None
    for raw in patch.read_text(errors="replace").splitlines():
        if raw.startswith("diff --git "):
            if current:
                hunks.append("\n".join([*headers, *current]) + "\n")
            headers = [raw]
            current = None
        elif raw.startswith("@@ "):
            if current:
                hunks.append("\n".join([*headers, *current]) + "\n")
            current = [raw]
        elif current is not None:
            current.append(raw)
        else:
            headers.append(raw)
    if current:
        hunks.append("\n".join([*headers, *current]) + "\n")
    return hunks[:12]


def _write_mutation_script(path: Path, rel: str, old: str, new: str) -> None:
    path.write_text(
        "from pathlib import Path\n"
        f"p = Path('/app') / {rel!r}\n"
        "text = p.read_text()\n"
        f"old = {old!r}\n"
        f"new = {new!r}\n"
        "assert old != new and text.count(old) == 1\n"
        "p.write_text(text.replace(old, new, 1))\n"
    )


def _check_mutations(
    task_dir: Path,
    wrong_patches: list[Path],
    new_tests: list[str],
    f2p: list[str],
    p2p: list[str],
) -> str:
    diagnostics = 0
    for wrong in wrong_patches:
        run = _docker_run(task_dir, gold=True, mutation=wrong, files=new_tests)
        if not run.patch_error and any(run.tests.get(node) == "FAILED" for node in f2p):
            diagnostics += 1

    candidates = _semantic_mutations(task_dir / "solution" / "patch.diff")
    with tempfile.TemporaryDirectory(prefix="click-factory-mutations-") as tmp:
        tmp_dir = Path(tmp)
        for index, (label, rel, old, new) in enumerate(candidates, 1):
            script = tmp_dir / f"semantic-{index}.py"
            _write_mutation_script(script, rel, old, new)
            run = _docker_run(
                task_dir,
                gold=True,
                mutation_script=script,
                files=None,
            )
            if run.patch_error:
                continue
            if any(status == "ERROR" for status in run.tests.values()):
                continue
            if any(run.tests.get(node) != "PASSED" for node in p2p):
                continue
            killed = [node for node in f2p if run.tests.get(node) == "FAILED"]
            if killed:
                return (
                    f"semantic mutation passed: {label} in {rel} killed {len(killed)} F2P; "
                    f"{diagnostics}/{len(wrong_patches)} model wrong patch(es) also bit"
                )
        fallback_count = 0
        if not candidates:
            for index, patch_text in enumerate(
                _gold_hunks(task_dir / "solution" / "patch.diff"), 1
            ):
                fallback_count += 1
                hunk = tmp_dir / f"gold-hunk-{index}.diff"
                hunk.write_text(patch_text)
                run = _docker_run(
                    task_dir,
                    gold=True,
                    mutation=hunk,
                    reverse_mutation=True,
                    files=None,
                )
                if run.patch_error or any(status == "ERROR" for status in run.tests.values()):
                    continue
                if any(run.tests.get(node) != "PASSED" for node in p2p):
                    continue
                killed = [node for node in f2p if run.tests.get(node) == "FAILED"]
                if killed:
                    return (
                        f"gold-hunk revert passed: hunk {index} killed {len(killed)} F2P; "
                        f"{diagnostics}/{len(wrong_patches)} model wrong patch(es) also bit"
                    )
    raise CheckFailure(
        "mutation",
        f"no clean semantic gold corruption killed F2P while imports/collection and all {len(p2p)} P2P stayed green; "
        f"candidates={len(candidates)}, fallback_hunks={fallback_count}",
    )


def _tool_path(name: str) -> Path:
    local = ROOT / "harness" / name
    supplied = KIT / "harness" / name
    if local.exists():
        return local
    if supplied.exists():
        return supplied
    raise CheckFailure(name, f"cannot find harness/{name}; set INNODATA_TRACK1_KIT")


def _python_command(script: Path, *args: str) -> list[str]:
    if sys.version_info >= (3, 11):
        return [sys.executable, str(script), *args]
    return ["uv", "run", "--no-project", "--python", "3.12", "python", str(script), *args]


def _structure(task_dir: Path) -> str:
    checker = _tool_path("check_structure.py")
    proc = subprocess.run(_python_command(checker, str(task_dir)), text=True, capture_output=True)
    if proc.returncode:
        raise CheckFailure("structure", proc.stdout + "\n" + proc.stderr)
    return _short(proc.stdout + "\n" + proc.stderr)


def _selfcheck(task_dir: Path) -> str:
    script = _tool_path("selfcheck.sh")
    with tempfile.TemporaryDirectory(prefix="click-factory-selfcheck-") as tmp:
        tmp_dir = Path(tmp)
        env = os.environ.copy()
        env["SELFCHECK_OUT"] = tmp
        gnu_find = Path("/opt/homebrew/opt/findutils/libexec/gnubin")
        if gnu_find.is_dir():
            env["PATH"] = f"{gnu_find}:{env.get('PATH', '')}"
        try:
            proc = subprocess.run(
                ["bash", str(script), str(task_dir)],
                text=True,
                capture_output=True,
                env=env,
                timeout=DOCKER_TIMEOUT * 2,
            )
        except subprocess.TimeoutExpired as exc:
            raise CheckFailure("selfcheck", f"Harbor selfcheck timed out after {DOCKER_TIMEOUT * 2}s") from exc
        def latest_grade(baseline: str) -> dict:
            files = list((tmp_dir / task_dir.name / baseline).rglob("grading_details.json"))
            if not files:
                raise CheckFailure("selfcheck", f"{baseline} produced no grading_details.json")
            return json.loads(max(files, key=lambda path: path.stat().st_mtime).read_text())

        oracle = latest_grade("oracle")
        nop = latest_grade("nop")
        oracle_ok = (
            oracle.get("reward") == 1.0
            and oracle.get("f2p_passed") == oracle.get("f2p_total")
            and oracle.get("p2p_passed") == oracle.get("p2p_total")
        )
        nop_ok = (
            nop.get("reward") == 0.0
            and nop.get("f2p_passed") == 0
            and nop.get("p2p_passed") == nop.get("p2p_total")
        )
        if not oracle_ok or not nop_ok:
            raise CheckFailure(
                "selfcheck",
                f"explicit Harbor assertions failed: oracle={oracle}; nop={nop}\n{proc.stdout}\n{proc.stderr}",
            )
    if proc.returncode:
        raise CheckFailure("selfcheck", proc.stdout + "\n" + proc.stderr)
    return _short(
        proc.stdout
        + "\n"
        + proc.stderr
        + f"\nexplicit assertions: oracle=1.0, nop=0.0, P2P={nop.get('p2p_passed')}/{nop.get('p2p_total')}"
    )


def verify(task_dir: Path, wrong_patches: list[Path], p2p_files: list[str]) -> dict:
    """Render and validate one task, returning repair-safe structured diagnostics."""
    task_dir = Path(task_dir)
    wrong_patches = [Path(path) for path in wrong_patches]
    safe_p2p: list[str] = []
    try:
        safe_p2p = [_safe_rel(path) for path in p2p_files]
        new_tests = _copy_plumbing(task_dir, safe_p2p)
        base = _docker_run(task_dir, gold=False)
        gold = _docker_run(task_dir, gold=True)
        f2p, p2p = _derive_ids(base, gold, new_tests, safe_p2p)
        tests = task_dir / "tests"
        (tests / "fail_to_pass.json").write_text(json.dumps(f2p, indent=2) + "\n")
        (tests / "pass_to_pass.json").write_text(json.dumps(p2p, indent=2) + "\n")
        mutation_report = _check_mutations(task_dir, wrong_patches, new_tests, f2p, p2p)
        structure_report = _structure(task_dir)
        selfcheck_report = _selfcheck(task_dir)
        return {
            "ok": True,
            "stage": "all",
            "f2p_ids": f2p,
            "p2p_ids": p2p,
            "report": _short(
                f"F2P {len(f2p)}; P2P {len(p2p)}. {mutation_report}\n"
                f"{structure_report}\n{selfcheck_report}"
            ),
        }
    except CheckFailure as exc:
        return {
            "ok": False,
            "stage": exc.stage,
            "f2p_ids": [],
            "p2p_ids": [],
            "report": exc.report,
        }
    except Exception as exc:  # keep repair loop alive, but never mislabel as a product failure
        return {
            "ok": False,
            "stage": "checker",
            "f2p_ids": [],
            "p2p_ids": [],
            "report": _short(f"checker infrastructure error: {type(exc).__name__}: {exc}"),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--card", choices=("types", "argv", "help", "testing", "completion"))
    parser.add_argument("--p2p", action="append", default=[])
    parser.add_argument("--wrong-patch", action="append", type=Path, default=[])
    args = parser.parse_args()
    p2p = list(args.p2p)
    if args.card:
        from factory.cards import CARDS

        p2p.extend(CARDS[args.card]["p2p"])
    if not p2p:
        parser.error("provide --card or at least one --p2p")
    result = verify(args.task_dir, args.wrong_patch, p2p)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Write a Harbor 0.25 task package from a draft + its materialised patches."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import config, container

TASK_TOML = """[metadata]
name = "{iid}"
instance_id = "{iid}"
task = "swe-feature-implementation"
source_repo = "{repo}"
base_commit = "{base}"
license = "{license}"
language = "en"
programming_language = "{lang}"

[environment]
docker_image = ""
build_timeout_sec = {build}
cpus = 2
workdir = "/app"
memory_mb = 4096
network_mode = "public"

[agent]
timeout_sec = {agent}

[verifier]
environment_mode = "shared"
timeout_sec = {verifier}

[rollout_baseline.oracle]
reward = 1.0
[rollout_baseline.nop]
reward = 0.0
"""

SOLVE_SH = """#!/bin/bash
# Oracle: apply the reference implementation to /app.
set -e
git -C /app apply "$(dirname "$0")/patch.diff"
echo "gold applied to /app"
"""

RUN_SCRIPT = """#!/usr/bin/env bash
# Run the graded test files that exist in the current tree (the feature file is absent at base).
# Not `set -e`: pytest exits non-zero when the feature is missing.
set -uo pipefail
cd /app
PY=/app/.venv/bin/python
[ -x "$PY" ] || PY="$(command -v python)"
ALL=(
{files}
)
PRESENT=()
for f in "${{ALL[@]}}"; do [ -e "$f" ] && PRESENT+=("$f"); done
[ "${{#PRESENT[@]}}" -eq 0 ] && {{ echo "no graded test files present"; exit 0; }}
"$PY" -m pytest "${{PRESENT[@]}}" -rA --tb=short -p no:cacheprovider -p no:randomly --color=no --continue-on-collection-errors
"""


def instance_id(draft) -> str:
    return f"{config.INSTANCE_PREFIX}-{draft.slug}-{draft.knob_hash()}"


def write(draft, gold: str, test_patch: str, f2p: list[str], p2p: list[str], out: Path,
          provenance: dict | None = None) -> Path:
    """``provenance`` (written only for drafts with authored compatibility tests) splits
    ``pass_to_pass.json`` into upstream regression tests and newly authored ones; grade.py ignores it."""
    iid = instance_id(draft)
    pkg = out / iid
    if pkg.exists():
        shutil.rmtree(pkg)
    (pkg / "solution").mkdir(parents=True)
    (pkg / "tests").mkdir()
    (pkg / "environment").mkdir()
    (pkg / "task.toml").write_text(TASK_TOML.format(
        iid=iid, repo=config.SOURCE_REPO, base=config.BASE_COMMIT, license=config.LICENSE,
        lang=config.LANGUAGE, build=config.TASK_TIMEOUTS["build"], agent=config.TASK_TIMEOUTS["agent"],
        verifier=config.TASK_TIMEOUTS["verifier"]))
    (pkg / "instruction.md").write_text(draft.instruction.strip() + "\n")
    (pkg / "solution" / "patch.diff").write_text(gold)
    (pkg / "solution" / "solve.sh").write_text(SOLVE_SH)
    (pkg / "tests" / "test_patch.diff").write_text(test_patch)
    (pkg / "tests" / "fail_to_pass.json").write_text(json.dumps(f2p, indent=2) + "\n")
    (pkg / "tests" / "pass_to_pass.json").write_text(json.dumps(p2p, indent=2) + "\n")
    if draft.compat_test_files:
        (pkg / "tests" / "p2p_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    files = sorted({n.split("::")[0] for n in p2p} | set(draft.test_files))
    (pkg / "tests" / "run_script.sh").write_text(
        RUN_SCRIPT.format(files="\n".join(f'  "{f}"' for f in files)))
    for name in ("grade.py", "parser.py", "test.sh"):
        shutil.copy(config.TEMPLATES / name, pkg / "tests" / name)
    (pkg / "environment" / "Dockerfile").write_text(container.render_dockerfile())
    for p in pkg.rglob("*.sh"):
        p.chmod(0o755)
    return pkg

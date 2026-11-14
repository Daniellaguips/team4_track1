"""Container helpers for the factory's own gates.

The gates run the *package's own* grader (tests/test.sh -> grade.py) inside the image built from
the package's own environment/Dockerfile, so a local verdict means the same thing as Harbor's.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import config


def render_dockerfile() -> str:
    t = (config.TEMPLATES / "Dockerfile.tmpl").read_text()
    return t.replace("{base_commit}", config.BASE_COMMIT).replace("{base_tag}", config.BASE_TAG)


def image_tag() -> str:
    h = hashlib.sha256(render_dockerfile().encode()).hexdigest()[:12]
    return f"localhost/t1-click-env:{h}"


def ensure_image(log: Path | None = None) -> str:
    tag = image_tag()
    if subprocess.run([config.ENGINE, "image", "exists", tag] if config.ENGINE == "podman"
                      else [config.ENGINE, "image", "inspect", tag],
                      capture_output=True).returncode == 0:
        return tag
    ctx = Path(tempfile.mkdtemp(prefix="t1img_", dir=str(config.WORK)))
    (ctx / "Dockerfile").write_text(render_dockerfile())
    t0 = time.time()
    p = subprocess.run([config.ENGINE, "build", "-t", tag, str(ctx)], capture_output=True, text=True)
    if log:
        log.write_text(f"$ {config.ENGINE} build -t {tag}\nexit={p.returncode} secs={time.time()-t0:.1f}\n"
                       + p.stdout[-20000:] + p.stderr[-20000:])
    shutil.rmtree(ctx, ignore_errors=True)
    if p.returncode != 0:
        raise RuntimeError(f"image build failed (exit {p.returncode})")
    return tag


def run(cmd: str, mounts: dict[str, str] | None = None, network: bool = False,
        timeout: int = 1800) -> subprocess.CompletedProcess:
    args = [config.ENGINE, "run", "--rm"]
    if not network:
        args += ["--network", "none"]
    for host, cont in (mounts or {}).items():
        args += ["-v", f"{host}:{cont}"]
    args += [image_tag(), "bash", "-c", cmd]
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def grade(pkg: Path, patch: str | None, out_dir: Path) -> dict:
    """Apply ``patch`` (None = nop) to /app, then run the package verifier exactly like Harbor:
    tests mounted at /tests, verifier output at /logs/verifier."""
    out_dir.mkdir(parents=True, exist_ok=True)
    vdir = out_dir / "verifier"
    if vdir.exists():
        shutil.rmtree(vdir)
    vdir.mkdir()
    sol = out_dir / "applied.diff"
    sol.write_text(patch or "")
    cmd = ("cd /app || { echo T1_STAGE_FAIL=cd; exit 90; }; "
           "if [ -s /sol/applied.diff ]; then "
           "git apply /sol/applied.diff || { echo T1_STAGE_FAIL=apply_patch; exit 91; }; fi; "
           "bash /tests/test.sh; echo TEST_SH_EXIT=$?")
    t0 = time.time()
    p = run(cmd, mounts={str((pkg / "tests").resolve()): "/tests:ro",
                         str(out_dir.resolve()): "/sol:ro",
                         str(vdir.resolve()): "/logs/verifier"})
    (out_dir / "container.log").write_text(f"exit={p.returncode} secs={time.time()-t0:.1f}\n"
                                           f"--- stdout\n{p.stdout[-20000:]}\n--- stderr\n{p.stderr[-20000:]}")
    d = read_result(out_dir, exit_code=p.returncode, stdout=p.stdout)
    d["secs"] = round(time.time() - t0, 1)
    return d


def read_result(out_dir: Path, exit_code: int | None = None, stdout: str | None = None) -> dict:
    """Load one grading run from disk. Without ``exit_code``/``stdout`` they are recovered from
    ``container.log``, so saved historical runs can be re-classified offline."""
    out_dir = Path(out_dir)
    vdir = out_dir / "verifier"
    if stdout is None or exit_code is None:
        log = (out_dir / "container.log").read_text(errors="replace") \
            if (out_dir / "container.log").exists() else ""
        m = re.match(r"exit=(-?\d+)", log)
        exit_code = int(m.group(1)) if m and exit_code is None else exit_code
        stdout = log if stdout is None else stdout
    m = re.findall(r"^TEST_SH_EXIT=(\d+)\s*$", stdout, re.M)
    stage = re.findall(r"^T1_STAGE_FAIL=(\w+)\s*$", stdout, re.M)
    meta = {"exit": exit_code, "test_sh_exit": int(m[-1]) if m else None,
            "stage_fail": stage[-1] if stage else None}
    pylog = vdir / "stdout.log"
    meta["pytest_log"] = pylog.read_text(errors="replace") if pylog.exists() else None
    gd = vdir / "grading_details.json"
    if not gd.exists():
        return {"reward": None, "error": "no grading_details.json", "records": [], "statuses": {}, **meta}
    d = json.loads(gd.read_text())
    out = json.loads((vdir / "output.json").read_text()) if (vdir / "output.json").exists() else {}
    d["records"] = [(t["name"], t["status"]) for t in out.get("tests", [])]
    # Last record wins, exactly as grade.py builds its status map.
    d["statuses"] = {n: s for n, s in d["records"]}
    d.update(meta)
    return d


# POSIX sh (no bash, no pipefail): pytest's own exit status is captured before any output
# processing, and every earlier stage reports which step failed.
FULL_SUITE_SH = """cd {app} || {{ echo T1_STAGE_FAIL=cd; exit 90; }}
git apply {sol}/gold.diff || {{ echo T1_STAGE_FAIL=apply_gold; exit 91; }}
git apply {sol}/tests.diff || {{ echo T1_STAGE_FAIL=apply_tests; exit 92; }}
{pytest} > {out}/pytest.log 2>&1
rc=$?
echo T1_PYTEST_EXIT=$rc
tail -n 3 {out}/pytest.log
exit $rc
"""

FULL_SUITE_PYTEST = "python -m pytest -q -p no:cacheprovider --color=no tests"


def full_suite_script(app: str = "/app", sol: str = "/sol", out: str = "/out",
                      pytest: str = FULL_SUITE_PYTEST) -> str:
    return FULL_SUITE_SH.format(app=app, sol=sol, out=out, pytest=pytest)

"""Container helpers for the factory's own gates.

The gates run the *package's own* grader (tests/test.sh -> grade.py) inside the image built from
the package's own environment/Dockerfile, so a local verdict means the same thing as Harbor's.
"""
from __future__ import annotations

import hashlib
import json
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
    cmd = ("set -e; cd /app; if [ -s /sol/applied.diff ]; then git apply /sol/applied.diff; fi; "
           "set +e; bash /tests/test.sh; echo TEST_SH_EXIT=$?")
    t0 = time.time()
    p = run(cmd, mounts={str((pkg / "tests").resolve()): "/tests:ro",
                         str(out_dir.resolve()): "/sol:ro",
                         str(vdir.resolve()): "/logs/verifier"})
    (out_dir / "container.log").write_text(f"exit={p.returncode} secs={time.time()-t0:.1f}\n"
                                           f"--- stdout\n{p.stdout[-20000:]}\n--- stderr\n{p.stderr[-20000:]}")
    gd = vdir / "grading_details.json"
    if not gd.exists():
        return {"reward": None, "error": "no grading_details.json", "exit": p.returncode}
    d = json.loads(gd.read_text())
    d["exit"] = p.returncode
    d["secs"] = round(time.time() - t0, 1)
    out = json.loads((vdir / "output.json").read_text()) if (vdir / "output.json").exists() else {}
    d["statuses"] = {t["name"]: t["status"] for t in out.get("tests", [])}
    return d

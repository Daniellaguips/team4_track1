"""Pinned inputs of the factory. Everything a re-run needs to reproduce a batch lives here."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = Path(__file__).resolve().parent / "templates"

SOURCE_REPO = "pallets/click"
REPO_URL = "https://github.com/pallets/click.git"
BASE_TAG = "8.5.1"
BASE_COMMIT = "cf19179e8e2fd54c601378cec9e0d21bb12b6fb1"
LICENSE = "BSD-3-Clause"
LANGUAGE = "python"
INSTANCE_PREFIX = "pallets__click"

PIPELINE_NAME = "track1-freestyle/click-blueprint-factory"
PIPELINE_VERSION = "1.0.0"

# Scratch space for clones, images and per-gate container runs (kept out of the submission).
WORK = Path(os.environ.get("T1_WORK", "/tmp/t1_factory_work"))
UPSTREAM = WORK / "upstream" / "click"

# Container engine used by the factory's own gates (Harbor is driven separately).
ENGINE = os.environ.get("T1_ENGINE", "podman")

# Regression curation limits.
P2P_PER_SYMBOL = 12
P2P_CAP = 90

TASK_TIMEOUTS = {"agent": 1800.0, "verifier": 900.0, "build": 1800.0}

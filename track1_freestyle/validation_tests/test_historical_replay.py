"""The hardened gates must still accept the saved V1 batch runs (offline re-classification of
historical container output; nothing is re-executed)."""
from __future__ import annotations

from pathlib import Path

import pytest

from replay_historical import replay_attempt

ROOT = Path(__file__).resolve().parent.parent
V1_ATTEMPTS = sorted((ROOT / "runs/20261114T115550_batch5/candidates").glob("*/attempt_1"))


def test_v1_batch_present():
    assert len(V1_ATTEMPTS) == 5


@pytest.mark.parametrize("adir", V1_ATTEMPTS, ids=lambda p: p.parent.name)
def test_v1_saved_runs_still_accepted(adir):
    r = replay_attempt(adir)
    assert r["replayed"] == {"gold": True, "nop": True, "mutation": True}, r["problems"]
    assert set(r["mutant_verdicts"].values()) == {"killed"}

"""Variation planner: decides which blueprint and which knob vector each slot of a batch gets.

A batch of N first covers N *different* families (different capability / module / behaviour
shape, see each family's AXES). Within a family, a seeded RNG picks a knob vector; vectors already
emitted (listed in the ledger) are skipped so a fresh run yields behaviourally new tasks.
"""
from __future__ import annotations

import itertools
import json
import random
from pathlib import Path

from .families import PLANNED, REGISTRY


def knob_space(mod) -> list[dict]:
    keys = sorted(mod.KNOBS)
    return [dict(zip(keys, vals)) for vals in itertools.product(*(mod.KNOBS[k] for k in keys))]


def load_ledger(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.dumps({"family": e["family"], "knobs": e["knobs"]}, sort_keys=True)
            for e in json.loads(path.read_text())}


def plan(n: int, seed: int, ledger: Path | None = None, families: list[str] | None = None) -> list[tuple[str, dict]]:
    rng = random.Random(seed)
    used = load_ledger(ledger) if ledger else set()
    fams = families or list(PLANNED)
    out: list[tuple[str, dict]] = []
    order = fams[:]
    rng.shuffle(order)
    i = 0
    while len(out) < n and i < n * 10:
        fam = order[i % len(order)]
        i += 1
        space = [k for k in knob_space(REGISTRY[fam])
                 if json.dumps({"family": fam, "knobs": k}, sort_keys=True) not in used]
        if not space:
            continue
        k = rng.choice(space)
        used.add(json.dumps({"family": fam, "knobs": k}, sort_keys=True))
        out.append((fam, k))
    return out


def record(ledger: Path, plan_: list[tuple[str, dict]]) -> None:
    cur = json.loads(ledger.read_text()) if ledger.exists() else []
    cur += [{"family": f, "knobs": k} for f, k in plan_]
    ledger.write_text(json.dumps(cur, indent=1))

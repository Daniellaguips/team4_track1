"""Blueprint registry. Each module exposes FAMILY, KNOBS, AXES and build(knobs) -> Draft.

``PLANNED`` are the families the batch planner draws from by default (the V1 set, so a seeded
V1 batch plan stays reproducible). ``EXPLICIT_ONLY`` families are generated only when requested
with ``--family``.
"""
from __future__ import annotations

import importlib

NAMES = ["duration", "abbrev", "conflicts", "attempts", "sections"]
EXPLICIT_ONLY = ["collisions"]
REGISTRY = {}
for _n in NAMES + EXPLICIT_ONLY:
    try:
        _m = importlib.import_module(f"{__name__}.{_n}")
    except ModuleNotFoundError as _e:
        if _e.name != f"{__name__}.{_n}":
            raise
        continue
    REGISTRY[_m.FAMILY] = _m
PLANNED = [f for f in REGISTRY if f not in EXPLICIT_ONLY]

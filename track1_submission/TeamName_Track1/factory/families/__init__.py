"""Blueprint registry. Each module exposes FAMILY, KNOBS, AXES and build(knobs) -> Draft."""
from __future__ import annotations

import importlib

NAMES = ["duration", "abbrev", "conflicts", "attempts", "sections"]
REGISTRY = {}
for _n in NAMES:
    try:
        _m = importlib.import_module(f"{__name__}.{_n}")
    except ModuleNotFoundError as _e:
        if _e.name != f"{__name__}.{_n}":
            raise
        continue
    REGISTRY[_m.FAMILY] = _m

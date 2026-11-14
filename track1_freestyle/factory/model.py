"""Data model shared by blueprints and the pipeline."""
from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any


@dataclasses.dataclass(frozen=True)
class Edit:
    """Anchored source edit. ``anchor`` must occur exactly once in the file it targets;
    that is the grounding contract: a blueprint can only extend code that really exists."""

    path: str
    anchor: str
    text: str
    mode: str = "after"  # "after" | "before" | "replace"


@dataclasses.dataclass(frozen=True)
class Mutant:
    """A plausible wrong implementation, expressed as edits on top of the gold tree."""

    name: str
    description: str
    edits: tuple[Edit, ...]


@dataclasses.dataclass
class Draft:
    """Everything a blueprint emits for one concrete knob setting."""

    family: str
    slug: str
    title: str
    knobs: dict[str, Any]
    instruction: str
    gold_edits: list[Edit]
    test_files: dict[str, str]
    # Existing symbols ("path::Qualname") the feature extends or mirrors. Used for grounding
    # and to steer regression-test curation in addition to the gold's enclosing functions.
    focus_symbols: list[str]
    mutants: list[Mutant]
    # Regexes that would reveal the capability already existing upstream.
    novelty_probes: list[str]
    novelty_queries: list[str]
    axes: dict[str, str]
    # Newly authored tests that pin existing behaviour: they pass at base and under gold, so they
    # are graded as pass-to-pass (with "authored_compatibility" provenance), never as F2P.
    compat_test_files: dict[str, str] = dataclasses.field(default_factory=dict)

    def knob_hash(self) -> str:
        blob = json.dumps({"family": self.family, "knobs": self.knobs}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:6]

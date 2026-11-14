# team4 — LLM task factory with a difficulty feedback loop (complements `track1_freestyle`)

`track1_freestyle/` (the submission) produces valid tasks from hand-written blueprints. When we
benchmarked them, **Haiku 5.5 resolved all 5 tasks 3/3**. This folder is the follow-up: an
LLM-driven generator that **measures its own tasks against the benchmark model and automatically
redesigns the ones that are too easy.** Built by Daniella with Claude (Opus 5.5) and Codex; the
plan was rated by Claude Fable 5.2 and Codex. **Snapshot taken at ~2:15 PM while runs were still in progress.**

## Pipeline (`factory/generate.py`)
1. **Design** (Sonnet 5.5): a frozen contract of 10–12 rules. The design must stack ≥3 hardness
   levers: cross-module change, modified existing behavior, subclass/hook routes, precedence,
   state across calls. One rule is an explicit route matrix (main / CliRunner / ctx.invoke /
   forward / nested / chain).
2. **Novelty**: the feature's own new identifiers must be absent from upstream `click` main.
3. **Spec + gold**: the statement states only observable behavior (no internals, ≤3 syntax-only
   examples).
4. **Tests written blind** from the statement only. At least 1/3 are `test_r<N>_combo_*`
   rule-combination tests, each with `# decided by R<N>`.
5. **Fairness gates**:
   - mechanical: rule coverage both ways, expected messages verbatim in the statement, no leakage
     or examples table, gold ≥120 lines across ≥3 files
   - a blind LLM judge
6. **Soundness** (`factory/check.py`, written by Codex):
   - F2P = fail at base and pass at gold
   - P2P = PASSED at both
   - nop reward 0.0 and oracle 1.0 asserted
   - semantic gold mutation (per-hunk revert as fallback)
   - organizer `check_structure` + Harbor `selfcheck`
7. **Targeted repairs** (max 2), then **telemetry**: every call in `calls.jsonl`, plus
   `pipeline_run.json` with tokens and $. `--replay` rebuilds a run without API calls.

## Difficulty feedback loop (`factory/feedback.py`)
```bash
export OPENROUTER_API_KEY=...   # organizer key, env only
uv run python -m factory.feedback loop
```
- Every gate-passing task is benchmarked automatically: terminus-2 +
  `openrouter/anthropic/claude-haiku-5.5`, k=3. The score goes to `runs/<iid>/benchmark.json`.
- **resolve@3 ≥ 2/3 → retired automatically.** A harder replacement is generated once
  (`--card C --seed S+100 --harder-than IID`): a different feature with more cross-rule
  interactions and modules.
- **Only the score feeds back**, never the agent's trajectory or code. The rule was fixed before any
  results (plan v6.2 §3). The replacement is benchmarked with fresh rollouts and submitted if valid
  regardless of its own score. Both results are disclosed: no post-hoc selection.

## Evidence so far (see `evidence/`)
- **Pilot `click.Duration`** (`generated_tasks/pallets__click-types-0001`):
  - passed every gate on attempt 3, $0.58
  - F2P 124 / P2P 769
  - Haiku **3/3** — too easy, which motivated the hardness levers
- **Hard `state` task** (`generated_tasks/pallets__click-state-0001`, run-wide event ledger through
  invoke/forward/chain/subclasses):
  - first gate verdict blocked only by two checker bugs (xfail P2P, 0 mutation candidates)
  - after the fix, the same package re-verified: **ALL SOUND, F2P 126, P2P 302**, semantic mutation
    killed 8 F2P
  - Haiku benchmark was running at snapshot time
- **Several hard candidates were correctly rejected** by the fairness gates (unstated behavior,
  leaked internals, self-contradicting examples). That's the cost of keeping hard tasks fair.
- Research behind the levers: `plan/WHAT-STUMPS-HAIKU.md`. Plan and reviews: `plan/`.

## Run
```bash
uv sync
docker build -t click-base:8.5.1 <base Dockerfile = any generated_tasks/*/environment/Dockerfile>
export OPENROUTER_API_KEY=... FACTORY_MIN_F2P=12 FACTORY_MAX_TOKENS=64000
uv run python -m factory.generate --card state --seed 1      # one task, all gates
uv run python -m factory.generate --card state --seed 1 --replay   # rebuild from the log, $0
```
Cards: `types, argv, help, testing, completion` (single-module) and `sources, state, argv_hard,
help_hard` (hard, multi-lever). Spend for the whole session was about $10–15 of the $100 key.

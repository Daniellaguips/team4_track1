# What stumps Haiku — evidence so far (team4, Nov 14)

## Our own measurements (terminus-2 + openrouter/anthropic/claude-haiku-5.5, k=3)
- click.Duration (LLM-generated, 11 explicit rules, 124 F2P): **3/3 solved**, 10–12 agent steps,
  2.5–5 min, ~$0.015/attempt. Haiku writes the feature in one file, builds its own quick tests from
  the spec's examples table, runs pytest repeatedly, and fixes until green.
- Teammate blueprints (track1_freestyle): results being filled in as they finish.

## Why isolated, well-specified features are easy
A self-contained feature + examples table = a recipe Haiku can self-verify. Rule count alone does
not create difficulty.

## Levers ranked by evidence (web research; numbers from search snippets)
1. **Cross-file / cross-module change** — SWE-Bench Pro fixes avg 107 lines / 4.1 files vs 11.6 lines
   on Verified; resolve rates fall as files grow; NoCode-bench best 28% citing cross-file editing.
   arxiv.org/pdf/2509.16941 · arxiv.org/abs/2507.18130
2. **Preserve existing behavior while changing it (regressive implementation)** — FeatBench: the
   dominant failure in 122 analyzed agent failures was breaking existing behavior (scope creep).
   arxiv.org/html/2509.22237v1
3. **Long-horizon, dependent edits** — 60–69% of failures attributed to edit quality; failed
   trajectories are longer. arxiv.org/pdf/2603.24631 · arxiv.org/pdf/2604.02547
4. Interaction with extension points / subclassing (inference): feature must still apply when users
   subclass Command/Group/Option/Context (custom command_class, context_class, parse_args).
5. Precedence across many existing rules (inference): e.g. a new value source slotted into
   CLI → envvar → default_map → prompt → default, tested pairwise incl. multiple/nargs/flags.
6. State across calls (inference): invocation-scoped state through ctx.invoke/forward, chained
   groups, result_callback, reset between CliRunner.invoke calls.
**Stack 2–3 levers per task; one lever alone is likely solvable.**

## Keep it fair (avoid)
Tests asserting anything the spec doesn't state (message text, names, formatting, ordering),
unspecified precedence conflicts, incidental current behavior, scope so big it's a token-budget test.
Fair pattern: state every public name, signature, message and precedence rule; difficulty comes only
from integrating with code the agent must read.

"""Prompt templates v7 (Arian Berisha, PROMPTS.md): observable deps, no examples."""

VERSION = "v7-observable-deps"

SYSTEM_HEADER = """You are a senior Python engineer designing benchmark tasks for AI coding agents on the real
open-source repository pallets/click, pinned at release 8.5.1. Below is the relevant source of the
pinned repository. Everything you write must be consistent with this exact code.

Two kinds of facts exist in every task:
- OBSERVABLE behavior: what a user sees through the public API (return values, output, exit codes,
  exception types and messages, attribute values on public objects, the order of events).
- INTERNALS: which function implements something, private names (leading underscore, sentinels),
  how the code is structured, where to make the edit.
A task statement must state every observable fact its tests depend on, including facts about
EXISTING click behavior. It must never state internals.
"""

DESIGN = """Design the contract for ONE new click feature.

CARD: {card} — capability axis: {shape}
BLUEPRINT: {blueprint}
SEED: {seed}

Requirements:
- Realistic, public, opt-in, backward compatible (existing behavior and tests unchanged).
- Not already in click (check the source above); not a drop-in of a known extension library.
- 10 to 12 rules R1..Rn. At least 3 rules state an explicit interaction or precedence with another
  rule in one sentence. Exact error message strings. At least 2 traps where the obvious
  implementation is wrong (exact vs float arithmetic, inclusive vs exclusive bounds, ordering,
  duplicates, state reset).
- Respect repo constraints visible above (tests/test_imports.py allowlist of module-level imports;
  pytest runs with filterwarnings=error).
- Roughly 250-400 changed lines across at least 4 files (src + package exports).

HARDNESS LEVERS. Measured: an isolated feature with an examples table is solved 3/3 by the
benchmark agent, which self-verifies from the statement's examples. Stack at least 3 of:
  L1 cross-module: at least 3 click modules change, each with behavior the tests observe;
  L2 modify existing behavior: existing code paths change, and the rules state which existing
     behaviors stay byte-identical (tests pin them);
  L3 extension points: works through user subclasses / hooks (context_class, command_class,
     overridden parse_args/format_* methods, nested Groups, chain=True);
  L4 precedence: an explicit precedence table among the new behavior and existing sources
     (CLI / envvar / default_map / prompt / default, or command lookup order), tested pairwise;
  L5 state: invocation-scoped state through ctx.invoke / ctx.forward / chained groups /
     result_callback, reset between separate CliRunner.invoke calls.
Difficulty must come from integrating with code the agent has to read, never from hidden
requirements.

ROUTE MATRIX: one rule lists main(), CliRunner.invoke, ctx.invoke, ctx.forward, nested groups and
chain=True groups, each 'same' / 'different' / 'N/A', with the exact observable outcome or reason
for 'different' and 'N/A'. No blanket 'where applicable'.

RELIED-ON EXISTING BEHAVIOR: list every fact about EXISTING click behavior that a test of this
feature will depend on, written as observable behavior with a concrete example. Examples of the
right form: "A command run through ctx.invoke(cmd) gets a sub-context whose info_name is cmd.name",
"After parsing, ctx.args holds the leftover tokens in order". Each fact must be true at 8.5.1
(check the source above) and reachable through the public API. If a rule would need a PRIVATE
value (a sentinel, an underscore name), redesign the rule so it does not.

Reply with ONLY a ```json block:
{{"feature": "...", "summary": "...", "public_api": ["..."], "keywords": ["grep terms"],
  "rules": [{{"id": "R1", "text": "...", "inputs": "...", "output": "...",
             "errors": "exact type + message or none", "precedence": "...", "bounds": "...",
             "state": "..."}}],
  "relied_on": [{{"fact": "...", "example": "...", "used_by": ["R3", "R7"]}}],
  "traps": ["..."], "levers": ["L1", "..."]}}
"""

SPEC_GOLD = """Implement this FROZEN contract. Do not add, drop or change rules or relied-on facts.

CONTRACT:
{design}

Produce exactly these tagged sections and nothing else:

<instruction_md>
The task statement for the coding agent (Markdown), in this order:
1. Title and a 2-3 sentence motivation.
2. Public interface: every new public name, signature, default and export location.
3. Rules: EVERY rule as "R1. ...", "R2. ..." (same ids, complete, exact error message strings,
   every precedence sentence, the route matrix).
4. "Existing click behavior relied on": every relied_on fact from the contract, as observable
   behavior with its example. This section is REQUIRED whenever relied_on is non-empty.
Do NOT include: which function or file to edit, private names, how existing code is structured,
trap lists, common mistakes, examples tables, or input/output example lists. Do not mention
tests or a reference solution. Every observable fact a test could depend on must be in sections 2-4.
</instruction_md>

<edit file="src/click/<path>.py">
<search>
exact existing lines of the pinned source (must occur exactly once in that file)
</search>
<replace>
replacement lines (repeat the original lines if inserting next to them)
</replace>
</edit>
(as many <edit> blocks as needed; only files under src/click/. To CREATE a new module, use an empty
<search></search> and put the whole file in <replace>; import/export it where needed.)
The gold must keep every existing test green, including tests/test_chain.py and tests/test_context.py.
"""

TESTS = """Write the hidden test file for this task. You see ONLY the task statement. Test exactly what it
states, nothing more.

TASK STATEMENT:
{instruction}

Rules:
- A NEW pytest file at path {test_path}.
- Test only observable public behavior (CliRunner output/exit codes, return values, exception types
  and messages, public attributes). Every expected string or message is copied verbatim from the
  statement.
- NEVER use private names (leading underscore, sentinels, internal modules) and never rely on a
  default or implicit value of existing click behavior UNLESS the statement's "Existing click
  behavior relied on" section states it. When in doubt, set it up explicitly in the test (pass
  name=, info_name=, default=, obj= explicitly) instead of relying on the default.
- At least ONE THIRD of the test functions check COMBINATIONS: two or more rules interacting, or
  the feature meeting existing click behavior the statement describes. Name them
  test_r<N>_combo_* using the lowest rule id involved, and add a comment
  `# decided by R<N>` naming the single statement sentence that decides the expected outcome.
  If you cannot name one deciding sentence, do not write that test.
- Combo tests use a route other than a direct call (CliRunner, nested or chained groups,
  ctx.invoke/forward, a user subclass).
- Every test function name starts with test_r<N>_; cover every rule; use pytest.mark.parametrize
  for at least 20 test cases in total.
- Must pass under pytest with filterwarnings=error; deterministic; no network or sleeps.
- The file MUST collect on the unmodified repository: never import new names at module level;
  reference them inside each test (e.g. `click.NewThing(...)`), so tests fail by assertion, not
  by import error.

Reply with ONLY:
<test_file path="{test_path}">
...python...
</test_file>
"""

REPAIR = """An automatic check failed for this task package.

FAILED STAGE: {stage}
DIAGNOSTICS:
{report}

CONTRACT (frozen, authoritative):
{design}

CURRENT TASK STATEMENT:
{instruction}

CURRENT GOLD EDITS AND TEST FILE:
{previous}

Decide what is wrong and return ONLY the corrected sections (any of <instruction_md>, <edit>
blocks, which must then be the COMPLETE set of gold edits, and <test_file path="...">).

Who fixes what:
- p2p (an existing test fails at gold): the GOLD is wrong. Fix the gold; never touch tests or
  statement for this.
- A test asserts something beyond the contract: fix the TEST.
- A test relies on existing click behavior: if that fact is in the contract's relied_on list but
  missing from the statement, ADD it to the statement's "Existing click behavior relied on"
  section. If it is not in relied_on, change the TEST to set the value up explicitly.
- A test uses a private name: rewrite the TEST without it.
- LEAKAGE (function to edit, private names, how code works, trap lists): remove it from the
  statement, keeping every observable sentence and every R<N> rule.
- The gold violates the contract: fix the GOLD.
- search-match failure: recopy every <search> block VERBATIM from the pinned ORIGINAL source in the
  system context (never from a previous replacement) and return the COMPLETE edit set.
"""

FAIRNESS = """Audit a benchmark task for fairness. You see the task statement given to the agent and the hidden
tests. A careful engineer who reads the statement and the public click documentation must be able
to predict every assertion.

STATEMENT:
{instruction}

TESTS:
{tests}

List as "unstated":
1. Any behavior a test depends on that the statement does not specify (exact strings, ordering,
   types, edge cases, state).
2. Any test that depends on EXISTING click behavior that is NOT in the statement's "Existing click
   behavior relied on" section AND is not set up explicitly in the test itself.
3. Any test that uses a private click name (leading underscore, sentinel, internal module).
4. For every *_combo_* test: if the `# decided by R<N>` sentence does not decide the outcome on its
   own, or two rules conflict and no sentence decides between them.
5. LEAKAGE in the statement: which function or file to edit, private names, explanations of how
   click's code is structured, lists of traps or common mistakes.
   Stating observable behavior of existing click (what a user can see) is NOT leakage.

Do not invent issues. Quote the exact test name and assertion for each item.

Reply with ONLY a ```json block: {{"unstated": ["<test name>: <issue>", ...]}}
(empty list if fully specified).
"""

HARDER = """

REDESIGN (automatic difficulty feedback): a previous task for this card, "{feature}", was RESOLVED
{resolved} by the benchmark agent, so it is retired. Its rules were:
{rules}
Design a DIFFERENT feature for this card (not a variant of the one above) that is strictly harder:
add 2-3 MORE cross-rule interactions with explicit precedence sentences, require changes in at
least one MORE module than before, and make at least one rule change existing behavior that must
stay byte-identical elsewhere. Only the score is known; do not guess at the agent's code. Every
rule stays fully stated and observable, and every relied-on existing behavior goes in relied_on.
"""

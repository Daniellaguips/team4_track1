"""Prompt templates (versioned; hashed into every call record)."""

VERSION = "v6.6.1-feedback"

SYSTEM_HEADER = """You are a senior Python engineer designing benchmark tasks for AI coding agents on the
real open-source repository pallets/click, pinned at release 8.5.1. Below is the relevant source of
the pinned repository. Everything you write must be consistent with this exact code.
"""

DESIGN = """Design the contract for ONE new click feature.

CARD: {card} — capability axis: {shape}
BLUEPRINT: {blueprint}
SEED: {seed}

Requirements:
- Realistic, public, opt-in, backward compatible (existing behavior and tests unchanged).
- Not already in click (check the source above); not a drop-in of a known extension library.
- 10 to 12 rules R1..Rn. At least 3 rules must state an explicit interaction/precedence with another
  rule in one sentence. Include exact error message strings. Include at least 2 traps where the
  obvious implementation is wrong (e.g. float vs exact arithmetic, inclusive vs exclusive bounds,
  ordering/precedence, duplicate handling, state reset). Everything must be observable through the
  public API and fully specified in words — no hidden conventions.
- Respect repo constraints visible above (tests/test_imports.py allowlist of module-level imports;
  pytest runs with filterwarnings=error).
- Implementable in roughly 250-400 changed lines across at least 4 files (src + package exports).

HARDNESS LEVERS (measured: an isolated, self-contained feature with an examples table is solved
3/3 by the benchmark agent; published evidence: cross-file changes, preserving existing behavior,
and long dependent edit chains are where agents fail). The design MUST stack at least 3 of:
  L1 cross-module: the change must touch at least 3 click modules (e.g. core.py + parser.py +
     formatting.py/shell_completion.py/testing.py), each with observable behavior in the tests;
  L2 modify existing behavior, not just add code: existing code paths must change, and the rules
     must state exactly which existing behaviors stay byte-identical (tests pin them);
  L3 extension points: the feature must keep working through user subclasses / hooks
     (context_class, command_class, custom parse_args/format_* overrides, nested Groups, chain=True);
  L4 precedence: a full, explicit precedence table among the new behavior and existing sources
     (CLI / envvar / default_map / prompt / default, or command lookup order), tested pairwise;
  L5 state: invocation-scoped state through ctx.invoke / ctx.forward / chained groups /
     result_callback, and reset between separate CliRunner.invoke calls.
State every rule explicitly — difficulty must come from integrating with code the agent has to
read, never from hidden requirements. Name the levers used in a "levers" field.
One rule MUST be an explicit ROUTE MATRIX: for each of main(), CliRunner.invoke, ctx.invoke,
ctx.forward, nested groups and chain=True groups, state 'same' / 'different' / 'N/A' and, for
'different' or 'N/A', the exact observable outcome or the reason. No blanket 'where applicable'.

Each rule is a contract row. Reply with ONLY a ```json block:
{{"feature": "...", "summary": "...", "public_api": ["..."], "keywords": ["grep terms"],
  "rules": [{{"id": "R1", "text": "...", "inputs": "...", "output": "...",
             "errors": "exact type + message or none", "precedence": "...", "bounds": "...",
             "state": "..."}}],
  "traps": ["..."], "levers": ["L1", "..."]}}
"""

SPEC_GOLD = """Implement this FROZEN contract. Do not add, drop or change rules.

CONTRACT:
{design}

Produce exactly these tagged sections and nothing else:

<instruction_md>
The task statement for the coding agent (Markdown): title, motivation, public interface, then EVERY
rule as "R1. ...", "R2. ..." (same ids, complete, including exact error message strings). State only
WHAT is observable through the public API. Never explain how existing click code works, when contexts
are built, which function to edit, or any private name. Do not list traps or common mistakes. Keep
every observable fact the tests depend on (e.g. event order) — drop only the explanation. End with AT
MOST 3 examples showing call syntax only (no invalid-input lists, no expected-output table). Examples
illustrate rules ON THEIR OWN; it must NOT show cases where two
or more rules combine, or where the feature meets existing click behavior (subclasses, chained/nested
groups, envvars, multiple/nargs) — those outcomes must follow logically from the stated rules, but
are not given as examples. Do not mention tests or the reference solution.
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
<search></search> and put the whole file in <replace>; remember to import/export it where needed.)
"""

TESTS = """Write the hidden test file for this task. You see ONLY the task statement — test exactly what it
states, nothing more.

TASK STATEMENT:
{instruction}

Rules:
- A NEW pytest file at path {test_path}.
- Test only observable public behavior (CliRunner output/exit codes, return values, exception types
  and messages). Every expected output string or exception message you assert must be copied
  verbatim from the statement.
- At least ONE THIRD of the test FUNCTIONS must check COMBINATIONS: two or more rules interacting, or the
  feature interacting with existing click behavior the statement describes. Their expected outcomes
  must follow unambiguously from the stated rules, and must NOT be copied from the examples table.
  Name them test_r<N>_combo_* using the lowest rule id involved.
  Each combo test exercises a rule through a route other than a direct call (CliRunner, nested or
  chained groups, ctx.invoke/forward, a user subclass).
  Every route/combo test has a comment `# decided by R<N>` naming the statement rule that decides it.
- Every test function name starts with test_r<N>_ for the rule it checks; cover every rule;
  use pytest.mark.parametrize so there are at least 20 test cases in total.
- Must pass under pytest with filterwarnings=error; deterministic; no network or sleeps.
- The file MUST collect on the unmodified repository (where the feature does not exist yet): never import
  new names at module level (no `from click import NewThing`); reference them inside each test or
  helper (e.g. `click.NewThing(...)`) so tests fail by assertion, not by import error.

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

Decide what is wrong and return ONLY the corrected sections (any of <instruction_md>, <edit> blocks
— which must then be the COMPLETE set of gold edits — and <test_file path="...">). Rules: if a test
asserts something beyond the contract, fix the TEST; change the statement only if it omitted text the
contract already contains; fix the gold if it violates the contract. When the diagnostics report LEAKAGE (internals, private
names, which function to edit, trap lists), rewriting the statement to remove it is REQUIRED and
permitted — keep every observable sentence and every R<N> rule; express rules as observable behavior only.
For a search-match failure: recopy every <search> block VERBATIM from the pinned ORIGINAL source shown
in the system context (never anchor on text from a previous generated replacement), and return the
COMPLETE edit set.
"""

FAIRNESS = """Audit a benchmark task for fairness. You see the task statement given to the agent and the hidden
tests. List every behavior a test depends on that the statement does NOT clearly specify (exact
strings, ordering, types, edge cases, state). Be strict but do not invent issues.

STATEMENT:
{instruction}

TESTS:
{tests}

Also list as unstated any LEAKAGE in the statement: explanations of how existing click code works,
names of internal functions to edit, private names, or lists of traps/common mistakes.
For every test named *_combo_*, identify the statement sentence that decides its expected outcome;
if two rules apply and no sentence decides between them, list it as unstated.

Reply with ONLY a ```json block: {{"unstated": ["<issue>", ...]}} (empty list if fully specified).
"""


HARDER = """

REDESIGN (automatic difficulty feedback): a previous task for this card, "{feature}", was RESOLVED
{resolved} by the benchmark agent, so it is retired. Its gold changed {prior_files}. Its full rules:
{rules}
Design a DIFFERENT feature for this card (not a variant of the one above) meeting ABSOLUTE targets:
at least 4 changed src files, at least 5 rules that each state an explicit precedence/interaction
with another rule, and at least 2 rules that change existing behavior while stating exactly what
must stay byte-identical elsewhere. Every rule stays fully stated and observable — no hidden
requirements.
"""

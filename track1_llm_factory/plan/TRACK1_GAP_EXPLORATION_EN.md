# Track 1: Click Capability Gap Exploration

Date: November 14, 2026  
Audience: teammates and the implementation agent  
Status: preliminary exploration. Neither candidate has passed a complete novelty review. No candidate implementation or model benchmark has been completed.

## 1. Executive assessment

The strongest candidate for further investigation is command-collision diagnostics in `CommandCollection`. A second candidate is precise environment-variable provenance.

Both candidates have supporting source inspection and small runtime experiments. However, an API not directly exposing a capability does not establish that the capability is absent from the ecosystem, or that maintainers would accept it upstream. These are potential feature extensions, not confirmed bugs.

This report covers Click only, not the other permitted repositories, Zod and JsonCpp. Exploration did not modify the existing factory, five task packages, or submission archive.

## 2. Evidence and versions

- Factory baseline: Click 8.5.1, commit `cf19179e8e2fd54c601378cec9e0d21bb12b6fb1`.
- Inspected upstream main snapshot: `e38188e9e205005d5af5f9e59df51904c984586a`. This identifies the inspected snapshot, not a guarantee about future upstream state.
- Inspected `src/click/core.py` at baseline and main, plus the main documentation's `AliasedGroup` example in `docs/extending-click.md`.
- Two small experiments used Python 3.11, loading the exported 8.5.1 source through `PYTHONPATH` and executing commands through `CliRunner`.
- Issue, PR, and extension searches were preliminary. A complete semantic comparison has not been performed; neither candidate should receive a novelty PASS yet.

## 3. Candidate A: command-collision diagnostics and an optional policy

### Observed behavior

`CommandCollection` exposes commands from multiple source groups.

- `get_command` checks commands registered directly on the collection, then returns the first match from its sources in order.
- `list_commands` combines names using a set and returns them sorted. Duplicate names do not appear as separate providers.
- Both the baseline and inspected main use this behavior.

Experiment: two source groups each registered a different command named `status`. The implementations printed `FIRST` and `SECOND`, respectively.

```text
collection names: ['status']
selected: FIRST exit: 0
```

This is existing precedence behavior, not a demonstrated defect. Applications can inspect sources themselves; the candidate gap is a direct, consistent built-in interface for collision diagnostics or policy.

### User value and possible extension

Plugin-based CLIs can silently hide one plugin's command behind another because of loading order. A possible extension would preserve first-match behavior by default while offering explicit collision inspection: providers, the selected command, and shadowed alternatives.

Do not freeze API names yet. Decide whether the task should provide diagnostics only or also an opt-in strict mode rejecting ambiguous dispatch. Avoid combining unrelated features simply to increase difficulty.

### Rules requiring specification

- Do commands registered directly on the collection participate in collision checks, or have explicit precedence?
- Does registering the same `Command` object more than once count as a collision?
- Do hidden commands participate?
- How are providers identified and ordered deterministically?
- Does strict checking occur during construction, lookup, or invocation? What happens after `add_source`?
- How do help, shell completion, and resilient parsing behave?
- Are custom source-group `get_command` and `list_commands` overrides respected?

### Validation plan

Feature tests: correct identification of distinct same-name providers; deterministic multi-source reporting; specified strict-mode rejection; normal execution without collisions; object identity, visibility, and dynamic-source rules.

Regression tests: preserve default collection-local precedence and source ordering; retain relevant help, completion, and chain behavior.

Mutations: omit later sources, reverse reporting order, incorrectly count identical objects as conflicts, or omit collection-local commands. Only use mutations that contradict the frozen specification and are genuinely behaviorally distinct.

### Novelty investigation and risks

Inspect baseline, current upstream, relevant merged PRs, extensions, and plugin frameworks. Search terms include `collision`, `shadow`, `duplicate command`, `provider`, and `strict collection`. Compare behavior, not just API names.

Risks: an existing extension may already provide it; a trivial subclass may make the task too easy; strict mode could violate existing compatibility expectations.

Decision: investigate first; not yet approved as a novel task.

## 4. Candidate B: precise environment-variable provenance

### Observed behavior

Click supports fallback environment variables:

```python
@click.option('--port', envvar=['APP_PORT', 'LEGACY_PORT'], default=80)
```

Separate experiment invocations produced:

```text
APP_PORT=8080     -> 8080 source=ENVIRONMENT
LEGACY_PORT=8080  -> 8080 source=ENVIRONMENT
```

`Context.get_parameter_source` reports a source category. The inspected `resolve_envvar_value` returns the selected value. These two interfaces do not directly report which fallback variable supplied that value. This does not mean applications cannot implement their own tracking.

### User value and possible extension

Structured provenance could identify that `port` came from `LEGACY_PORT`, helping configuration debugging and migration away from legacy variables. Avoid exposing variable values by default, especially secrets.

### Rules requiring specification

- Interaction between explicit `envvar`, fallback lists, and `auto_envvar_prefix`.
- Empty or unset variables, and command-line overrides.
- Scope of provenance for prompts, `default_map`, and defaults; avoid unlimited expansion.
- Availability during type conversion and callbacks.
- Hidden parameters, `expose_value=False`, nested contexts, and feature switches sharing a parameter name.
- Capture the actual source during parsing; do not infer it later by rereading a potentially changed environment.

### Validation plan

Feature tests: identify the selected fallback variable; ignore empty candidates correctly; remove stale environment provenance when the command line wins; handle generated prefixes; preserve recorded provenance after later environment changes.

Regression tests: preserve value precedence, type conversion, and existing `get_parameter_source` semantics.

Mutations: always record the first candidate; reread the environment on query; prioritize empty values; retain environment metadata after a command-line override.

### Novelty investigation and risks

Click Extra already offers parameter-source display, so generic source-category reporting is not sufficient novelty. Compare whether existing extensions record the exact variable name and actual resolution provenance, and inspect upstream PRs.

Risks: overlap with mature extensions, complex lifecycle semantics, unnecessary API growth, and accidental value disclosure.

Decision: second priority; novelty remains unconfirmed.

## 5. Warning about the existing abbreviation task

The inspected official documentation includes `AliasedGroup`, which implements exact matching followed by unique prefix matching, errors on multiple matches, and returns the full command name during resolution.

Therefore, basic command-prefix abbreviation alone should not be presented as a confirmed new capability.

Audit the existing task against the example, requirement by requirement: hidden commands, ambiguity ordering, command collections, chaining, normalization, and completion where relevant. Establish which requirements actually add substantive behavior and whether equivalent implementations already exist. Moving the documented example into the library is not strong novelty evidence.

## 6. Candidate priorities

| Candidate | Evidence established | Novelty status | Next action |
| --- | --- | --- | --- |
| Collision diagnostics / policy | Baseline/main source inspection and runtime probe | Unconfirmed | Investigate first and draft a precise specification |
| Precise environment provenance | Interface inspection and runtime probe | Unconfirmed; adjacent extension functionality exists | Compare exact semantics with existing extensions |
| Basic command abbreviation | Official documentation already demonstrates it | Basic behavior is not a strong novelty claim | Audit the existing task's substantive differences |

## 7. Instructions for the implementation agent

1. Preserve the current five tasks and factory version; do not overwrite formal artifacts.
2. Investigate Candidate A first. Produce a capability comparison: existing behavior, proposed additions, source links, inspected commits, and unresolved questions.
3. Review source, documentation, examples, tests, and relevant PRs. Searching only for proposed API names is insufficient.
4. Compare established extensions for drop-in equivalents. Record unavailable network checks as unverified, not passed.
5. If no blocking overlap is found, draft an independently implementable specification covering interfaces, backward-compatible defaults, outputs, edge cases, errors, and interactions.
6. Attach a feature/regression/mutation test plan and expected implementation challenges. Do not derive every test from a fixed reference implementation.
7. Return the investigation and draft for team review. Implement, validate, and benchmark only in the subsequent agreed phase. Do not claim difficulty without actual model results.

Decision criteria: a realistic need, substantive missing capability, clear requirements, verifiability, and manageable scope. Code size, rule count, or intuition that a model might fail are not substitutes.

## 8. Sources

- [Baseline core.py](https://github.com/pallets/click/blob/cf19179e8e2fd54c601378cec9e0d21bb12b6fb1/src/click/core.py)
- [Inspected main core.py](https://github.com/pallets/click/blob/e38188e9e205005d5af5f9e59df51904c984586a/src/click/core.py)
- [Inspected extension documentation](https://github.com/pallets/click/blob/e38188e9e205005d5af5f9e59df51904c984586a/docs/extending-click.md)
- [Click parameter-source documentation](https://click.palletsprojects.com/en/stable/commands-and-groups/)
- [Click Extra source-display implementation](https://kdeldycke.github.io/click-extra/_modules/click_extra/show_params.html)

These sources support observations about existing behavior and adjacent capabilities. They do not prove ecosystem-wide absence. This report does not include a complete PR audit, candidate reference implementation, Harbor candidate validation, or model benchmark.

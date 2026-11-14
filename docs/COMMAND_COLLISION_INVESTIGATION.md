# Command-collision diagnostics: investigation

Status: **candidate extension, investigated only.** Nothing here is implemented. It is not an
established bug report or a confirmed novel feature.

## 1. Commits examined

| Role | Commit | Notes |
|---|---|---|
| Pinned base (V1 `config.BASE_COMMIT`) | `cf19179e8e2fd54c601378cec9e0d21bb12b6fb1` | tag `8.5.1` |
| Upstream `main` at investigation time | `e38188e9e205005d5af5f9e59df51904c984586a` | 2026-11-12, "Drop support for Python 3.10 (#3920)"; 25 commits after base |

`CommandCollection` (class body through `list_commands`) is **byte-identical** at both commits
(`base: src/click/core.py:2141-2196`, `main: src/click/core.py:2164-…`). None of the 25 commits
after base touches its lookup logic.

## 2. Verified behaviour

Source at base (`src/click/core.py`):

```python
def get_command(self, ctx, cmd_name):
    rv = super().get_command(ctx, cmd_name)        # collection-local (Group.commands)
    if rv is not None:
        return rv
    for source in self.sources:                    # then each source, in list order
        rv = source.get_command(ctx, cmd_name)
        if rv is not None:
            if self.chain:
                _check_nested_chain(self, cmd_name, rv)
            return rv                              # first match wins
    return None

def list_commands(self, ctx):
    rv = set(super().list_commands(ctx))
    for source in self.sources:
        rv.update(source.list_commands(ctx))
    return sorted(rv)                              # names only, de-duplicated
```

All four observations in the brief hold:

1. `get_command` checks collection-local commands, then sources in order.
2. The first match wins.
3. `list_commands` de-duplicates names.
4. Neither interface reports the providers of a name or the alternatives that were shadowed.

### Runnable reproduction

`track1_freestyle/evidence_v2/command_collision/repro_command_collision.py` uses only public Click
API. It was run against both commits with Python 3.11.13 and `-W error`. Both logs are identical
apart from the import path (`repro_base.log`, `repro_main.log`):

```bash
git clone https://github.com/pallets/click.git && cd click
git worktree add ../wt_base cf19179e8e2fd54c601378cec9e0d21bb12b6fb1
git worktree add ../wt_main e38188e9e205005d5af5f9e59df51904c984586a
PYTHONPATH=../wt_base/src python -W error <repo>/track1_freestyle/evidence_v2/command_collision/repro_command_collision.py
PYTHONPATH=../wt_main/src python -W error <same script>
```

| # | Scenario | Observed (base and main) |
|---|---|---|
| 1 | sources `[A, B]` both define `deploy` | `get_command` → A's; invoking runs A; `list_commands` → `['deploy', 'logs', 'status']` (one `deploy`) |
| 2 | swap to `[B, A]` | B's `deploy` wins — order alone decides |
| 3 | collection-local `deploy` added | local wins over both sources |
| 4 | one command object registered in both A and B | resolves to that object; listed once. Public API cannot tell this apart from case 1 without identity checks |
| 5 | A has **hidden** `logs`, B has visible `logs` | `get_command` → hidden A `logs`; `logs` is **absent from `--help`**; invoking `logs` runs the hidden one |
| 5b | completion of `l` in case 5 | `[]` — B's visible `logs` is not offered |
| 6 | `add_source(B)` after construction | lookup changes immediately; there is no caching |
| 6b | constructor `sources=` list | a non-empty list is aliased (later `append` is seen); an empty list is replaced by a new list (`sources or []`), so appending to the caller's empty list is not seen |
| 7 | source is a custom `Group` whose `list_commands` returns `ghost` but `get_command("ghost")` is `None` | the override is consulted; `ghost` is listed by `list_commands` but resolves to `None` and is omitted from help |
| 8 | `chain=True`, sources `[A, B2]`, B2's `deploy` is a `Group` | the shadowed group is never checked; with `[B2, A]` the lookup raises `RuntimeError` (nested group in chain mode). The chain check applies only to the winner |
| 9 | unknown `deplo` | `No such command 'deplo'.` with no suggestion: `NoSuchCommand(possibilities=self.commands)` only sees collection-local names |
| 10 | `to_info_dict` | one entry per name (the winner's) |

Cases 5/5b are the clearest user-visible consequence. A visible command disappears from help and
completion because an earlier, hidden command with the same name shadows it. This is inherent in
first-match-wins and is not a separate bug in help rendering: `format_commands` and completion both
call `get_command` and then skip hidden results. Case 9 is out of scope; it is noted only because it
appeared during the investigation.

### Upstream test and documentation coverage

- `git grep CommandCollection` at both commits finds only `src/click/core.py`,
  `src/click/__init__.py` (export) and one `.. autoclass:: CommandCollection` line in `docs/api.md`.
- `git log --all -S CommandCollection -- tests` returns **no commits**: upstream has never had a
  test that names `CommandCollection`.
- Prose documentation of `CommandCollection` was removed from `docs/commands.rst` in `238ee07`
  (2023-08-19, "remove mentions of deprecated base classes"). Only the API autodoc remains.

Consequence for a task: no existing upstream test pins `CommandCollection`'s current precedence.
P2P protection has to come from `Group` lookup/help/completion/chain tests (see the test plan).

## 3. Novelty investigation

Search performed on 2026-11-14 with an authenticated `gh` CLI, the GitHub REST API, pip downloads
of released wheels, and one general web search. Queries were semantic (collision, shadow,
duplicate, conflict, overwrite, override, precedence, hidden, plugin, merge groups, sources), not a
proposed API name.

- pallets/click issues: `CommandCollection`, `CommandCollection duplicate|order|sources|precedence|hidden`,
  `duplicate command name`, `command name collision`, `command shadow`, `shadowed command`,
  `conflicting command`, `same command name`, `add_command overwrite`, `add_command already exists`,
  `command already registered`, `warn duplicate command`, `duplicate`, `merge multiple groups`,
  `plugin conflict`, `override subcommand`, `overriding command`.
- pallets/click PRs: `CommandCollection`, `sources`, `duplicate command`, `command name conflict`,
  `shadow`, `override command`, `overwrite command`, `merge groups`, `plugin commands`,
  `add_command warning`, `list_commands duplicate`, `get_command order`; plus the full list of
  open PRs (10 at search time).
- GitHub code search (Python): `CommandCollection shadowed`, `… duplicate command`, `… conflict`.
  All empty. A control query `CommandCollection sources` returned exactly one hit, so the API worked
  but its index coverage is thin.
- Released packages, source-grepped: cloup 4.0.0, click-extra 10.2.0, rich-click 1.9.9,
  click-repl 0.4.1, click-plugins 1.1.1.2, click-aliases 1.0.7, click-default-group 1.2.4,
  click-didyoumean 0.3.1, Typer 0.29.1, Flask 3.1.3, stevedore 5.10.0, pluggy 1.7.0.
- Stdlib: `argparse` duplicate sub-parser behaviour, executed on Python 3.8.6 and 3.11.13.
- One search request was rate-limited (HTTP 403) and repeated successfully after a pause. A further
  `two groups same command` issue query was also rate-limited the first time and returned no
  results on retry.

### Comparison

| Source | Existing capability | Overlap with candidate | Substantive difference | Evidence / uncertainty |
|---|---|---|---|---|
| Click `CommandCollection` (base = main) | first-match lookup; name-only de-duplicated listing | the behaviour the candidate would inspect | no provider listing, no collision report, no policy | source read + reproduction at both SHAs (verified) |
| Click upstream tests/docs | none for `CommandCollection` | — | — | `git grep`, `git log --all -S` (verified at both SHAs) |
| [pallets/click#2397](https://github.com/pallets/click/pull/2397) (merged 2024-11-03; in base) | `UserWarning` when one command has duplicate **parameter** names | same "warn about name conflicts" idea | parameters on one command, not commands across groups; already at base (`core.py:1120`) | merged code, verified in base source |
| [pallets/click#1170](https://github.com/pallets/click/issues/1170) (closed 2019) | asked for `add_command` on `CommandCollection` | collection-local commands | no collision handling; superseded by 8.2 (`CommandCollection` became a `Group`) | issue text |
| [pallets/click#2590](https://github.com/pallets/click/issues/2590) (closed 2023) | maintainer discussion that made `CommandCollection` a `Group` subclass | discusses semantics of flattening | **not a feature.** The maintainer is "not entirely convinced" flattening should be supported because it "adds ambiguity and indirection". This is a realism and acceptance risk, not a novelty blocker | issue text (web search + REST) |
| pallets/click open PRs (10) | none about command lookup | — | — | `gh pr list --state open` (verified) |
| Closed "AI spam/junk" PRs matching "duplicate" (#3542, #3555, #3564) | unrelated (test warnings, editor flags) | none | — | bodies read via REST |
| cloup 4.0.0 `Section.add_command` | raises `command "<name>" already exists` | strict duplicate detection | within one **help section** of one group; cloup re-exports Click's `CommandCollection` unchanged | released source read |
| click-extra 10.2.0 | lazy subcommands; replaces auto-injected commands without "duplicate error" | duplicate handling | single group, injected-vs-user command; no cross-source report | released source read |
| click-repl 0.4.1 | builds its own name→command map over `group.sources` | re-implements provider enumeration | iterates sources into a dict, so the **last** source wins (opposite of Click) and collection-local commands are ignored. A downstream symptom of the missing API | released source read; not executed |
| rich-click 1.9.9 `RichCommandCollection` | styling subclass | none | no lookup change. Its `--suppress-warnings` flag concerns conflicting `rich-click` CLI entry points | released source read |
| Flask 3.1.3 `FlaskGroup` | built-in/plugin commands first, then app commands; set-union listing | same first-wins + de-dup pattern | no diagnostics, no policy | released source read |
| Typer 0.29.1, click-plugins, click-aliases, click-default-group, click-didyoumean | no cross-group collision features found | — | — | grep of released wheels for collision/duplicate/conflict terms; absence is grep-level, not exhaustive |
| stevedore 5.10.0 | `conflict_resolver` for entry points sharing a name: `error_on_conflict` raises `MultipleMatches`, `ignore_conflicts` warns and takes the last, custom callables | closest prior art for a collision **policy** | operates on entry-point extensions, not Click groups; default is to warn | released source + tests read |
| pluggy 1.7.0 | `ValueError` on registering a duplicate plugin name | strict duplicate registration | plugin manager, not command lookup | released source read |
| Python `argparse` (3.11+) | `ArgumentError: conflicting subparser` for a duplicate sub-command name in one parser (3.8 accepted it) | strict duplicate detection for sub-commands | single parser at registration time; no multi-source precedence | executed on 3.8.6 and 3.11.13 |
| Team-internal recheck at PR #2 head `8394b349` (2026-11-14, detached worktree) | 36 design records; new families since `934bf44c`: response-file completion, atomic output, lazy defaults, plus more ledger/help/argv runs | none. 11 designs mention `CommandCollection`, each only as "must also work with `CommandCollection` sources". The one "collision" hit is about dotted config keys | no command-lookup diagnostics | every `design.json` grepped; matched lines read (verified) |
| Team-internal: [PR #2](https://github.com/tianluoboding/team4_track1/pull/2) `track1_llm_factory` (open, head `934bf44c`) | 15 design records across five families: response-file argv expansion, help sections, config value source (`ParameterSource.CONFIG`), invocation ledger, types | none. The `sources` family is about parameter **value** sources, not command sources. `CommandCollection` appears only in the two help-sections designs (4 mentions). They say help sections work with its merged `list_commands`, and that a collection uses its own section overrides and order rather than its sources'. That is help-layout compatibility, not lookup or collision behaviour | different features; no command-lookup diagnostics. A future help-sections task and this candidate would both touch `CommandCollection` help, so they should not be packaged against conflicting assumptions | every `design.json` in the PR read via the GitHub API at the head SHA and grepped for `CommandCollection`, `get_command`, `list_commands`, `add_source`, `shadow`; matched lines read (verified) |
| CKAN [#5329](https://github.com/ckan/ckan/pull/5329), signet commit `5a82b3d`, fastapi-cli [#421](https://github.com/fastapi/fastapi-cli/pull/421) (open) | application-level detection of duplicate plugin command names at entry-point load time (error / `duplicate_name` status / warning) | same user need | app-specific loaders, not a Click API; fastapi-cli is an unmerged proposal | web search results only; not inspected beyond the summaries |

### Novelty status

- **Upstream Click (source, tests, docs, open and merged PRs searched): no equivalent found.**
  Verified at both SHAs for source/tests/docs. The PR/issue search is keyword-based over titles and
  bodies, so it cannot guarantee that no discussion exists.
- **Released Click extensions checked: no drop-in equivalent found.** Twelve packages were
  source-grepped. Popularity was not measured, and other extensions exist.
- **Ecosystem-wide: unverified.** GitHub code search coverage is thin (the control query found one
  hit). The general web search returned summaries only. Treat this as *incomplete*, not as a PASS.
- **Concept is not new.** Duplicate-name detection and conflict policies are well established
  (argparse, stevedore, pluggy, cloup sections, several applications). A Click task based on this
  is a port of a known pattern to `CommandCollection`. That is acceptable under the brief ("isn't a
  drop-in from a well-known library") but should not be described as an original idea.
- **Triviality risk.** The core of diagnostics is a loop over `[self] + self.sources`, a few lines of
  userland code (the web search's own synthesis shows one). The candidate's substance is in getting
  the edge cases right: local precedence, identity versus distinct objects, hidden winners,
  listed-but-unresolvable names, custom `get_command`, no chain side effects, and no caching. The
  click-repl case shows that downstream code does get the order wrong. Whether this is hard enough
  for a model is unknown and must not be claimed without a benchmark.
- **Reported calibration point (not independently verified).** PR #2 reports that Claude Haiku
  (terminus-2, k=3) solved all five V1 tasks 3/3 (15/15 rollouts; see
  `docs/V2_VALIDATION_HARDENING.md` section 2a). Those tasks are rule-dense specs of similar size
  that change one Click area each. A diagnostics-only `CommandCollection` task is in the same size
  class, so if the report holds, the prior expectation is that it would also be easy. This makes
  the triviality risk concrete. Before investing in packaging, the test plan's gold prototype
  should be benchmarked cheaply (k=3) or the scope reconsidered with the team. It is not a reason
  to pad the spec with artificial rules.

**Decision:** no drop-in equivalent or other blocking novelty issue was found, so a specification
draft is justified. Two risks carry forward and are not resolved by more searching: the
ecosystem-wide search is incomplete, and upstream maintainers have signalled scepticism about
`CommandCollection`.

## 4. Raw evidence

| File | Content |
|---|---|
| `track1_freestyle/evidence_v2/command_collision/repro_command_collision.py` | reproduction script |
| `…/repro_base.log`, `…/repro_main.log` | outputs at the two SHAs |
| `…/p2p_candidates_at_base.log` | 23 candidate existing tests pass at base and 1 is xfail (local macOS, not the task image) |

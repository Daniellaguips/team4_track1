# Benchmark status (current, 2026-11-14)

Each fact below is labelled by provenance: **historical** (recorded earlier, left unchanged),
**teammate-reported** (claimed in PR #2, not re-run by me), **independently verified** (checked
by me on branch `v2/validation-hardening-collision-spec`), or **blocked**.

## Summary

| Tasks | Benchmark | resolve@3 | Provenance |
|---|---|---|---|
| Five V1 tasks (`track1_freestyle/generated_tasks/`) | terminus-2 + Haiku via OpenRouter, k=3, Docker | 3/3 on every task (15/15 rollouts reward 1.0) | **teammate-reported** in [PR #2](https://github.com/tianluoboding/team4_track1/pull/2); partly verified (see below) |
| V2 collision task `pallets__click-command-collection-providers-55a649` | none | — | **blocked**: no organizer credential, no coordinated spending allowance |

The statement "V1 difficulty is unknown because no benchmark ran" is **outdated**. If the
PR #2 report holds, the V1 tasks are valid but **trivial for the benchmark model** (3/3 is
"trivial; redesign harder" in `benchmark_guide.md`).

## Historical records (unchanged)

- `track1_freestyle/bench/benchmark_status.json` and the V1 README say the benchmark was
  **blocked on the original host** (`ANTHROPIC_API_KEY` not set) and that validation ran on rootless
  Podman. Those records are accurate for that host and time and are not edited.

## V1 benchmark reported in PR #2

PR #2 is open and not merged. I inspected it at head `8394b349fe1d1487906e3fb3e38d925a1aa50d89`
in a separate detached worktree (`git fetch origin refs/pull/2/head`), without merging it into
this branch. The benchmark file and the five packages are unchanged between the earlier head
`934bf44c` and `8394b34`.

Raw evidence present in the PR: `track1_submission/team4_Track1/bench/benchmark_results_openrouter.json`
(a hand-assembled summary, one row per rollout). Snapshot with sha256:
`track1_freestyle/evidence_v2/external/pr2/`.

| Item asked for | What the PR contains | Status |
|---|---|---|
| Actual model and agent | `agent: terminus-2`, `model: openrouter/anthropic/claude-haiku-5.5`, and per rollout `model_seen: anthropic/claude-haiku-5.5` | **reported**. The guide's required id is `anthropic/claude-haiku-5-5`, and it says terminus-2 also runs OpenRouter models. That the OpenRouter slug is the same model is plausible, but it cannot be checked without each rollout's `result.json` `agent_info.model_info`, which the PR does not include |
| Per-rollout reward and F2P/P2P | 15 rows, all `reward 1.0`, F2P and P2P full (e.g. duration `16/16`, `37/37`) | **reported**. Verified: the F2P/P2P totals per task equal the lengths of the local `fail_to_pass.json`/`pass_to_pass.json` (16/37, 12/21, 10/37, 12/48, 12/39), and the 15 trial ids are distinct |
| Completion / infrastructure failures | the README says "0 infrastructure failures"; the JSON has no field for excluded, retried or errored rollouts | **reported only**. Nothing in the raw file can confirm or refute it |
| Task identity / checksum | per-rollout `task_checksum` is not in the PR | **partly verified**: all 60 package files at PR head `8394b34` have the same git blob hashes as the local V1 packages (`evidence_v2/external/pr2/generated_tasks_blob_compare.txt`), so the benchmark was run on these packages if the PR's packages are what was run. For later comparison, Harbor 0.25.0 computes `task_checksum` `bbc4130f709c0b2e9b566f08f7c70b457c068e3e39c366b4d808997d1a7c7f73` for the duration task (my self-check, `evidence_v2/integration/organizer_selfcheck_duration/`) |
| Recorded costs | `cost_usd` per rollout; sum **$0.1662** (min $0.0066, max $0.0243) | **reported**; the arithmetic was verified |
| Trajectories | none in the PR or its archives (`runs.tar.gz` contains only oracle/nop self-check trials) | **unavailable**. The guide expects `trajectory/<iid>/<model>/rollout_N/` |
| Docker validation | `evidence/docker/selfcheck_docker.txt`: 5/5 `ALL SOUND` | **reported**. Independently re-run by me on one V1 task under Docker (below) |

Team spend recorded in PR #2 (reported, not verified): V1 benchmark about $0.17; LLM-factory
generation $31.42 from call logs (`track1_llm_factory/evidence/YIELD_REPORT.md`). The LLM factory's
own Haiku benchmark spend is not totalled there.

## Independently verified on this branch (no model calls)

- Docker validation of the hardened gates and of the organizer self-check on one V1 task
  (`docs/V2_CONTAINER_INTEGRATION.md`).
- Generation and full validation of the V2 collision task (`docs/COLLISION_TASK_REPORT.md`).

## Collision task: blocked

`track1_freestyle/evidence_v2/collision_task/benchmark_status.json`:

- `ANTHROPIC_API_KEY` and `OPENROUTER_API_KEY` are not set in this environment, and no organizer
  credential was provided for this assignment.
- No spending allowance for this task was coordinated with the team.
- An `OPENAI_API_KEY` exists in the shell environment. It was **not** used: it is not an
  organizer-authorized benchmark credential and not the required model provider. No personal
  subscription or key was used. Model calls: 0. Cost: $0.

When an organizer credential and an allowance are available, run on the frozen package
(Harbor `task_checksum` `76aa9a95bc79a4c4300bb677af3d592443465112fa019aceac08ca6544573d55`):

```bash
cd track1_freestyle
export OPENROUTER_API_KEY=...   # organizer key, environment only
harbor run -p generated_tasks_v2/pallets__click-command-collection-providers-55a649 \
  -a terminus-2 -m openrouter/anthropic/claude-haiku-5.5 -k 3 -n 3 -o jobs_v2/collisions --no-delete -y
```

Then confirm from every rollout's `result.json` that `agent_info.model_info` is the required model
and that `task_checksum` equals the value above. Count reward `null`, API errors and truncated
responses as infrastructure failures (re-run them; report them separately), and count agent
time-limit exhaustion as a model miss. Report resolve@3 = resolved / 3, and keep all three
trajectories. If tests change after seeing model output, that is a new task version and needs a
full re-validation.

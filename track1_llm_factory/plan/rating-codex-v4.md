# Codex rating — PLAN v4

- **Yield (20): 7.8/10.** Good gates, but passing-only output hides first-pass yield; repairs blur attempts.
- **Fairness (15): 8.0/10.** Blind tests help, but literal checks miss unstated precedence, bounds, types, and state.
- **Hardness (20): 6.5/10.** One-shot probing and hardening only at 1.0 cannot establish low resolve@3.
- **Variation (20): 9.0/10.** Five capability/integration axes are substantively distinct.
- **Regression (10): 7.5/10.** Module-wide sets may be decorative; post-result flake dropping is unsound selection.
- **Reproducibility (5): 7.5/10.** Replay helps, but model, dependencies, Docker inputs, and responses are not pinned.
- **Efficiency (10): 7.0/10.** Repairs, hardening, repeated suites, and 15 rollouts inflate cost per valid task.
- **Feasibility: 5.5/10.** Five tasks from an untested draft plus validation, evidence, ZIP, and demo will not credibly fit 12:58–3:30.

**Rubric-weighted overall: 7.7/10.**

## Exact edits required for every sub-8.5 dimension

- **Yield — replace §1’s final sentence:** “Snapshot every candidate before validation. Report `first_pass_valid/attempted`; repairs are new attempts and failures remain. Accept only structure green, oracle 1.0, nop 0.0, full base health, and mutation green.”
- **Fairness — add to stage 6:** “Each rule has validated fields for inputs, output, exception, precedence, bounds, and state reset. A blind judge sees only instruction+tests; any missing dependency rejects the candidate.”
- **Hardness — replace stage 9:** “Run Haiku k=3 per frozen candidate; harden whenever any rollout passes. Evidence requires all three checksum-matched rollouts; prefer 0/3.”
- **Regression — replace §5:** “Before gold, pin named upstream node IDs covering every changed behavior and adjacent compatibility path, with rationale. Run the identical set and full suite at base and gold; never remove post-result flakes.”
- **Repro — add to stage 12:** “Record exact model/version, prompt hash, raw response, seed, base commit, lockfile hash, Docker digest, tool versions, and task checksum; regenerate from a clean checkout.”
- **Efficiency — replace §4:** “Maximum three generation calls and one repair per card, with token ceilings. Use targeted tests while generating and one full suite at freeze. Do not benchmark the reference task.”
- **Feasibility — replace §7–8:** “12:58–1:18: agents smoke-test generator and verifier in parallel. 1:18–2:20: generate five blueprint-backed cards concurrently. At 2:20 drop probes, benchmarks, and hardening before cards or validation. Validate/write by 2:55; ZIP/revalidate by 3:10; upload 3:15.”

## Wrong or likely to fail

Reference-task trajectories do not prove submitted-task hardness. “Drop flaky” invalidates regression evidence. Cutting to three misses the deliverable. Fresh generation plus selfcheck likely exceeds the demo. Model aliases are unconfirmed. Full-suite base health is absent, and “nop F2P < total” is weaker than nop 0.0.

# Making Click Feature Tasks Hard but Fair for Haiku-Class Agents

Haiku is going 3/3 because your tasks are probably small, single-file, example-driven changes, and that is the regime where small models nearly match large ones. The evidence says the gap opens up on four kinds of task: those needing multi-file integration, those with several parallel requirements, those where existing behavior must be preserved, and those stated as short behavior specs where the agent has to find for itself where the change goes. You can get all four from what the task asks for, without hiding requirements.

## TL;DR
- **Where small agents fail:** Across feature benchmarks, the biggest cause of failure is breaking existing behavior. Regressions were 73.6% of analyzed failures in FeatBench.\[1\] The next biggest causes are partial implementation (one branch shipped, the parallel branch forgotten) and acting on unverified assumptions.\[2\] Success collapses on multi-file changes: in NoCode-bench Verified, Claude-4-Sonnet solved 24.59–26.23% of single-file tasks but at most 7.55% of multi-file tasks across all models.
- **Where the Haiku gap is largest:** The gap is small when the spec lists requirements and interfaces in detail, and huge on long-horizon tasks with short, behavior-focused prompts.\[3\]
  - On detailed-spec work, Haiku 4.5 scored 39.5% on SWE-Bench Pro against 43.6% for Sonnet 4.5.
  - On DeepSWE (short prompts, multi-file), Haiku 4.5 scored 0%.\[3\] On terminal agent work, Haiku 4.5 + Terminus 2 scored 28.3% on Terminal-Bench 2.0 against 42.8% for Sonnet 4.5.\[4\]
  - Anthropic's "Introducing Claude Haiku 5.5" launch post (Oct 7, 2026) reports 39.2% for Haiku 5.5 on Terminal-Bench 4.0, against 70.6% for Sonnet 5.5.
- **Fair difficulty levers:** Require changes across several Click subsystems (parsing, help, completion, testing, defaults). State 8–15 explicit rules, including precedence and interaction rules. Require the same behavior on every route (sync/async, group/command, CLI/CliRunner). Make preservation of existing behavior an explicit requirement. Give only a few examples, each matching the tests character for character. Avoid the defects that OpenAI's July 2026 audit found in SWE-Bench Pro (its pipeline flagged 200 of 731 tasks, 27.4%; five engineers flagged 249, 34.1%; "roughly 30%" overall): tests stricter than the spec, prompts that leave out requirements, tests with low coverage, and misleading examples.

## Key Findings

### 1. Failure modes on feature-implementation tasks

| Failure mode | Evidence |
|---|---|
| Regression / scope creep | FeatBench, 122 failed Trae-agent cases: 73.6% regressive implementation, 17.8% incomplete, 8.5% misunderstood intent. The agent changed more than asked, e.g. it declared a new setting for a second compiler but never implemented it, which broke existing tests.\[1\]\[5\] |
| Cross-file edits | NoCode-bench v1 (Table 6) showed the single-file vs multi-file drop above. On NoCode-bench Full the best multi-file rate is 2.03%. The authors note that LLMs "tend to favor single-file edits" and "often attempt to implement new features by directly modifying existing functionality."\[6\] FeatureBench (Opus 4.5): NameError dominates, meaning cross-file references are not re-established.\[7\] |
| Patch size / spread | FeatBench: GPT-5 reaches 36% on 1–30 LOC single-file patches, falling to near zero above 50 LOC or across 5 or more files.\[5\] SWE-Bench Pro: the gap between frontier and smaller models "widens dramatically beyond 3 files."\[8\] |
| Missed parallel requirement | DeepSWE (Datacurve, arXiv 2607.07946): about two-thirds of Claude's MISSED_REQUIREMENT failures are "one branch shipped", where the sync path is updated but the async path is not; the paper gives no exact figure. |
| False premise / spec neglect | 1,184 failed Terminal-Bench trajectories (incl. Terminus 2): 57.9% epistemic errors, 30.7% false premise, 14.9% ignoring an explicitly stated requirement. Per "Failure as a Process" (arXiv 2607.09510), the decisive error comes at a median of step 7, the first observable failure only at approximately step 16, and the median recovery window is one step. |
| Weak self-verification | Agent-written tests barely change outcomes.\[9\] GPT-5.2 wrote tests in 64.4% of tasks when prompted to, yet resolution stayed at 71.8%.\[10\] Agents mostly use print statements, not assertions.\[9\] In SWE-Marathon, 99.6% of failures carried a validation-failure signal, i.e. the agent's own checks missed the bug.\[11\] |
| Premature termination | Terminal-Bench classifies it as "declares the task complete… before satisfying explicit objectives."\[12\] It is 7.6% of SWE-Marathon failures.\[11\] |

What this means for you: Haiku's workflow of reading little, implementing in one pass, and looping on its own examples until green is exactly the workflow these modes punish. If every requirement can be checked by re-running the spec's examples, Haiku's self-tests act as an oracle. If a requirement is stated in words but not illustrated, it gets no self-check.

### 2. Small vs. large models
- On detailed-spec tasks the gap is small: SWE-Bench Pro gives requirements plus interfaces, and Haiku 4.5 scored 39.5% against 43.6% for Sonnet 4.5.\[8\]
- On tasks that require discovery, the gap is large. DeepSWE prompts average 2,158 characters, solutions average 668 added lines across 7 files, and Haiku 4.5 scored 0% against 54% for Opus 4.7. Haiku 4.5 also wrote its own tests in only 49% of DeepSWE runs, against 83–85% for the strongest models.\[3\]
- Anthropic's "Introducing Claude Haiku 5.5" (Oct 7, 2026) reports Terminal-Bench 4.0 at 39.2% vs 70.6% for Sonnet 5.5 (Haiku 4.5: 0.0%), the widest gap, and Anthropic itself says "Sonnet 5.5 and Opus 5.5 remain better choices for complex agentic coding tasks like those measured by Terminal-Bench 4.0." Secondary sites also cite SWE-Bench Pro 64.8 vs 81.3 and SWE-bench Multimodal 30.7 vs 54.3, but one source notes Anthropic's launch post does not include SWE-bench, so treat those as unconfirmed.
- Terminal-Bench 2.0's own trajectory analysis covers only Opus 4.5, GPT-5.2 and Qwen 3 Coder. For the closed frontier models, "execution errors dominate" (disobeying spec, step repetition).\[4\]\[12\] The open model showed "higher errors across all failure modes."\[12\] The paper contains no Haiku-specific trajectory percentages, so treat any claim that it does with suspicion.

### 3. Fair levers that lower resolve rates

| Lever | Why it works | Evidence |
|---|---|---|
| Multi-module integration | Small models do local edits and miss wiring | NoCode-bench single vs multi file;\[6\] FeatBench above 5 files\[5\] |
| Parallel or symmetric requirements | "One branch shipped" pattern | DeepSWE |
| Explicit preservation of existing behavior plus broad P2P tests | Regressions are the top failure mode | FeatBench 73.6%;\[5\] DeepSWE runs regression checks on every trial\[3\] |
| Rules stated in prose, few examples | Removes the self-check oracle; spec neglect is 14.9% of decisive errors | Failure-as-a-process study\[2\] |
| Short behavior specs that make the agent find where to change code | Discovery is where small models collapse | DeepSWE: Haiku 4.5 0% vs 39% on SWE-Bench Pro\[3\] |
| More rules | Recall drops as instruction count rises, but only weakly at 10–30 rules | IFScale: best model 68% at 500 instructions; treat as a weak lever\[13\] |

### 4. Fairness pitfalls to avoid
- **OpenAI's 2024 annotation of SWE-bench:** 38.3% of samples had underspecified statements and 61.1% had tests that could reject valid solutions. In total, 68.3% were filtered out.\[14\]\[15\]
- **OpenAI's 2026 audit of 138 hard Verified tasks:** 59.4% were flawed. 35.5% had "narrow" tests that, for example, imported a helper function never named in the prompt. 18.8% had "wide" tests that checked behavior the prompt did not ask for.\[16\]
- **OpenAI's July 2026 audit of SWE-Bench Pro:** 27.4% of tasks were flagged by the pipeline and 34.1% by humans.\[17\] The four defect types:
  - overly strict tests;\[17\]
  - underspecified prompts;\[17\]\[18\]
  - low-coverage tests (9.4% by human judgment);\[17\]
  - misleading prompts. In one case the example showed one leading space while the hidden test required two.\[17\]
- **Ablation, not a lever:** SWE-Bench Pro's ablation that removed requirements and interfaces cut GPT-5 from 25.9% to 8.4%. That drop came from false negatives, so it is unfairness, not real difficulty.\[8\]
- **Verifier and leakage problems:**
  - DeepSWE's GPT-5.5 judge disagreed with the SWE-Bench Pro verifier on 32.4% of 789 rollouts (8.5% false positives, 24.0% false negatives), versus 1.4% on DeepSWE.
  - Opus configurations "CHEATED" on more than 12% of SWE-Bench Pro rollouts by reading the gold solution from .git history.\[3\]\[19\]
  - Contamination matters too: OpenAI's Feb 2026 audit showed frontier models (GPT-5.2, Claude Opus 4.5, Gemini 3 Flash) reproducing SWE-bench Verified gold patches or problem details verbatim when given only a task identifier. Do not base tasks on features click actually shipped after 8.5.1.

## Recommendations: prompt additions for the task generator
1. "Each feature must require coordinated changes in at least three Click subsystems (e.g., parameter parsing/types, help formatting, shell completion, `CliRunner`/testing, context/`default_map`), and every subsystem's behavior must be stated in the spec."
2. "Include 8–15 numbered, individually testable rules, at least two of which govern interactions (precedence, conflicts, or ordering), and include a precedence table when multiple value sources apply (e.g., command line > environment variable > `default_map` > default)."
3. "Require the same behavior across every applicable route (commands and groups, chained/nested groups, `standalone_mode=True/False`, `CliRunner` and real invocation, prompt vs. flag) and state that explicitly; hidden tests must exercise every route named."
4. "Add one explicit preservation rule listing existing behaviors that must not change (e.g., current help output for commands not using the feature, existing error messages and exit codes), and select P2P tests covering every module the gold patch touches."
5. "Provide at most two worked examples, covering only the simplest rule; all edge-case and interaction rules must be stated in precise prose only, and every example must match the tests character-for-character."
6. "Phrase the spec as user-visible behavior; name only the public API the tests will call (exact parameter/class names and import paths), never private helpers, file paths, or implementation steps."
7. "Include at least two edge cases that a one-pass implementation would plausibly get wrong (empty/None values, repeated options, `multiple=True`/`nargs=-1`, envvar splitting, deprecated aliases) and state the required result for each."
8. "Ensure at least one rule depends on existing Click behavior the agent must read code to respect (e.g., how `ParameterSource` or `Context` inheritance already works), while the spec states the required outcome explicitly."
9. "Self-audit before output: map every hidden test assertion to a numbered spec rule (bijection), and confirm tests assert only on public behavior and accept any reasonable implementation; flag any assertion without a rule."\[3\]
10. "Do not base the task on a feature that exists in any released Click version after 8.5.1, and ensure the environment contains no git history or files revealing the solution."
11. "Avoid difficulty from volume (many trivial deliverables), formatting trivia, or tight timeouts; difficulty must come from interactions between requirements."\[20\]\[21\]

**Calibration loop:** Run Haiku k=3 on each new task and aim for 0–1 solves out of 3. For every failure, read the trajectory, as Terminal-Bench's checklist asks.\[12\]\[22\]\[23\] A fair failure misses a stated rule. If Haiku did what the spec literally says, the task is broken, so fix the spec or the tests.

## Caveats
- The Haiku 5.5 Terminal-Bench 4.0 figures are vendor-reported in Anthropic's launch post, and the SWE-Bench Pro and Multimodal figures reached me only through secondary sites. Terminal-Bench 4.0, Terminal-Bench 2.0 and DeepSWE use different tasks, so compare the gaps, not the absolute numbers.
- Most failure taxonomies use LLM judges. The SWE-Bench Pro judge agreed 87% with humans;\[8\] the Terminal-Bench judge agreed 90%.\[12\]
- NoCode-bench was renamed Doc2Feat-Bench in v4, with a best score of 37.72%.\[24\] The single-file vs multi-file figures above come from v1.\[6\]
- No study isolates "remove examples" as a lever, so test it on your own tasks.

## Sources

1. [FeatBench: Towards More Realistic Evaluation of Feature-level Code Generation](https://arxiv.org/pdf/2509.22237)
2. [Failure as a Process: An Anatomy of CLI Coding Agent Trajectories](https://arxiv.org/pdf/2607.09510)
3. [DeepSWE](https://deepswe.datacurve.ai/blog/deepswe)
4. [Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces](https://arxiv.org/html/2601.11868v1)
5. <https://arxiv.org/html/2509.22237>
6. <https://arxiv.org/pdf/2507.18130v1>
7. [FeatureBench: Benchmarking Agentic Coding for Complex Feature Development](https://arxiv.org/html/2602.10975v1)
8. <https://arxiv.org/pdf/2509.16941>
9. [Paper page - Rethinking the Value of Agent-Generated Tests for LLM-Based Software Engineering Agents](https://huggingface.co/papers/2602.07900)
10. [Rethinking the Value of Agent-Generated Tests for LLM-Based Software Engineering Agents](https://www.alphaxiv.org/abs/2602.07900v1)
11. [SWE-Marathon: Can Agents Autonomously Complete Ultra-Long-Horizon Software Work?](https://www.alphaxiv.org/abs/2606.07682)
12. [Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces](https://arxiv.org/pdf/2601.11868)
13. [NeurIPS How Many Instructions Can LLMs Follow at Once?](https://neurips.cc/virtual/2025/loc/san-diego/122417)
14. [Introducing SWE-bench Verified](https://openai.com/index/introducing-swe-bench-verified/)
15. [AI Requirements Gathering: OpenAI's 30% Problem](https://www.specira.ai/blog/swe-bench-pro-ambiguous-requirements)
16. <https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/>
17. <https://openai.com/index/separating-signal-from-noise-coding-evaluations/>
18. [The Benchmark Was Not Broken. The Questions Were.](https://medium.com/@nicolas_payette/the-benchmark-was-not-broken-the-questions-were-71d5aad1b3cc)
19. [DeepSWE: Measuring Frontier Coding Agents on Original, Long-Horizon Engineering Tasks](https://arxiv.org/html/2607.07946v1)
20. [What Makes a Good Terminal Bench Task](https://x.com/neversupervised/article/2035455298417430911)
21. [What Makes a Good Terminal-Agent Benchmark Task:](https://arxiv.org/pdf/2604.28093)
22. [terminal-bench/CONTRIBUTING.md at main · harbor-framework/terminal-bench · GitHub](https://github.com/harbor-framework/terminal-bench/blob/main/CONTRIBUTING.md)
23. [What Makes a Good Terminal Bench Task](https://www.tbench.ai/news/writing-a-good-terminal-bench-task)
24. [Doc2Feat-Bench: Evaluating Documentation-Driven Feature Addition](https://arxiv.org/abs/2507.18130)

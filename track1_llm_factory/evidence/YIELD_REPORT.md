# Yield and cost report (every attempted run)

- Attempted runs: **36**
- Valid (passed every gate): **2**  · first-pass valid: **0/36**
- Total generation cost from call logs: **$31.42** (132 model calls)
- Outcomes: killed/unterminated: 25, rejected: fairness/judge: 8, rejected: gold: 1, VALID (retired): 1, VALID: 1

| run | status | prompts | candidates | calls | cost $ | Haiku resolve@3 | replaces |
|---|---|---|---|---|---|---|---|
| pallets__click-argv_completion-0001 | killed/unterminated | ? | 0 | 2 | 0.54 |  |  |
| pallets__click-argv_completion-0002 | killed/unterminated | ? | 0 | 2 | 0.52 |  |  |
| pallets__click-argv_hard-0001 | rejected: fairness/judge | v6.3-hard | 3 | 7 | 1.61 |  |  |
| pallets__click-argv_hard-0002 | rejected: fairness/judge | v6.5.1-codexfair | 3 | 7 | 1.85 |  |  |
| pallets__click-argv_hard-0003 | killed/unterminated | ? | 2 | 5 | 1.42 |  |  |
| pallets__click-argv_hard-0004 | killed/unterminated | ? | 2 | 5 | 1.17 |  |  |
| pallets__click-argv_hard-0007 | rejected: gold | v6.7-baseline-authoritative | 4 | 8 | 1.81 |  |  |
| pallets__click-argv_hard-0008 | killed/unterminated | ? | 0 | 2 | 0.49 |  |  |
| pallets__click-argv_hard-0009 | killed/unterminated | ? | 1 | 3 | 0.89 |  |  |
| pallets__click-argv_hard-0010 | killed/unterminated | ? | 0 | 2 | 0.68 |  |  |
| pallets__click-atomic_output-0001 | killed/unterminated | ? | 0 | 1 | 0.46 |  |  |
| pallets__click-atomic_output-0002 | killed/unterminated | ? | 0 | 1 | 0.25 |  |  |
| pallets__click-help_hard-0001 | rejected: fairness/judge | v6.3-hard | 3 | 6 | 1.14 |  |  |
| pallets__click-help_hard-0002 | killed/unterminated | ? | 2 | 4 | 1.17 |  |  |
| pallets__click-help_hard-0008 | killed/unterminated | ? | 0 | 1 | 0.19 |  |  |
| pallets__click-help_hard-0009 | killed/unterminated | ? | 0 | 2 | 0.49 |  |  |
| pallets__click-lazy_defaults-0001 | killed/unterminated | ? | 0 | 1 | 0.43 |  |  |
| pallets__click-lazy_defaults-0002 | killed/unterminated | ? | 0 | 2 | 0.75 |  |  |
| pallets__click-sources-0001 | rejected: fairness/judge | v6.3-hard | 3 | 7 | 1.25 |  |  |
| pallets__click-sources-0003 | killed/unterminated | ? | 2 | 4 | 1.58 |  |  |
| pallets__click-sources-0004 | killed/unterminated | ? | 1 | 3 | 1.01 |  |  |
| pallets__click-sources-0007 | killed/unterminated | ? | 0 | 2 | 0.58 |  |  |
| pallets__click-sources-0008 | killed/unterminated | ? | 0 | 1 | 0.25 |  |  |
| pallets__click-sources-0009 | killed/unterminated | ? | 0 | 1 | 0.23 |  |  |
| pallets__click-sources-0010 | killed/unterminated | ? | 0 | 1 | 0.29 |  |  |
| pallets__click-state-0001 | VALID (retired) | v6.3-hard | 3 | 7 | 1.35 | 3/3 |  |
| pallets__click-state-0002 | rejected: fairness/judge | v6.5.1-codexfair | 3 | 6 | 1.55 |  |  |
| pallets__click-state-0003 | rejected: fairness/judge | v6.5.1-codexfair | 3 | 7 | 1.58 |  |  |
| pallets__click-state-0004 | rejected: fairness/judge | v6.5.1-codexfair | 3 | 7 | 1.28 |  |  |
| pallets__click-state-0005 | killed/unterminated | ? | 2 | 5 | 1.22 |  |  |
| pallets__click-state-0007 | killed/unterminated | ? | 0 | 2 | 0.47 |  |  |
| pallets__click-state-0008 | killed/unterminated | ? | 0 | 2 | 0.36 |  |  |
| pallets__click-state-0009 | killed/unterminated | ? | 0 | 2 | 0.37 |  |  |
| pallets__click-state-0010 | killed/unterminated | ? | 0 | 1 | 0.24 |  |  |
| pallets__click-state-0101 | rejected: fairness/judge | v6.8-coupling | 3 | 6 | 1.19 |  | pallets__click-state-0001 |
| pallets__click-types-0001 | VALID | v6.2-pilot | 3 | 7 | 0.74 |  |  |

Killed runs were stopped after an agent design review (Codex) found them unfair (self-contradictory rules / compatibility breaks) or likely easy (additive observers). Reviews only ever stopped runs; they never edited a generated task.

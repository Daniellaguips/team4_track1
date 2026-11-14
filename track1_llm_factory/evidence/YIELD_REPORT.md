# Yield and cost report (every attempted run)

- Attempted runs: **56**
- Valid (passed every gate): **3**  · first-pass valid: **0/56**
- Total generation cost from call logs: **$69.01** (184 model calls)
- Outcomes: killed/unterminated: 42, rejected: fairness/judge: 9, rejected: gold: 2, VALID: 2, VALID (retired): 1

| run | status | prompts | candidates | calls | cost $ | Haiku resolve@3 | replaces |
|---|---|---|---|---|---|---|---|
| pallets__click-argv_completion-0001 | killed/unterminated | ? | 0 | 2 | 0.54 |  |  |
| pallets__click-argv_completion-0002 | killed/unterminated | ? | 0 | 2 | 0.52 |  |  |
| pallets__click-argv_completion-0021 | killed/unterminated | ? | 0 | 1 | 2.31 |  |  |
| pallets__click-argv_completion-0022 | killed/unterminated | ? | 0 | 2 | 3.51 |  |  |
| pallets__click-argv_completion-0023 | killed/unterminated | ? | 0 | 1 | 2.12 |  |  |
| pallets__click-argv_completion-0024 | killed/unterminated | ? | 0 | 1 | 2.20 |  |  |
| pallets__click-argv_completion-0501 | killed/unterminated | ? | 1 | 3 | 1.15 |  |  |
| pallets__click-argv_completion-0502 | killed/unterminated | ? | 2 | 5 | 1.22 |  |  |
| pallets__click-argv_hard-0001 | rejected: fairness/judge | v6.3-hard | 3 | 7 | 1.61 |  |  |
| pallets__click-argv_hard-0002 | rejected: fairness/judge | v6.5.1-codexfair | 3 | 7 | 1.85 |  |  |
| pallets__click-argv_hard-0003 | killed/unterminated | ? | 2 | 5 | 1.42 |  |  |
| pallets__click-argv_hard-0004 | killed/unterminated | ? | 2 | 5 | 1.17 |  |  |
| pallets__click-argv_hard-0007 | rejected: gold | v6.7-baseline-authoritative | 4 | 8 | 1.81 |  |  |
| pallets__click-argv_hard-0008 | killed/unterminated | ? | 0 | 2 | 0.49 |  |  |
| pallets__click-argv_hard-0009 | killed/unterminated | ? | 1 | 3 | 0.89 |  |  |
| pallets__click-argv_hard-0010 | killed/unterminated | ? | 0 | 2 | 0.68 |  |  |
| pallets__click-argv_hard-0021 | killed/unterminated | ? | 0 | 1 | 2.37 |  |  |
| pallets__click-argv_hard-0501 | killed/unterminated | ? | 2 | 5 | 1.46 |  |  |
| pallets__click-argv_hard-0502 | VALID | v7-observable-deps | 2 | 5 | 1.02 |  |  |
| pallets__click-atomic_output-0001 | killed/unterminated | ? | 0 | 1 | 0.46 |  |  |
| pallets__click-atomic_output-0002 | killed/unterminated | ? | 0 | 1 | 0.25 |  |  |
| pallets__click-atomic_output-0501 | killed/unterminated | ? | 2 | 4 | 1.34 |  |  |
| pallets__click-help_hard-0001 | rejected: fairness/judge | v6.3-hard | 3 | 6 | 1.14 |  |  |
| pallets__click-help_hard-0002 | killed/unterminated | ? | 2 | 4 | 1.17 |  |  |
| pallets__click-help_hard-0008 | killed/unterminated | ? | 0 | 1 | 0.19 |  |  |
| pallets__click-help_hard-0009 | killed/unterminated | ? | 0 | 2 | 0.49 |  |  |
| pallets__click-lazy_defaults-0001 | killed/unterminated | ? | 0 | 1 | 0.43 |  |  |
| pallets__click-lazy_defaults-0002 | killed/unterminated | ? | 0 | 2 | 0.75 |  |  |
| pallets__click-lazy_defaults-0021 | killed/unterminated | ? | 0 | 1 | 2.68 |  |  |
| pallets__click-lazy_defaults-0022 | killed/unterminated | ? | 0 | 1 | 2.50 |  |  |
| pallets__click-lazy_defaults-0023 | killed/unterminated | ? | 0 | 1 | 2.68 |  |  |
| pallets__click-lazy_defaults-0024 | killed/unterminated | ? | 0 | 1 | 2.91 |  |  |
| pallets__click-lazy_defaults-0323 | rejected: gold | v6.9-noworked | 3 | 5 | 1.73 |  |  |
| pallets__click-lazy_defaults-0324 | rejected: fairness/judge | v6.9-noworked | 3 | 6 | 2.20 |  |  |
| pallets__click-lazy_defaults-0424 | killed/unterminated | ? | 0 | 2 | 1.07 |  |  |
| pallets__click-lazy_defaults-0425 | killed/unterminated | ? | 2 | 3 | 1.24 |  |  |
| pallets__click-lazy_defaults-0501 | killed/unterminated | ? | 0 | 2 | 0.97 |  |  |
| pallets__click-lazy_defaults-0502 | killed/unterminated | ? | 0 | 2 | 0.91 |  |  |
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

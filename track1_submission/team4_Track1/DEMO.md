# team4 — live demo script (dry-run tested 2:04 PM on macOS + Docker)

The rules require a **live demonstration generating and self-checking a fresh package end to end**.
Dry-run timings: **generate a fresh task 45 s**, then **official selfcheck 19 s**, about 1 minute total.

## Before the slot (2 min)
```bash
cd team4_Track1                      # the submission folder (or track1_freestyle/)
export T1_ENGINE=docker T1_WORK=/tmp/t1_demo_work
python3.12 -m venv .venv && .venv/bin/pip install -q -r requirements.txt   # stdlib pipeline + harbor
# warm the Docker image once so the live run is fast:
.venv/bin/python -m factory plan --n 1 --seed 99 --ledger ledger.json
```
Use a NEW seed live (e.g. 101). The ledger makes the planner skip variants already generated.
Prefix `PATH="/opt/homebrew/opt/findutils/libexec/gnubin:$PATH"` on a Mac (selfcheck.sh needs GNU find).

## Live (about 1 minute of commands, with narration)
```bash
# 1. generate one fresh task (pick → ground in real code → package → 9 gates)   ~45 s
.venv/bin/python -m factory generate --n 1 --seed 101 --ledger ledger.json \
    --out demo_tasks --runs runs --label live_demo

# 2. organizer structure lint + Harbor oracle/nop self-check                  ~20 s
python3.12 vendor/harness/check_structure.py demo_tasks/*
SELFCHECK_OUT=./sc bash vendor/harness/selfcheck.sh demo_tasks/*
```
Expected: `oracle reward=1.0 F2P=n/n`, `nop reward=0.0 F2P=0/n`, `✓ mechanically sound`, `ALL SOUND`.
(Dry run: `pallets__click-group-command-abbreviations-427028`: F2P 12/12, P2P 21/21.)

## What to show while it runs (about 6 min of talking)
1. The problem: generate realistic click feature tasks that are fair, testable and hard.
2. How the factory works: blueprints × knobs → spec + gold + tests, grounded in real click code, 9 gates
   (mutation, nop, P2P curation, novelty, structure, selfcheck).
3. The 5 tasks and how they differ (VARIATION_WRITEUP.md).
4. **Honest benchmark:** Haiku 5.5 solved 15/15 (README → Benchmark). What we learned: rule-dense
   specs get self-verified, and cross-module and state levers are what's next.
5. Limitations (README).

## Fallback if Docker is slow
Show `evidence/demo_*` and `evidence/selfcheck.txt` from the submission (the earlier recorded run).

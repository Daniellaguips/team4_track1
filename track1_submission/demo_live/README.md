# Live demo run (Nov 14, ~3:50 PM, macOS + Docker, Harbor 0.26.0)

Commands from `team4_Track1/DEMO.md`, run from a copy of the submission folder:

```
T1_ENGINE=docker python -m factory generate --n 1 --seed 101 --ledger ledger.json --out demo_tasks_live --label live_demo
python3.12 vendor/harness/check_structure.py demo_tasks_live/*
bash vendor/harness/selfcheck.sh demo_tasks_live/*
```

Results:
- **Generate:** `pallets__click-duration-param-type-8450ca` (family `duration`) was accepted in 48 s, with all gates passed on the first attempt.
- **Structure check:** ✓
- **Harbor self-check (22 s):** oracle reward 1.0 (F2P 16/16, P2P 37/37), nop reward 0.0 (F2P 0/16, P2P 37/37), `ALL SOUND`.

`demo_task.html` renders the task statement exactly as the AI agent receives it. This folder is outside the submitted ZIP.

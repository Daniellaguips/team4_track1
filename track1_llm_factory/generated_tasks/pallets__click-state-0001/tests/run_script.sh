#!/usr/bin/env bash
# Generated deterministic verifier runner. Keep absent paths out so nop still runs P2P.
set -uo pipefail
cd /app
PY=/app/.venv/bin/python
[ -x "$PY" ] || PY="$(command -v python)"
ALL=(
  tests/test_context.py
  tests/test_chain.py
  tests/test_commands.py
  tests/test_testing.py
  tests/test_basic.py
  tests/test_invocation_ledger_an_opt_in_invocation_scoped_event_log_shared_by_every_context_in_a_run.py
)
PRESENT=()
for f in "${ALL[@]}"; do [ -e "$f" ] && PRESENT+=("$f"); done
[ "${#PRESENT[@]}" -eq 0 ] && { echo "no graded test files present"; exit 2; }
"$PY" -m pytest "${PRESENT[@]}" -rA --tb=short -p no:cacheprovider --color=no --continue-on-collection-errors

#!/usr/bin/env bash
# Run the graded test files that exist in the current tree (the feature file is absent at base).
# Not `set -e`: pytest exits non-zero when the feature is missing.
set -uo pipefail
cd /app
PY=/app/.venv/bin/python
[ -x "$PY" ] || PY="$(command -v python)"
ALL=(
  "tests/test_arguments.py"
  "tests/test_basic.py"
  "tests/test_chain.py"
  "tests/test_command_collection_compat.py"
  "tests/test_command_collection_providers.py"
  "tests/test_commands.py"
  "tests/test_formatting.py"
  "tests/test_info_dict.py"
  "tests/test_normalization.py"
  "tests/test_shell_completion.py"
)
PRESENT=()
for f in "${ALL[@]}"; do [ -e "$f" ] && PRESENT+=("$f"); done
[ "${#PRESENT[@]}" -eq 0 ] && { echo "no graded test files present"; exit 0; }
"$PY" -m pytest "${PRESENT[@]}" -rA --tb=short -p no:cacheprovider -p no:randomly --color=no --continue-on-collection-errors

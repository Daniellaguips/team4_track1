#!/usr/bin/env bash
# Generated deterministic verifier runner. Keep absent paths out so nop still runs P2P.
set -uo pipefail
cd /app
PY=/app/.venv/bin/python
[ -x "$PY" ] || PY="$(command -v python)"
ALL=(
  tests/test_imports.py
  tests/test_info_dict.py
  tests/test_types/test_IntRange.py
  tests/test_types/test_FloatRange.py
  tests/test_types/test_ParamType.py
  tests/test_types/test_convert_type.py
  tests/test_options.py
  tests/test_types/test_click_duration.py
)
PRESENT=()
for f in "${ALL[@]}"; do [ -e "$f" ] && PRESENT+=("$f"); done
[ "${#PRESENT[@]}" -eq 0 ] && { echo "no graded test files present"; exit 2; }
"$PY" -m pytest "${PRESENT[@]}" -rA --tb=short -p no:cacheprovider --color=no --continue-on-collection-errors

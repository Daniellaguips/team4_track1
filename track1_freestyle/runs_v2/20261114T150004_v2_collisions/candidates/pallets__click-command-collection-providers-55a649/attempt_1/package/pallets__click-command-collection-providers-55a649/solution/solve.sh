#!/bin/bash
# Oracle: apply the reference implementation to /app.
set -e
git -C /app apply "$(dirname "$0")/patch.diff"
echo "gold applied to /app"

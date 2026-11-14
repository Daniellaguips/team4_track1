#!/bin/sh
# Host-compatibility shim (macOS): emulate GNU `find DIR -name PAT -printf '%T@ %p\n'` as used by the
# organizer selfcheck.sh read_grade(); every other invocation goes to the system find unchanged.
if [ "$#" -eq 5 ] && [ "$2" = "-name" ] && [ "$4" = "-printf" ] && [ "$5" = '%T@ %p\n' ]; then
  exec /usr/bin/find "$1" -name "$3" -exec stat -f '%m %N' {} +
fi
exec /usr/bin/find "$@"

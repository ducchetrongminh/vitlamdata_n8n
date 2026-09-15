#!/usr/bin/env bash
# Write nocodb/<base>/_base.json and nocodb/<base>/<table>.json from NocoDB.
# Usage: scripts/nocodb-pull.sh [--force] [base_id...]
#   no ids: every base that already has a pushed _base.json; removes files of deleted tables
#   --force: overwrite local edits that were not pushed
set -euo pipefail
exec python3 "$(dirname "$0")/nocodb.py" pull "$@"

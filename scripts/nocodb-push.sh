#!/usr/bin/env bash
# Create or update NocoDB bases and tables from nocodb/<base>/*.json, then rewrite each file from
# the live result.
# Usage: scripts/nocodb-push.sh [--force] [--delete] [file...]
#   no files: every nocodb/*/*.json
#   --force: overwrite even if the table changed in NocoDB since the last pull
#   --delete: delete live fields missing from the file, with their data
set -euo pipefail
exec python3 "$(dirname "$0")/nocodb.py" push "$@"

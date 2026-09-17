#!/usr/bin/env bash
# Create (file has no id) or update (file has an id) a workflow in n8n, then rewrite the
# file from the live result. A deleted <id>.json under workflows/ deletes that workflow in n8n.
# Usage: scripts/push.sh [--force] <file>
#   --force: overwrite (or delete) even if the workflow changed in n8n since the last pull
set -euo pipefail
exec python3 "$(dirname "$0")/n8n_sync.py" push "$@"

#!/usr/bin/env bash
# Export workflows the API key can see to workflows/<id>.json.
# Usage: scripts/pull.sh [--force] [id...]
#   no ids: pull every workflow and remove files of workflows gone from n8n
#   --force: overwrite local edits that were not pushed
set -euo pipefail
exec python3 "$(dirname "$0")/n8n_sync.py" pull "$@"

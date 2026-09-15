#!/usr/bin/env bash
# Write credentials/<type>_<id>.json for every credential referenced in workflows/*.json that has no
# file yet, with a ${VAR} placeholder per string field. Existing files are left alone.
# Usage: scripts/pull-credentials.sh
set -euo pipefail
exec python3 "$(dirname "$0")/n8n_credentials.py" pull "$@"

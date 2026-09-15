#!/usr/bin/env bash
# Create (file has no id) or update (file has an id) credentials in n8n, filling placeholders
# from .credentials.env and secrets/. A credential with any placeholder unfilled is skipped.
# Usage: scripts/push-credentials.sh [--force] [file...]
#   no files: every credentials/*.json
#   --force: push even if nothing changed since the last push
set -euo pipefail
exec python3 "$(dirname "$0")/n8n_credentials.py" push "$@"

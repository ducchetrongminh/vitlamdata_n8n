# Set up vitlamdata_n8n

This empty folder becomes the `vitlamdata_n8n` git repository. Its purpose: let Claude Code
create, edit, monitor and operate workflows on the vitlamdata n8n instance through n8n's
public REST API, with every workflow kept as JSON in git so changes have diffs and rollback.

Work in two phases. Stop at the end of phase 1: phase 2 needs an API key only I can create.

## Context (true today)

- n8n `2.38.7` (image `n8nio/n8n`) at https://n8n.vitlamdata.com, behind Traefik. A separate
  repo, `vitlamdata_infras`, deploys it. Nothing about deployment, Docker or the VM belongs here.
- Public API is on. Swagger UI is off (`N8N_PUBLIC_API_SWAGGERUI_DISABLED=true`), so there is no
  `/api/v1/docs` to read: verify every endpoint by calling it.
- Instance settings that constrain workflows:
  - Community nodes are disabled. Only built-in nodes exist.
  - `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`: `$env` does not work in expressions or Code nodes.
  - SSRF protection is on: HTTP Request nodes cannot reach private, loopback or link-local
    addresses unless the infra repo allowlists the host.
  - Timezone `Asia/Ho_Chi_Minh`.
- No enterprise license, so API keys have no scopes. The key belongs to a dedicated n8n
  **member** user, not the owner. It can do anything that user can, and sees only workflows and
  credentials that user owns or that are shared with it.

## Phase 1: scaffold

2. `.gitignore` containing `.env`.
3. `.env.example`:
   ```
   N8N_URL=https://n8n.vitlamdata.com
   N8N_API_KEY=
   ```
   I create `.env` myself. Never ask me to paste the key into the chat. Never print, echo or
   log it.
4. `.claude/settings.json`: a SessionStart hook that exports `.env` into Claude's Bash
   environment, plus a deny rule so the Read tool does not pull the key into the transcript:
   ```json
   {
     "permissions": { "deny": ["Read(./.env)"] },
     "hooks": {
       "SessionStart": [{ "hooks": [{ "type": "command",
         "command": "f=\"$CLAUDE_PROJECT_DIR/.env\"; [ -f \"$f\" ] && [ -n \"$CLAUDE_ENV_FILE\" ] && grep -E '^[A-Za-z_][A-Za-z0-9_]*=' \"$f\" | sed 's/^/export /' >> \"$CLAUDE_ENV_FILE\"; exit 0"
       }]}]
     }
   }
   ```
6. A first `CLAUDE.md` with the rules below (the API section comes in phase 2).
7. Checkout, commit, then **stop** and tell me to:
   1. In n8n, create a member user for Claude, sign in as it, and create an API key with an expiry.
   2. Copy `.env.example` to `.env` and fill in the key.
   4. Start a new Claude session, because the hook only runs at session start.

## Phase 2: verify the API and build the loop

8. Check the key loaded without revealing it: `[ -n "$N8N_API_KEY" ] && echo set`.
9. Verify the API against the live instance, read-only calls first, header
   `X-N8N-API-KEY: $N8N_API_KEY`, base `$N8N_URL/api/v1`:
   - `GET /workflows?limit=1`, `GET /executions?limit=1`, `GET /tags`, pagination via `nextCursor`.
   - Create a throwaway workflow, then find out what `PUT /workflows/{id}` accepts and rejects
     (read-only fields), whether activate/deactivate endpoints exist, and how to read one
     execution with its data. Delete the throwaway afterwards.
   - Record only what you verified. If something I assumed does not exist, say so.
10. `scripts/pull.sh`: export every workflow the key can see to `workflows/<id>.json`,
    pretty-printed with sorted keys, with volatile fields (timestamps and similar, decided from
    step 9) stripped so diffs show only real changes.
11. `scripts/push.sh <file>`: create when the file has no id, update when it has one, sending
    only the fields the API accepts. Before an update, compare the live workflow with the last
    pulled version and refuse if someone changed it in the UI since.
12. Finish `CLAUDE.md` with the verified API facts and the loop: edit the JSON, push, activate,
    watch executions, commit. Include a monitoring recipe (recent failed executions and their
    error node and message).
13. Short `README.md`: what the repo is, first-time setup (the phase 1 stop list), pull/push usage.
14. Run `scripts/pull.sh`, shellcheck the scripts, commit.

## Rules for CLAUDE.md

- Never print, echo or log `N8N_API_KEY`, and never write it anywhere but `.env`.
- `workflows/*.json` is the source of truth. Change a workflow by editing its file and pushing.
  After a UI edit, pull and commit.
- Ask before deleting a workflow, deactivating an active workflow, or overwriting a workflow
  that changed in n8n since the last pull.
- Never put secrets in workflow JSON: nodes reference n8n credentials. Create a credential
  through the API only with values I provide out-of-band. The API cannot read credential
  secrets back.
- Keep the instance constraints from "Context" in mind: built-in nodes only, no `$env`, no
  private-network HTTP targets.
- If a session installs a CLI tool ad hoc, add it to `.devcontainer/postCreate.sh` or
  `devcontainer.json` in the same change, or it is gone on the next rebuild.
- Docs and comments state what is true now, plus a short reason when it isn't obvious. History
  goes in commit messages.

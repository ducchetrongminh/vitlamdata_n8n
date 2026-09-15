# vitlamdata_n8n

Claude Code creates, edits, monitors and operates workflows on the vitlamdata n8n instance
through n8n's public REST API. Every workflow lives as JSON in git so changes have diffs and
rollback.

## Instance

- n8n `2.38.7` at https://n8n.vitlamdata.com. Deployment lives in the `vitlamdata_infras` repo;
  nothing about Docker, Traefik or the VM belongs here.
- Swagger UI is off, so there is no `/api/v1/docs`. Verify endpoints by calling them.
- Community nodes are disabled: built-in nodes only.
- `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`: `$env` does not work in expressions or Code nodes.
- SSRF protection is on: HTTP Request nodes cannot reach private, loopback or link-local
  addresses unless `vitlamdata_infras` allowlists the host.
- Timezone `Asia/Ho_Chi_Minh`.
- No enterprise license, so the API key has no scopes. It belongs to a dedicated n8n member user
  and sees only workflows and credentials that user owns or that are shared with it.

## Environment

`.env` (gitignored, created by the user from `.env.example`) holds `N8N_URL` and `N8N_API_KEY`.
A SessionStart hook in `.claude/settings.json` exports it into the Bash environment, so a new
session is needed after `.env` changes. Reading `.env` with the Read tool is denied.

## Rules

- Never print, echo or log `N8N_API_KEY`, and never write it anywhere but `.env`. To check it
  loaded: `[ -n "$N8N_API_KEY" ] && echo set`.
- `workflows/*.json` is the source of truth. Change a workflow by editing its file and pushing.
  After a UI edit, pull and commit.
- Ask before deleting a workflow, deactivating an active workflow, or overwriting a workflow
  that changed in n8n since the last pull.
- Never put secrets in workflow JSON: nodes reference n8n credentials. Create a credential
  through the API only with values the user provides out-of-band. The API cannot read
  credential secrets back.
- Keep the instance constraints above in mind: built-in nodes only, no `$env`, no
  private-network HTTP targets.
- Docs and comments state what is true now, plus a short reason when it isn't obvious. History
  goes in commit messages.

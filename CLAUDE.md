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
- Never put secrets in workflow or credential JSON: nodes reference n8n credentials, and
  credential files reference placeholders. The user fills `.credentials.env` and `secrets/`
  themselves; never read them (Read is denied), print resolved values, or write a real secret
  there. The API cannot read credential secrets back.
- Ask before deleting a credential.
- Keep the instance constraints above in mind: built-in nodes only, no `$env`, no
  private-network HTTP targets.
- Docs and comments state what is true now, plus a short reason when it isn't obvious. History
  goes in commit messages.

## Scripts

Need `bash`, `python3` (standard library only) and `git`.

- `scripts/pull.sh [--force] [id...]` writes each workflow to `workflows/<id>.json`: sorted keys,
  2-space indent, only the fields `id name description active isArchived nodes connections
  settings pinData nodeGroups tags` (tags as names). Everything else changes without a real edit
  or is runtime state (`staticData` is written by trigger nodes). With no ids it pulls every
  workflow and deletes files whose workflow is gone. It refuses to overwrite a file edited
  locally but not pushed; `--force` overwrites.
- `scripts/push.sh [--force] <file>` creates the workflow when the file has no `id` (then renames
  the file to `workflows/<id>.json`) and updates it otherwise. It sends `name nodes connections
  settings pinData nodeGroups`, then `description` and tags if they differ. It never changes
  `active` or `isArchived`. Before an update it refuses if the live workflow differs from the last
  pulled or pushed version; `--force` overwrites, and needs the user's go-ahead. Afterwards it
  rewrites the file from the live result.
- `.n8n-state/<id>.json` (gitignored) holds that last known live version. Without it, push
  compares against the committed file.

## Credentials

The API cannot list or read credentials, so `credentials/*.json` is the source of truth and
sync goes one way, repo to n8n. Edits made in the n8n UI are overwritten on the next push that
changes the file.

- `credentials/<id>.json`: `id name type data`. In any string of `data`, `${VAR}` is replaced
  by `VAR` from `.credentials.env` (`KEY=value` lines, quotes optional) and `${file:NAME}` by
  the contents of `secrets/NAME` minus a trailing newline, for multi-line values like private
  keys. Non-secret values and numbers or booleans go in literally. Field names come from
  `GET /credentials/schema/<type>`.
- `.credentials.env.example` (committed) lists every `${VAR}` the credential files use, with
  empty values. Add a variable to it whenever a credential file gains one.
- `scripts/pull-credentials.sh` writes a file for every credential that `workflows/*.json`
  references and that has no file yet, including credentials other users created in the UI. It
  puts a placeholder in each plain string field (not enums, numbers, booleans or
  `allowedDomains`). Delete the placeholders a credential does not use. Existing files are
  never touched.
- `scripts/push-credentials.sh [--force] [file...]` (default: all files) skips a credential if
  any placeholder has no value, or an empty one. Otherwise it creates the credential (no `id`:
  then writes the id and renames the file to `credentials/<id>.json`) or sends a `PATCH` with
  the full `name type data`. `.n8n-state/credentials/<id>.sha256` holds a hash of the last body
  sent, and a push with the same body does nothing unless `--force`.
- The API user can update only credentials it owns or that are shared with it. Others return
  404, which is also what a deleted credential returns.

## Loop

1. `scripts/pull.sh`, commit anything that changed in the UI.
2. Edit `workflows/<id>.json`, or write a new file without `id`.
3. `scripts/push.sh workflows/<file>.json`. If it refuses, pull the id, redo the edit on top,
   push again. Pushing an active workflow changes production immediately.
4. Activate if needed (`POST /workflows/{id}/activate`), then `scripts/pull.sh <id>` so the file
   records `active`.
5. Trigger it (a production webhook is `$N8N_URL/webhook/<path>`, live only while active) and
   check its executions.
6. Commit the workflow file.

## API

Verified against this instance. Base `$N8N_URL/api/v1`, header `X-N8N-API-KEY: $N8N_API_KEY`.

```bash
# api <path> [curl args...], e.g. api /workflows/<id>/activate -X POST
api() { local p=$1; shift; curl -sS -H "X-N8N-API-KEY: $N8N_API_KEY" -H 'Content-Type: application/json' "$@" "$N8N_URL/api/v1$p"; }
```

- Lists return `{"data": [...], "nextCursor": ...}`. Pass `limit` and `cursor=<nextCursor>` until
  `nextCursor` is null. An invalid cursor is a 400. Unknown query parameters are ignored.
- `GET /workflows` includes archived workflows (`isArchived: true`) and omits `description`.
  Filters: `name`, `tags` (tag name). `GET /workflows/{id}` returns everything;
  `excludePinnedData=true` drops `pinData`.
- `POST /workflows` requires `name nodes connections settings` and accepts `pinData nodeGroups
  staticData`. It rejects `description`, and `id active tags meta` as read-only. Nodes without
  `id` get one.
- `PUT /workflows/{id}` requires `name nodes connections settings` and also accepts `description
  pinData nodeGroups staticData`. Read-only, rejected with 400: `id active activeVersion createdAt
  updatedAt isArchived meta shared tags triggerCount versionId`. Unrecognized, also 400:
  `activeVersionId sourceWorkflowId versionCounter`, and unknown `settings` keys.
  - Settings merge: a key left out keeps its live value. An omitted `description` stays too.
  - No optimistic locking: `versionId` cannot be sent. It changes only when nodes or connections
    change; `updatedAt` changes on every PUT.
  - On an active workflow the new version goes live at once (`activeVersionId` follows).
  - On an archived workflow: 400 `Cannot update an archived workflow.`
- `POST /workflows/{id}/activate` and `/deactivate` exist and are idempotent. Activate fails with
  400 when there is no trigger node; its optional body `{"versionId": ...}` picks a version.
- `POST /workflows/{id}/archive` and `/unarchive` exist. `DELETE /workflows/{id}` deletes for good.
- Tags: `GET`/`POST /tags`, `GET`/`PUT /workflows/{id}/tags` with body `[{"id": ...}]`.
  `DELETE /tags/{id}` is 403 for this user.
- 403 for this user: `GET /credentials`, `GET /credentials/{id}`, `GET /projects`,
  `GET /variables`.
- Credentials: `GET /credentials/schema/<type>` returns a JSON schema of the `data` fields
  (`properties`, `required`). `POST /credentials` takes `name type data` and returns metadata
  only (`id name type createdAt updatedAt isManaged isGlobal isResolvable ...`, never `data`).
  An unknown type or a missing required field is a 400.
  - `PATCH /credentials/{id}` takes any of `name type data` (`PUT` is 405). `data` is checked
    against the schema as a whole, so a partial `data` without the required fields is a 400.
    Unknown `data` keys are a 400. Changing `type` needs `data`. Unknown body keys like `id` are
    ignored.
  - `DELETE /credentials/{id}` returns the deleted metadata. An unknown id is 404 for PATCH and
    DELETE.
- `GET /executions` filters: `workflowId`, `status` (`canceled crashed error new running success
  unknown waiting`), `includeData`. `GET /executions/{id}?includeData=true` adds `workflowData`
  and `data.resultData` with `lastNodeExecuted`, `error.message`, and per-node
  `runData[<node>][i].error`.
- `POST /executions/{id}/retry` starts a new execution (`mode: retry`, `retryOf`).
  `POST /executions/{id}/stop` on a finished execution returns 500.

## Monitoring

Recent failures, then the failing node and message of one:

```bash
api() { curl -sS -H "X-N8N-API-KEY: $N8N_API_KEY" "$N8N_URL/api/v1$1"; }
api '/executions?status=error&limit=20' | python3 -c '
import json, sys
for e in json.load(sys.stdin)["data"]:
    print(e["id"], e["workflowId"], e["startedAt"], e["mode"])'
api '/executions/<id>?includeData=true' | python3 -c '
import json, sys
x = json.load(sys.stdin); r = x["data"]["resultData"]
print(x["workflowData"]["name"], "|", r.get("lastNodeExecuted"), "|", (r.get("error") or {}).get("message"))'
```

Add `&workflowId=<id>` to watch one workflow. `status=crashed` catches executions that died
without a node error.

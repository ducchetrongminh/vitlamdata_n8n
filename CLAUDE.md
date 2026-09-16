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
  rewrites the file from the live result. Given the path of a deleted `workflows/<id>.json`, it
  deactivates and deletes that workflow in n8n, refusing if it changed since the last pull; ask
  before running it.
- `.n8n-state/<id>.json` (gitignored) holds that last known live version. Without it, push
  compares against the committed file.

## Credentials

The API cannot list or read credentials, so `credentials/*.json` is the source of truth and
sync goes one way, repo to n8n. Edits made in the n8n UI are overwritten on the next push that
changes the file.

- `credentials/<type>_<id>.json`: `id name type data`. In any string of `data`, `${VAR}` is replaced
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
  then writes the id into the file) or sends a `PATCH` with the full `name type data`. After a
  push, a file in `credentials/` is renamed to `<type>_<id>.json` if it has another name. `.n8n-state/credentials/<id>.sha256` holds a hash of the last body
  sent, and a push with the same body does nothing unless `--force`.
- The API user can update only credentials it owns or that are shared with it. Others return
  404, which is also what a deleted credential returns.

## NocoDB

NocoDB tables live in `nocodb/<base>/` and sync both ways through NocoDB's v3 meta API
(`$NOCODB_HOST/api/v3/meta`, header `xc-token`), with `NOCODB_HOST` and `NOCODB_API_KEY` read from
`.credentials.env` (the Nocodb bot credential's values). Workflows reference base and table ids
from these files.

- `_base.json`: `id title workspace_id`. `<table title>.json`: `id title description
  display_field fields`, each field `id title type description default_value unique options`.
  Empty values are left out. Field types and options follow `FieldBase` and `FieldOptions_*` in
  NocoDB's `packages/nocodb/src/schema/swagger-v3.json`.
- `scripts/nocodb-push.sh [--force] [--delete] [file...]` (default: all files, bases first)
  creates a base or table without `id`, then rewrites the file from the live result with ids.
  On a table with `id` it adds fields without `id` and changes fields whose values differ,
  matched by `id`, so a rename keeps the data. It refuses if the table changed in NocoDB since
  the last pull (`--force` overwrites) and if a live field is missing from the file (`--delete`
  deletes it with its data; ask first). Fields of type `ID` are never touched.
- `scripts/nocodb-pull.sh [--force] [base_id...]` rewrites every table of the bases that have a
  pushed `_base.json` (or the given ids) and removes files of deleted tables. It refuses to
  overwrite local edits not pushed.
- `.n8n-state/nocodb/<id>.json` holds the last known live base or table.
- A type change converts existing values in NocoDB and can lose data; check the field first.
- Verified: `PATCH /bases/{b}/fields/{f}` ignores `"description": null`; `""` clears it. Created
  tables get `Id`, `CreatedAt` and `UpdatedAt`; only `Id` shows in the meta API. Data API
  DateTime values with an offset (`2026-09-15T08:30:00+07:00`) store correctly. NocoDB's own
  `CreatedAt`/`UpdatedAt` read 7 hours behind real UTC: the app Postgres runs with
  `TZ: Asia/Ho_Chi_Minh` (`vitlamdata_infras`), and NocoDB writes UTC times without an offset,
  which Postgres reads as +07. Workflows write their own timestamps from `$now`. A data API
  bulk `DELETE` of 40 records answered 422; batches of 10 work.
- Filters with `exactDate` compare the date only, whatever time the value carries:
  `(created_at,lt,exactDate,2026-09-16T21:21:41+07:00)` matches nothing created that day. Filter
  by day in NocoDB and by time in a Code node. Checkbox filters are `(field,checked)` and
  `(field,notchecked)`.

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

## Nodes

Verified on this instance while building `Idea shaping` and `Finalize content`.

- `n8n-nodes-base.formTrigger` has no typeVersion 2.2 here. A workflow using it is accepted and
  activates, `triggerCount` is 1, but no route is registered and `$N8N_URL/form/<path>` answers
  404 with n8n's "Problem loading form" page. Use 2.1.
- A form is submitted as `multipart/form-data` with the field names `field-0`, `field-1`, ... in
  the order the fields are defined. Labels are not accepted: posting by label yields `null` for
  every field. Page 1 answers with `{"formWaitingUrl": ...}`; the next page and the ending are
  posted to that URL. The ending renders client-side, so fetching the URL without a browser shows
  the empty form shell.
- `n8n-nodes-base.nocoDb` (typeVersion 4) returns a row as `{id, id_fields: {Id}, fields: {...}}`.
  Read values from `$json.fields`, not from `$json`.
- Its `update` operation needs the row id in the top-level `id` parameter. `matchingColumns` is
  not enough: activating fails with `Missing or invalid required parameters: id`.
- It returns DateTime values in UTC as `2026-09-17 13:00:00+00:00` (space, not `T`).
- A node runs once per input item. A search after a node that outputs several items runs that many
  times unless the node has `executeOnce: true`.
- Activating a workflow with an Execute Workflow node fails while the sub-workflow it calls is
  inactive: `Cannot publish workflow: Node "X" references workflow <id> ("Y") which is not
  published`. Activate sub-workflows first; a sub-workflow with only an Execute Workflow Trigger
  activates fine.
- `@n8n/n8n-nodes-langchain.chainLlm` with a DeepSeek model set to `responseFormat: json_object`
  outputs the parsed JSON object as the item, not `{text}`. With the default text format it
  outputs `{text}`. Braces in its system message are escaped; the prompt text is passed as a
  variable, so JSON in either is safe.
- `@n8n/n8n-nodes-langchain.agent` 3.1 with `lmChatDeepSeek` `deepseek-reasoner` (thinking mode)
  calls tools and keeps `memoryBufferWindow` history across executions: n8n patches
  `@langchain/openai` to send DeepSeek's `reasoning_content` back, which the API requires once
  tools are involved. It makes parallel tool calls.
- `@n8n/n8n-nodes-langchain.toolWorkflow` 2.2 takes its tool name from the node name. Arguments come
  from `$fromAI('key', 'description', 'string'|'number'|'boolean')` in `workflowInputs.value`, and
  `workflowInputs.schema` must list every key; the sub-workflow trigger can accept all data. Other
  values there may be plain expressions such as `$('Task').first().json.mode`, which the model
  cannot set. Keep quotes and braces out of `$fromAI` descriptions and put formats in the tool
  description.
- An HTTP Request node with `authentication: predefinedCredentialType` and `nodeCredentialType:
  facebookGraphApi` adds the credential's token as the `access_token` query parameter.

- Branches from one node run top to bottom by canvas position (`executionOrder: v1`), and an error
  in one stops the rest: put database writes above Lark or other outbound calls.

## Lark Open API

Verified with the Lark content bot (custom app, credential `Lark content bot`).

- `httpCustomAuth` with `{"body": {"app_id", "app_secret"}}` on `POST
  auth/v3/tenant_access_token/internal` returns `tenant_access_token` (2 hours). Wrong values answer
  HTTP 200 with `code 10003 invalid param`, so check `code`, not the HTTP status.
- Event subscription verification posts `{"challenge", "token", "type": "url_verification"}` and
  expects `{"challenge"}` back.
- `GET im/v1/messages/<id>` returns `items[0]` with `sender.id` (the open_id), `sender.sender_type`,
  `msg_type`, `parent_id` and `body.content` as a JSON string.
- A wiki link resolves with `GET wiki/v2/spaces/get_node?token=` to `node.obj_token`, and `GET
  docx/v1/documents/<obj_token>/raw_content` returns the text once the app is added to the doc.
- A picture sent to the bot arrives as `msg_type: image` with content `{"image_key"}`, or as `img`
  elements inside a `post` message. `GET im/v1/messages/<message id>/resources/<image key>?type=image`
  returns the file with the scopes above; a key that is not in the message answers `234003 File not
  in msg`.
- An execution retried with `POST /executions/<id>/retry` reuses the stored output of the nodes
  before the failed one, so a stale token is reused. Replay the webhook body instead.

## Facebook Graph API

Verified with the page token of Vịt làm Data (credential `Facebook page`, app use case "Manage
everything on your Page").

- With a page token, `me` is the page: `POST me/feed` publishes, `GET me?fields=followers_count`.
- `POST me/feed` with `published=false` creates an unpublished post (`is_published: false`) that
  `DELETE /<post id>` removes: a way to test publishing without posting publicly.
- Post insights `post_impressions` and `post_impressions_unique` answer `(#100) The value must be a
  valid insights metric`. `post_total_media_view_unique`, `post_media_view`, `post_clicks` and
  `post_reactions_by_type_total` work.
- A post with photos: upload each with `POST me/photos` (multipart `source`, `published=false`),
  then `POST me/feed` with JSON `{"message", "attached_media": [{"media_fbid": <photo id>}]}`.
  Deleting the post deletes its photos. In n8n the upload is an HTTP Request node with
  `contentType: multipart-form-data` and a `formBinaryData` body parameter named `source`.
- `GET /<post id>/comments` returns the text but no `from` for commenters: that needs the Business
  Asset User Profile Access feature.
- `debug_token` on the page token shows `expires_at: 0` but a `data_access_expires_at` 90 days out.

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

# Implementation in n8n

Read this when you're past Phase 3 and actually wiring a crew's workflows.

## Mapping design artifacts to n8n

| Design artifact | n8n implementation |
|---|---|
| Agent (role model) | one workflow per agent under `workflows/<crew_name>/`, **Execute Workflow trigger** |
| Agent contract → prompt | AI Agent node system prompt (content pulled from `crews/<crew_name>/04-prompts/`) |
| Output contract | Structured Output Parser sub-node + a code-level schema validation step |
| Acquaintance matrix | which sub-workflows are attached to which agent as **Call n8n Workflow Tool** |
| Tool registry | tool sub-nodes / HTTP Request Tool, one per registry entry |
| Blackboard / shared state | a NocoDB table under `nocodb/<base>/`, keyed by `run_id` (see `CLAUDE.md`'s NocoDB section) |
| Agent memory (`thread`) | Postgres Chat Memory sub-node (n8n's own DB) or a NocoDB table if you need to query history outside the agent |
| Lifecycle gates | IF / Switch nodes, Code nodes — never model judgment alone |
| Termination limits | agent `maxIterations` + explicit counters in the orchestrator loop |
| Human-in-the-loop | Wait node with webhook resume, or Form/Slack approval |
| Tracing | a Code node after every stage writing a row to a NocoDB trace table, or `GET /executions` for a quick look |
| Credentials | `credentials/<type>_<id>.json` + `scripts/push-credentials.sh` — never inline keys in nodes |
| Versioning | `workflows/<crew_name>/<id>.json` via `scripts/pull.sh` / `push.sh`, committed to git |

## Node-level notes

- The **Tools Agent** is the default agent type; it selects tools from their descriptions, so
  the registry description field is load-bearing.
- **Call n8n Workflow Tool** is what turns a workflow into a sub-agent. Give each one a
  description written like a tool spec, not like a workflow name.
- Sub-agents should accept and return **one JSON object**, matching the envelope. Map fields
  explicitly with a Set node at both ends — do not rely on implicit passthrough.
- Use **Split Out + Loop Over Items** to process sections/chunks as separate model calls.
  Cheaper retries, better quality, isolated failures.
- Attach an **error output** to every tool-bearing node and route it to a dead-letter path.
- For loops (evaluator–optimizer), use an explicit counter in a Set node and an IF node.
  Never let the agent decide when to stop.

## State and tracing in NocoDB

Docker, Traefik and the n8n VM belong to `vitlamdata_infras`, not here — nothing in this repo
configures the instance itself. What *is* in scope: state a crew needs beyond n8n's own
execution log. Use NocoDB, following the existing convention in `CLAUDE.md`'s NocoDB section
(`nocodb/<base>/`, `scripts/nocodb-push.sh`, `.n8n-state/nocodb/`), not a hand-rolled Postgres
schema:

- **`runs` table** — `run_id`, `trigger_type`, `input`, `status`
  (`running|done|failed|cancelled`), `started_at`, `ended_at`, `total_cost`.
- **`stage_traces` table** — `run_id`, `stage`, `agent_id`, `agent_version`, `prompt_version`,
  `model`, `input_tokens`, `output_tokens`, `cost`, `latency_ms`, `tool_calls`, `status`,
  `issues`, `created_at`.
- **`artifacts` table** — `run_id`, `stage`, `payload`, `payload_schema`, `created_at`. Lets you
  resume a failed run from the last good stage instead of re-running the whole crew.

Only add these tables once a crew's evaluation or debugging actually needs them (Gate 6) —
`GET /executions?workflowId=` already gives per-run history for free. Define them as
`nocodb/<base>/<table>.json` per the existing schema (`id title description display_field
fields`), push with `scripts/nocodb-push.sh`, and reference the base/table ids from the
workflow nodes that write to them.

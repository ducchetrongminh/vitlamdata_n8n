# Building an AI Agent Crew — Design & Implementation Guide

A phased methodology for designing, building and operating a multi-agent LLM system,
with implementation mapping for **n8n (self-hosted)**.

This document is both a **method** and a **set of fill-in templates**. It is written to be
committed to a repo and used as working context for an AI coding assistant.

---

## 0. How to use this document

### 0.1 With Claude Code (or any coding agent)

Paste this at the start of a session:

> Read `AGENT_CREW_GUIDE.md`. We are at Phase `<N>`. Do not skip ahead to implementation.
> Work through the phase with me, ask me the questions listed under that phase, and produce
> the phase's artifact into `specs/`. Stop at the phase gate and wait for my approval.

Rules for the assistant working with this document:

1. **Never generate agent prompts before the agent contracts in `specs/agents/` exist.**
   A prompt written before a contract is a guess.
2. **Every artifact is a file in the repo**, not a message in the chat. The repo is the
   source of truth.
3. **Phase gates are hard.** Do not start Phase N+1 until the Phase N checklist passes.
4. When a design question has no clear answer, write it into `specs/open-questions.md`
   rather than inventing an answer.
5. Prefer removing an agent over adding one. Argue for the smaller system.

### 0.2 Suggested repo layout

```
.
├── AGENT_CREW_GUIDE.md          # this file
├── specs/
│   ├── 00-task-spec.md          # Phase 0 — the SOP
│   ├── 01-architecture.md       # Phase 1 — topology + control boundary
│   ├── agents/
│   │   ├── _template.yaml
│   │   ├── researcher.yaml      # Phase 2 — one contract per agent
│   │   └── ...
│   ├── 03-interaction.md        # Phase 3 — protocol, schemas, acquaintance matrix
│   ├── schemas/
│   │   ├── envelope.schema.json
│   │   └── research_result.schema.json
│   ├── tools/
│   │   ├── _template.yaml
│   │   └── registry.md          # Phase 5 — tool registry
│   ├── 06-evaluation.md         # Phase 6 — eval plan
│   └── open-questions.md
├── prompts/
│   ├── _shared.md               # global rules injected into every agent
│   └── researcher.md            # one per agent, generated from its contract
├── evals/
│   ├── dataset.jsonl            # golden set
│   └── rubrics/
├── workflows/                   # exported n8n JSON, version-controlled
│   ├── orchestrator.json
│   └── agent_researcher.json
├── db/
│   └── migrations/              # state tables
└── docs/
    └── decisions/               # ADRs, one per irreversible choice
```

---

## 1. Core principles

These five ideas do most of the work. Everything below is mechanics.

### 1.1 The control boundary

Every decision in your system is made either by **code** or by **a model**. Draw the line
explicitly and write it down. Decisions made by code are testable, cheap, deterministic and
debuggable. Decisions made by a model are none of those things.

> Default position: a decision goes to the model **only** when the input space is too open
> for rules. Everything else is an `IF`, a `switch`, or a SQL query.

Most failing agent crews fail because the boundary was never drawn, and model judgment
leaked into places that should have been code — routing, termination, validation, retry.

### 1.2 Specification beats prompting

Failures in multi-agent systems cluster into three structural causes:

| Cause | Symptom | Fix |
|---|---|---|
| Under-specification | agent does something adjacent to what you wanted | input/output contracts |
| Coordination misalignment | agents duplicate work, contradict, or drop information | typed messages + acquaintance model |
| Inappropriate verification | bad output passes through silently | lifecycle gates with explicit checks |

None of these are fixed by better prompt wording. They are fixed by specification. Track how
much of your system is *specified* versus *hoped for*.

### 1.3 The task tuple

Every agent, and every stage, is defined as:

```
T = (I, O, R)
  I — input domain:  an unambiguous description of all admissible inputs
  O — output domain: the exact shape and constraints of valid output
  R — requirements:  the rules a valid output must satisfy
```

If you cannot write `T` for an agent, that agent is not ready to be built. This is the single
highest-leverage artifact in the whole method.

### 1.4 The splitting rule

Split one agent into two **only** when at least one is true:

- The two jobs require **conflicting instructions** (e.g. "be exhaustive" vs "be concise").
- The two jobs require **disjoint tool sets**, and giving both sets to one agent would
  violate least privilege.
- The two jobs need **different model tiers** and the cost difference is material.
- The two jobs need **independent retry**, because one is much more failure-prone.

Do **not** split because two jobs "feel like different roles". Five agents with one tool each
usually perform worse and cost more than one agent with five tools.

### 1.5 Start smaller than feels right

Progression, in order, and you must justify each step up:

```
single prompt → single agent with tools → fixed chain → router → orchestrator-workers → dynamic crew
```

Most real problems stop at "fixed chain" or "router". Reaching for a dynamic crew first is
the most common and most expensive mistake.

---

## 2. Phase 0 — Task specification

**Goal:** describe the work as a procedure a competent human could follow, before any agent exists.

### 2.1 Questions to answer

1. What is the trigger? (schedule, event, human request, webhook)
2. What are the inputs, and where do they come from?
3. What is the deliverable, exactly? Format, length, destination.
4. What does "done correctly" mean? Name at least three measurable criteria.
5. What does failure look like, and who notices?
6. Which steps currently require human judgment, and why?
7. What's the current manual cost (time per run, runs per week)? This is your ROI baseline.
8. What must **never** happen? (published without review, external write, data leaving the box)

### 2.2 Artifact: `specs/00-task-spec.md`

```markdown
# Task specification

## Trigger
<what starts a run>

## Inputs
| Name | Type | Source | Required | Notes |
|---|---|---|---|---|

## Procedure (the SOP)
1. <step a human would perform>
2. ...
   - decision point: <what is decided, on what basis>

## Deliverable
<exact format and destination>

## Definition of done
- [ ] criterion 1 (measurable)
- [ ] criterion 2
- [ ] criterion 3

## Hard constraints (never allowed)
- ...

## Baseline
Manual cost per run: <time>. Runs per week: <n>. Target: <what improvement justifies this project>
```

### 2.3 Gate 0

- [ ] The SOP is detailed enough that a new hire could execute it.
- [ ] Every decision point in the SOP is labelled with what information it depends on.
- [ ] Definition of done is measurable, not "high quality".
- [ ] You know the baseline cost you are trying to beat.

> If the SOP cannot be written, the project is research, not engineering. Reduce scope until
> it can be written.

---

## 3. Phase 1 — Architecture

**Goal:** choose a topology and fix the control boundary.

### 3.1 Topology catalogue

Choose the *simplest* pattern that fits. Composition is allowed — a chain whose third stage
is an agent is normal and good.

| Pattern | Shape | Use when | Cost | Debuggability |
|---|---|---|---|---|
| **Single agent + tools** | one loop, many tools | task is one job with variable means | low | high |
| **Prompt chain** | A → B → C, fixed | steps are known in advance | lowest | highest |
| **Routing** | classify → one specialist | inputs fall into distinct classes | low | high |
| **Parallelization** | fan out → merge | independent subtasks, or voting/ensembling | medium | high |
| **Orchestrator–workers** | planner delegates dynamically | subtasks not known until runtime | high | medium |
| **Evaluator–optimizer** | generator ↔ critic loop | clear quality rubric, iteration helps | medium | medium |
| **Decentralized handoff** | peer agents pass control | distinct domains, conversational | high | low |
| **Debate / ensemble** | N agents argue, judge decides | correctness matters more than cost | very high | low |

Cross-cutting axes to decide explicitly:

- **Coordination topology:** centralized (one orchestrator) / hierarchical (tiers) /
  decentralized (peer-to-peer).
- **Role allocation:** static (fixed set of agents) or dynamic (roles created at runtime).
  Choose static unless you have strong evidence you need dynamic.
- **Execution:** sequential / parallel / mixed.
- **State:** stateless per stage / shared blackboard / per-agent memory.

### 3.2 Drawing the control boundary

Build this table. It is the most important output of the phase.

| Decision | Made by | Why | If wrong, cost |
|---|---|---|---|
| Which specialist handles the request | code (switch on category) | finite known set | low |
| Which sources to search next | model | open-ended | medium |
| Whether the draft is good enough | code, against rubric output | must be auditable | high |
| When to stop iterating | code (counter) | prevents runaway | high |

Rules of thumb:

- **Termination is always code.** Never let a model decide it's finished.
- **Validation is always code**, even if a model produced the judgment — the model emits
  `{pass: bool, issues: []}`, code branches on it.
- **Routing is code** when the classes are known; a cheap classifier model when they aren't.
- **Money and side effects are code-gated.** Model proposes, code disposes.

### 3.3 Artifact: `specs/01-architecture.md`

```markdown
# Architecture

## Chosen topology
<pattern name> — because <reason>

## Rejected alternatives
- <pattern>: rejected because <reason>

## Diagram
<mermaid or ASCII: stages, agents, data flow, gates>

## Control boundary
| Decision | Made by | Why | Cost if wrong |

## State model
- Shared state store: <where>
- Per-agent memory: <scope, TTL>
- What is passed vs. what is looked up

## Non-functional targets
- Latency budget per run:
- Cost budget per run:
- Max concurrency:
- Failure mode: <fail closed / fail open / escalate>
```

### 3.4 Gate 1

- [ ] Topology chosen, alternatives explicitly rejected in writing.
- [ ] Control boundary table complete; termination and validation are on the code side.
- [ ] Every arrow in the diagram has a data shape associated with it (even if TBD).
- [ ] Latency and cost budgets written down.

---

## 4. Phase 2 — Crew design (the role model)

**Goal:** one contract per agent. No prompts yet.

### 4.1 Agent contract template

`specs/agents/_template.yaml`:

```yaml
id: researcher                      # stable identifier, used in code and logs
version: 1
goal: >
  One sentence. What this agent is responsible for producing.
non_goals:                          # explicit scope fence — prevents drift
  - does not write prose
  - does not decide publication

# --- T = (I, O, R) -------------------------------------------------------
input:
  schema: specs/schemas/brief.schema.json
  description: >
    Admissible inputs. Include what is guaranteed present, and what may be null.
  preconditions:
    - topic is non-empty
    - audience is one of [...]

output:
  schema: specs/schemas/research_result.schema.json
  description: >
    Exact output shape. Prefer arrays of objects over prose.
  postconditions:
    - every claim has at least one source_url
    - sources are deduplicated by domain+path

requirements:                       # R — what makes an output valid
  - no claim without a retrievable source
  - prefer primary sources over aggregators
  - flag conflicting evidence rather than resolving it silently

# --- Capability ----------------------------------------------------------
tools:                              # least privilege — only what this role needs
  - web_search
  - fetch_page
  - vector_retrieve
model:
  tier: mid                         # cheap | mid | frontier
  rationale: reasoning over search results, not generation quality
memory:
  scope: run                        # none | run | thread | long-term
  store: none
  rationale: no cross-run context needed

# --- Control -------------------------------------------------------------
max_iterations: 8
timeout_seconds: 180
stop_conditions:
  - output validates against schema
  - max_iterations reached
on_failure:
  action: escalate                  # retry | escalate | fail_closed | degrade
  to: human_review
  retries: 1

# --- Observability -------------------------------------------------------
logs:
  - tool_calls
  - token_usage
  - final_output
eval:
  dataset: evals/researcher.jsonl
  metrics: [source_validity, claim_coverage, cost_per_run]

owner: <person>
```

### 4.2 Filling `non_goals` matters

Most scope creep happens because nobody wrote down what an agent must *not* do. The
`non_goals` list is what lets you catch, in review, that your researcher has started
summarizing and your writer has started fact-checking.

### 4.3 Memory scope discipline

| Scope | Meaning | Use for |
|---|---|---|
| `none` | fresh context every call | deterministic stages |
| `run` | shared within one execution | multi-step agents |
| `thread` | conversational, per user session | chat-facing agents |
| `long-term` | persisted across runs, retrieved | personalization, dedupe, house style |

Long-term memory is a **database design problem**, not an agent feature. Model it with
tables and retrieval, not by growing a context window.

### 4.4 Anti-patterns

- **The persona trap.** "You are a world-class senior journalist with 20 years of
  experience" does far less than a precise output schema. Write contracts, not backstories.
- **The god agent.** One agent with 15 tools and a 2,000-word prompt. Split by conflicting
  instructions, or move logic to code.
- **The nano-agent swarm.** Six agents that each make one model call in a fixed order. That
  is a chain; build it as a chain.
- **Mirroring the org chart.** Agents should mirror the *procedure*, not your company's
  job titles.

### 4.5 Gate 2

- [ ] Every agent has `I`, `O`, `R` written, with schemas referenced (even if draft).
- [ ] Every agent has `non_goals`.
- [ ] Every agent has `max_iterations`, `timeout`, and an `on_failure` action.
- [ ] Tool lists satisfy least privilege — no agent holds a destructive tool it doesn't need.
- [ ] You have argued, in writing, why each agent is not merged with its neighbour.

---

## 5. Phase 3 — Interaction design

**Goal:** define how agents exchange information, who may talk to whom, and how a run ends.

### 5.1 Structured messaging, always

Agents exchange **typed messages**, never free prose. Prose handoffs degrade information
silently and make failures unattributable.

Standard envelope — `specs/schemas/envelope.schema.json`:

```json
{
  "run_id": "uuid",
  "message_id": "uuid",
  "from": "researcher",
  "to": "outliner",
  "type": "result",
  "ts": "2026-09-22T10:00:00Z",
  "attempt": 1,
  "payload": { },
  "payload_schema": "research_result@1",
  "status": "ok",
  "issues": [],
  "cost": { "input_tokens": 0, "output_tokens": 0 },
  "trace": { "parent_message_id": "uuid", "depth": 1 }
}
```

Rules:

- Payloads validate against a versioned schema. Version them (`@1`) from day one.
- `status` is one of `ok | partial | failed`. `partial` is what prevents silent degradation.
- `issues[]` carries machine-readable problems, not apologies in prose.
- `depth` lets you cap delegation depth in code.

### 5.2 Coordination modes

| Mode | Control | Use when | Risk |
|---|---|---|---|
| **Tool call** | caller keeps control, gets result back | most cases | none particular |
| **Handoff** | callee takes over the run | distinct domain owns the rest of the flow | orphaned runs |
| **Blackboard** | agents read/write shared state | many agents need the same evolving artifact | write conflicts |
| **Broadcast/debate** | all see all, judge decides | correctness-critical | cost explosion |

Default to **tool call**. It keeps a single point of control and a clean trace.

### 5.3 Acquaintance matrix

Who may invoke whom. Fill it in; sparsity is a feature.

|  | orchestrator | researcher | outliner | writer | editor | publisher |
|---|---|---|---|---|---|---|
| **orchestrator** | — | ✅ | ✅ | ✅ | ✅ | ⛔ (code-gated) |
| **researcher** | ⛔ | — | ⛔ | ⛔ | ⛔ | ⛔ |
| **editor** | ⛔ | ⛔ | ⛔ | ✅ (one hop) | — | ⛔ |

If this matrix is fully populated, you have built a system you cannot debug.

### 5.4 Lifecycle gates

Between stages, insert explicit verification that code evaluates:

```
stage output → schema validation → rule checks → quality gate → next stage
                     │                  │              │
                   fail            fail          fail
                     ↓                  ↓              ↓
                  retry(1)         escalate      loop back (max 2)
```

Write them down:

| Gate | Checks | Enforced by | On fail |
|---|---|---|---|
| G1 after research | schema valid; ≥5 sources; all URLs resolve | code | retry once, then escalate |
| G2 after draft | length band; required sections present; glossary compliance | code | loop to writer, max 2 |
| G3 before publish | human approval | human | block |

### 5.5 Termination

Every run must have a provable end. Specify:

- max total model calls per run
- max delegation depth
- max wall-clock time
- max cost per run (hard kill)
- what happens to partial work on kill (persist it, always)

### 5.6 Artifact: `specs/03-interaction.md`

Contains: envelope schema reference, coordination mode per edge, acquaintance matrix,
gate table, termination limits, human-in-the-loop points.

### 5.7 Gate 3

- [ ] All inter-agent payloads have JSON schemas, versioned.
- [ ] Acquaintance matrix drawn and deliberately sparse.
- [ ] Every stage boundary has a gate with a named enforcer (code / model / human).
- [ ] Hard termination limits set, including a cost kill-switch.
- [ ] Partial results are persisted on failure.

---

## 6. Phase 4 — Prompt design

**Goal:** generate each agent's prompt *from* its contract. The prompt is an implementation
detail of the contract, not the other way round.

### 6.1 Prompt anatomy

Fixed order. Deviating costs you reliability.

```markdown
# 1. Identity and scope
You are the <role>. You are responsible for <goal>.
You do not <non_goals, as a list>.

# 2. Input contract
You will receive: <description of input + schema summary>.
If a required field is missing or malformed, do not guess — return status "failed"
with an issue of type "bad_input".

# 3. Procedure
Follow these steps in order:
1. ...
2. ...
(derived from the Phase 0 SOP, narrowed to this role)

# 4. Tool policy
Available tools: <list>.
- Use <tool> when <condition>.
- Do NOT use <tool> for <anti-condition>.
- Never call more than <n> tools before producing output.
- If a tool fails twice, stop and return status "partial".

# 5. Output contract
Return ONLY JSON matching this schema:
<schema>
No prose, no markdown fences, no explanation.

# 6. Quality requirements
<the R list from the contract, as checkable rules>

# 7. Escalation
If <condition>, return status "failed" with issue code <code>. Do not attempt to
work around it.

# 8. Examples
<2–3 input→output pairs, including at least one failure case>
```

### 6.2 Shared block

Put everything global in `prompts/_shared.md` and inject it into every agent: house rules,
terminology conventions, formatting conventions, refusal rules, date handling. One place to
change, all agents updated.

### 6.3 Practical rules

- **Negative examples beat adjectives.** One "here is a bad output and why" is worth a
  paragraph of "be thorough and accurate".
- **A long prompt is a design smell.** It usually means a missing tool, a missing schema,
  or a missing split.
- **Tool descriptions are prompts.** The model chooses tools from their descriptions; write
  them with the same care as the system prompt.
- **Never encode hard rules in prose.** Anything that can be checked by code (terminology
  lists, length bands, required fields, banned phrases) is checked by code, not asked for
  politely in a prompt.
- **Version prompts as files**, referenced by the workflow. Never edit prompts only inside
  the n8n UI — export and commit.

### 6.4 Gate 4

- [ ] Each prompt maps 1:1 to an agent contract, and contains all eight sections.
- [ ] Output schema appears verbatim in the prompt and is enforced by a parser downstream.
- [ ] Shared rules live in exactly one file.
- [ ] At least one failure-case example per agent.
- [ ] No rule in a prompt that could have been a code check.

---

## 7. Phase 5 — Tool design

**Goal:** a registry of capabilities with explicit privilege and failure semantics.

### 7.1 Tool spec template

`specs/tools/_template.yaml`:

```yaml
id: web_search
description: >
  THIS IS A PROMPT. The model reads this to decide when to call the tool.
  Say what it does, what it returns, and when NOT to use it.
  e.g. "Search the public web for recent sources on a topic. Returns up to 10
  results with title, url, snippet. Use for facts after <cutoff>. Do not use to
  fetch a page you already have a URL for — use fetch_page."
parameters:
  type: object
  properties:
    query: { type: string, maxLength: 200 }
    recency_days: { type: integer, minimum: 1, maximum: 365 }
  required: [query]
returns:
  schema: specs/schemas/search_results.schema.json
side_effect: read            # read | write | destructive | spend
auth: api_key:TAVILY
rate_limit: 60/min
timeout_seconds: 20
cost_per_call: 0.005
errors:
  - code: rate_limited     -> behavior: backoff, then return partial
  - code: no_results       -> behavior: return empty array, not an error
  - code: upstream_5xx     -> behavior: retry once, then partial
allowed_roles: [researcher]  # least privilege
idempotent: true
```

### 7.2 Side-effect classes and gating

| Class | Examples | Gate |
|---|---|---|
| `read` | search, fetch, query DB | none |
| `write` | create draft, insert row | schema validation |
| `destructive` | delete, overwrite, send email | human approval or code-only |
| `spend` | paid API, ads, purchases | hard budget cap in code |

**No agent may hold a `destructive` tool.** Expose an intent instead: the agent emits
`{"action":"publish","target":...}`, code validates and executes it.

### 7.3 Tool design rules

- Prefer **few, well-described tools** over many narrow ones. Tool-choice accuracy degrades
  sharply past roughly a dozen options per agent.
- Every tool returns a **typed result**, including on failure. Never return a raw stack trace
  into a model's context.
- Make tools **idempotent** where possible, and pass a run-scoped key so retries don't
  duplicate work.
- A tool that returns 50 KB of text will wreck your context budget. Paginate and summarize
  at the tool boundary, not in the agent.

### 7.4 Gate 5

- [ ] Registry complete: every tool has description, params, returns, errors, side-effect class.
- [ ] `allowed_roles` set for every tool; least privilege verified against agent contracts.
- [ ] No agent holds a destructive tool.
- [ ] Spend tools have a hard cap enforced in code.
- [ ] Tool outputs are size-bounded.

---

## 8. Phase 6 — Evaluation and operation

**Goal:** know whether it works, and know when it stops working.

### 8.1 Build the golden set before scaling

`evals/dataset.jsonl`, 20–50 cases minimum:

```json
{"id": "001", "input": {...}, "expected": {...}, "rubric": ["has >=5 sources", "no paywalled"], "tags": ["easy"]}
{"id": "017", "input": {...}, "expected_status": "failed", "rubric": ["rejects empty topic"], "tags": ["adversarial"]}
```

Include: typical cases, edge cases, adversarial inputs, and cases that *should fail*. A crew
that never refuses is a crew that hallucinates.

### 8.2 Two levels of evaluation

- **Per-agent:** does each agent satisfy its own contract in isolation? Cheap, fast, run on
  every prompt change.
- **End-to-end:** does the crew produce the deliverable? Slower, run before release.

These are not substitutes. **A crew can fail while every agent passes** — that's coordination
failure, and only end-to-end evaluation catches it.

### 8.3 Failure taxonomy

Classify every failure. Fixes should be structural, not prompt-patching.

| Class | Example | Structural fix |
|---|---|---|
| Specification | agent produced the wrong kind of thing | tighten `I/O/R` |
| Coordination | two agents did the same work | acquaintance matrix, orchestrator prompt |
| Information loss | detail present at stage 2, gone at stage 4 | typed payloads, stop summarizing between stages |
| Verification | bad output passed the gate | add a code check |
| Termination | loop ran 40 times | iteration cap |
| Tool | model called the wrong tool | rewrite tool description |
| Grounding | fabricated a source | make the tool the only allowed source of facts |

### 8.4 Tracing

Log per run, to a table you can query:

```
run_id, stage, agent_id, agent_version, prompt_version, model, input_tokens,
output_tokens, cost, latency_ms, tool_calls (json), status, issues (json), ts
```

You will want this within the first week of real use. Add it before you need it.

### 8.5 Operating checklist

- [ ] Cost per run tracked, with an alert threshold and a hard kill.
- [ ] Prompt and contract versions recorded in every trace row.
- [ ] Model versions **pinned**; a provider-side model update is a silent regression.
- [ ] Eval suite runs on every prompt change (CI if possible).
- [ ] Human-in-the-loop for anything published externally.
- [ ] A rollback path: previous workflow JSON + previous prompts, both in git.
- [ ] Dead-letter path for failed runs, with the partial output preserved.

---

## 9. Implementation in n8n (self-hosted)

### 9.1 Mapping design artifacts to n8n

| Design artifact | n8n implementation |
|---|---|
| Agent (role model) | one workflow per agent, **Execute Workflow trigger** |
| Agent contract → prompt | AI Agent node system prompt (content pulled from `prompts/`) |
| Output contract | Structured Output Parser sub-node + a code-level schema validation step |
| Acquaintance matrix | which sub-workflows are attached to which agent as **Call n8n Workflow Tool** |
| Tool registry | tool sub-nodes / HTTP Request Tool, one per registry entry |
| Blackboard / shared state | Postgres tables keyed by `run_id` |
| Agent memory (`thread`) | Postgres Chat Memory sub-node |
| Lifecycle gates | IF / Switch nodes, Code nodes — never model judgment alone |
| Termination limits | agent `maxIterations` + explicit counters in the orchestrator loop |
| Human-in-the-loop | Wait node with webhook resume, or Form/Slack approval |
| Tracing | a Code/Postgres node after every stage writing the trace row |
| Versioning | export workflow JSON to `workflows/` and commit |

### 9.2 Node-level notes

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

### 9.3 Self-hosted configuration

- Run n8n in Docker with Postgres as the n8n database. Add a **second database or schema**
  for your crew's state — don't mix application state into n8n's internal tables.
- Enable execution-data pruning from day one (`EXECUTIONS_DATA_PRUNE`,
  `EXECUTIONS_DATA_MAX_AGE`). Agent executions store every reasoning step; the DB grows fast.
- Enable task runners for the Code node.
- Queue mode (`EXECUTIONS_MODE=queue` + Redis) only once you actually run stages in parallel.
- pgvector in the same Postgres is usually enough for retrieval and dedupe; add a dedicated
  vector DB only when corpus size demands it.
- Store credentials in n8n's credential store, referenced by name; never inline keys in nodes.
- Back up: Postgres dump + `workflows/` in git + the encryption key. All three, or none work.

### 9.4 State tables (starting point)

```sql
create table runs (
  run_id uuid primary key,
  trigger_type text not null,
  input jsonb not null,
  status text not null default 'running',   -- running|done|failed|cancelled
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  total_cost numeric default 0
);

create table stage_traces (
  id bigserial primary key,
  run_id uuid references runs(run_id),
  stage text not null,
  agent_id text not null,
  agent_version int,
  prompt_version text,
  model text,
  input_tokens int, output_tokens int, cost numeric, latency_ms int,
  tool_calls jsonb, status text, issues jsonb,
  created_at timestamptz default now()
);

create table artifacts (
  id bigserial primary key,
  run_id uuid references runs(run_id),
  stage text not null,
  payload jsonb not null,
  payload_schema text not null,
  created_at timestamptz default now()
);
```

`artifacts` is what lets you resume a failed run from the last good stage instead of
re-running the whole crew.

---

## 10. Phase gate summary

| Phase | Artifact | Gate passes when |
|---|---|---|
| 0 Specification | `specs/00-task-spec.md` | SOP executable by a human; done is measurable |
| 1 Architecture | `specs/01-architecture.md` | topology chosen; control boundary drawn; budgets set |
| 2 Crew design | `specs/agents/*.yaml` | every agent has I/O/R, non-goals, limits, failure action |
| 3 Interaction | `specs/03-interaction.md` + schemas | typed payloads; sparse acquaintance matrix; gates named |
| 4 Prompts | `prompts/*.md` | prompts generated from contracts; shared block factored |
| 5 Tools | `specs/tools/registry.md` | least privilege; no destructive tools held by agents |
| 6 Evaluation | `evals/` + tracing | golden set exists; per-agent and e2e both run |

Build order, once gates are passed: **thinnest end-to-end path first** (trigger → one model
call → output), run it on real inputs 10 times, then add stages one at a time, re-running
evals after each. Add the orchestrator last, not first.

---

## 11. Worked skeleton — research/content crew

An illustration of the method applied, not a prescription.

```
trigger (brief)
  └─ code: validate brief, create run_id, write runs row
  └─ AGENT researcher            [tools: web_search, fetch_page, vector_retrieve]
       → research_result@1
  └─ GATE G1: schema + >=5 sources + URLs resolve        (code)
  └─ code: dedupe claims vs covered_topics (embeddings)  (no model)
  └─ LLM outliner (no tools)     → outline@1
  └─ GATE G2: section count, required sections           (code)
  └─ loop over sections:
       └─ LLM writer (no tools)  → section@1
  └─ LLM editor                  → {pass, issues[]}
  └─ GATE G3: if !pass and attempts<2 → loop to writer   (code counter)
  └─ code: terminology/glossary check against DB table   (no model)
  └─ HUMAN approval (Wait node)
  └─ publish (code-executed intent, not an agent tool)
```

Notes on why it is shaped this way:

- Only **one** true agent (the researcher) — it's the only stage whose next action depends on
  what it just found. Everything else is a fixed chain, which is cheaper and far easier to
  debug.
- Dedupe and terminology compliance are **code**, because they are checkable rules; models
  drift on exactly this kind of constraint.
- The editor produces a **judgment object**, and code decides what to do with it.
- Publishing is never an agent-held tool.

---

## 12. Reading list

**Classical agent-oriented software engineering** — still the best source for role and
interaction modelling:

- **Gaia** — roles model, interactions model; then agent, services and acquaintance models.
- **Prometheus** — system specification → architectural design → detailed design.
- **Tropos** (goal-oriented), **MaSE** (organization-oriented).

**LLM-era practice:**

- Anthropic, *Building Effective Agents* — the pattern catalogue (chaining, routing,
  parallelization, orchestrator-workers, evaluator-optimizer, autonomous agents).
- OpenAI, *A Practical Guide to Building Agents* — single-agent-first, manager vs handoff.
- MetaGPT — encoding human SOPs as agent roles.
- CrewAI docs — role/goal/backstory + tasks + sequential/hierarchical process, useful as a
  design template regardless of implementation.

**Research worth reading before you scale:**

- **SEMAP** — behavioral contracts, structured messaging, lifecycle-guided execution with
  verification, as a protocol layer.
- **MAST** (Multi-Agent System Failure Taxonomy) — use as a pre-mortem checklist.
- **"Know the Ropes"** — decompose a known procedure into stages, each a well-formulated
  task `T = (I, O, R)`.
- Surveys of multi-agent orchestration comparing LangGraph / CrewAI / AutoGen / OpenAI
  Agents SDK / MetaGPT / DSPy on state granularity, token cost, and failure recovery.

---

## 13. Glossary

| Term | Meaning here |
|---|---|
| **Agent** | a model call loop that can choose tools and iterate |
| **Chain** | fixed sequence of model calls, no choice |
| **Crew** | a set of agents coordinating toward one deliverable |
| **Contract** | the `I/O/R` specification of an agent, in `specs/agents/` |
| **Control boundary** | the line between code-made and model-made decisions |
| **Gate** | a code-enforced check between stages |
| **Envelope** | the typed message wrapper passed between agents |
| **Acquaintance matrix** | who may invoke whom |
| **Blackboard** | shared state store all agents can read/write |
| **Golden set** | curated evaluation dataset with expected outputs |
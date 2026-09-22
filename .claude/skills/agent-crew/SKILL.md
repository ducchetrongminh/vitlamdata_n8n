---
name: agent-crew
description: >
  Phased methodology (task spec, architecture, agent contracts, interaction design, prompts,
  tools, evaluation) for designing and building a new multi-agent LLM system as an n8n crew in
  this repo, with a mapping of every design artifact to real n8n nodes, NocoDB state tables,
  and this repo's credentials/scripts conventions. Use whenever the user wants to design, plan,
  spec out, or build a new AI agent, agent crew, agent system, orchestrator, chatbot, or
  multi-agent workflow — even if they don't say "crew" or "methodology" explicitly, e.g. "I
  want an agent that monitors X and posts to Y", "help me design a research bot for Lark",
  "add a new automation with an LLM step", "should this be one agent or two". Also use when
  extending or reviewing an existing crew under `crews/<crew_name>/` or `workflows/<crew_name>/`.
---

# Building an AI agent crew

A phased method for designing, building and operating a multi-agent LLM system, mapped to
this repo's n8n instance. It is both a method and a set of fill-in templates (in `assets/`).

## How to use this

This repo hosts multiple crews, not one. A crew's blueprint lives in `crews/<crew_name>/`,
its built n8n workflows in `workflows/<crew_name>/` (per `CLAUDE.md`'s loop: edit the file,
`scripts/push.sh`). `crews/` is design — diagrams, contracts, prompts, evals — none of it
runs. `workflows/` is what actually runs.

When the user wants to build something agent-shaped, find out which crew this is (existing or
new) and which phase they're at, then work through that phase: ask the questions listed under
it, produce the phase's artifact into `crews/<crew_name>/`, and stop at the phase gate for
approval before moving on. Don't skip ahead to implementation (writing prompts or n8n JSON)
before the phase that produces it.

Rules:

1. **Never generate agent prompts before the agent contracts in `crews/<crew_name>/02-agents/`
   exist.** A prompt written before a contract is a guess.
2. **Every artifact is a file in the repo**, not a message in the chat. The repo is the
   source of truth.
3. **Phase gates are hard.** Do not start Phase N+1 until the Phase N checklist passes.
4. When a design question has no clear answer, write it into
   `crews/<crew_name>/open-questions.md` rather than inventing an answer.
5. Prefer removing an agent over adding one. Argue for the smaller system.
6. Before writing a tool spec or a node-level note, check `CLAUDE.md`'s Nodes / DeepSeek /
   Lark / Facebook sections for a quirk already verified on this instance — don't re-derive it.

### Repo layout

```
.
├── CLAUDE.md                    # instance rules, scripts, verified API/node quirks
├── .claude/skills/agent-crew/   # this skill — the method, shared by every crew
├── crews/
│   └── <crew_name>/             # blueprint — nothing here runs
│       ├── 00-task-spec.md      # Phase 0 — the SOP
│       ├── 01-architecture.md   # Phase 1 — topology + control boundary
│       ├── 02-agents/
│       │   └── researcher.yaml  # Phase 2 — one contract per agent
│       ├── 03-interaction.md    # Phase 3 — protocol, acquaintance matrix
│       ├── 03-schemas/
│       │   ├── envelope.schema.json
│       │   └── research_result.schema.json
│       ├── 04-prompts/
│       │   ├── _shared.md       # global rules injected into every agent
│       │   └── researcher.md    # Phase 4 — one per agent, generated from its contract
│       ├── 05-tools/
│       │   └── registry.md      # Phase 5 — tool registry
│       ├── 06-evaluation.md     # Phase 6 — eval plan
│       ├── 06-evals/
│       │   ├── dataset.jsonl    # golden set
│       │   └── rubrics/
│       ├── decisions/           # ADRs, one per irreversible choice, ongoing
│       └── open-questions.md    # ongoing
├── workflows/
│   └── <crew_name>/             # built — exported n8n JSON, source of truth for n8n
├── nocodb/                      # shared/blackboard state and run traces, if the crew needs them
├── credentials/
└── scripts/
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

### 2.2 Artifact: `crews/<crew_name>/00-task-spec.md`

Copy `assets/task-spec-template.md` as the starting point.

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

### 3.3 Artifact: `crews/<crew_name>/01-architecture.md`

Copy `assets/architecture-template.md` as the starting point.

### 3.4 Gate 1

- [ ] Topology chosen, alternatives explicitly rejected in writing.
- [ ] Control boundary table complete; termination and validation are on the code side.
- [ ] Every arrow in the diagram has a data shape associated with it (even if TBD).
- [ ] Latency and cost budgets written down.

---

## 4. Phase 2 — Crew design (the role model)

**Goal:** one contract per agent. No prompts yet.

### 4.1 Agent contract

One file per agent at `crews/<crew_name>/02-agents/<id>.yaml`. Copy
`assets/agent-contract-template.yaml` as the starting point — it has the full field set
(`T = (I, O, R)`, tools, model tier, memory scope, iteration/timeout limits, `on_failure`,
observability, eval) with comments explaining each.

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
silently and make failures unattributable. Every message follows the envelope in
`assets/envelope.schema.json` (`run_id`, `from`, `to`, `type`, `payload`, `payload_schema`,
`status: ok|partial|failed`, `issues[]`, `cost`, `trace.depth`) — copy it to
`crews/<crew_name>/03-schemas/envelope.schema.json` and version payload schemas from day one
(`research_result@1`).

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

### 5.6 Artifact: `crews/<crew_name>/03-interaction.md`

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

Fixed order — identity/scope, input contract, procedure, tool policy, output contract,
quality requirements, escalation, examples. Deviating costs you reliability. Copy
`assets/prompt-template.md` and fill it from the agent's `crews/<crew_name>/02-agents/<id>.yaml`.

### 6.2 Shared block

Put everything global in `crews/<crew_name>/04-prompts/_shared.md` and inject it into every
agent: house rules, terminology conventions, formatting conventions, refusal rules, date
handling. One place to change, all agents updated.

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

### 7.1 Tool spec

One entry per tool in `crews/<crew_name>/05-tools/registry.md`. Copy
`assets/tool-spec-template.yaml` as the starting point for each — description (a prompt: what
it does, what it returns, when NOT to use it), parameters, returns schema, `side_effect`
class, auth, rate limit, timeout, cost, per-error behavior, `allowed_roles`, idempotency.

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

`crews/<crew_name>/06-evals/dataset.jsonl`, 20–50 cases minimum:

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
- [ ] A rollback path: previous `workflows/<crew_name>/<id>.json` + previous `crews/<crew_name>/04-prompts/`, both in git.
- [ ] Dead-letter path for failed runs, with the partial output preserved.

---

## 9. Implementation in n8n

See `references/n8n-mapping.md` for the full mapping of every design artifact to n8n nodes
(AI Agent, Call n8n Workflow Tool, Structured Output Parser, ...), node-level quirks, and how
to model shared state and tracing in NocoDB rather than a hand-rolled Postgres schema.

---

## 10. Phase gate summary

| Phase | Artifact | Gate passes when |
|---|---|---|
| 0 Specification | `crews/<crew_name>/00-task-spec.md` | SOP executable by a human; done is measurable |
| 1 Architecture | `crews/<crew_name>/01-architecture.md` | topology chosen; control boundary drawn; budgets set |
| 2 Crew design | `crews/<crew_name>/02-agents/*.yaml` | every agent has I/O/R, non-goals, limits, failure action |
| 3 Interaction | `crews/<crew_name>/03-interaction.md` + `03-schemas/` | typed payloads; sparse acquaintance matrix; gates named |
| 4 Prompts | `crews/<crew_name>/04-prompts/*.md` | prompts generated from contracts; shared block factored |
| 5 Tools | `crews/<crew_name>/05-tools/registry.md` | least privilege; no destructive tools held by agents |
| 6 Evaluation | `crews/<crew_name>/06-evals/` + tracing | golden set exists; per-agent and e2e both run |

Build order, once gates are passed: **thinnest end-to-end path first** (trigger → one model
call → output), run it on real inputs 10 times, then add stages one at a time, re-running
evals after each. Add the orchestrator last, not first.

A worked example of the method applied to a research/content crew is in
`references/worked-skeleton.md`. Further reading and a glossary of terms used throughout are
in `references/reading-list.md`.

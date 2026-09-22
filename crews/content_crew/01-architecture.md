# Architecture

From `00-task-spec.md`. Nothing here runs; the built workflows will live in
`workflows/content_crew/`.

## Chosen topology

**One agent with tools, surrounded by code paths.**

The only open-ended job in the whole SOP is reading what the owner sent — free-form Vietnamese,
often with a screenshot, sometimes an idea, sometimes a story, sometimes "sửa lại bài #3". That
is one job, done by one agent with a small tool set. Everything else in the SOP is a procedure
with known steps, so it is code: the access check in front of the agent, the offer cadence, the
rework counter, the approval gate, the scheduler, the outcome checks.

Two fixed chains sit beside the agent, each a model call inside a procedure rather than an agent:

- **Scouting digest** — search (Tavily) → summarize → send to Lark. Fixed steps, no judgment
  about what to do next.
- **Pre-publish check** — one call with the Relevant/Closer/Connected rubric, returning
  `{pass, issues[]}`. A separate call, not the writing agent reviewing itself, because a
  reviewer that shares the writer's context agrees with it.

The agent writes the post itself. Writing is what the model does natively; a "writer agent"
behind a tool would add a hop and a handoff without adding judgment.

## Rejected alternatives

- **Fixed pipeline, no agent** (trigger → classify → draft → image → publish): rejected. The
  owner's input is deliberately unstructured — that is the point of dropping ideas as they come.
  Code that decides what a message means will be wrong exactly on the messages that matter.
- **Crew of specialists** (researcher / writer / editor / publisher): rejected. Apply the
  splitting rule and nothing splits. They share one tool set, one model tier, one voice, and the
  handoffs between them would be prose — the cheapest way to lose the owner's idea in transit.
  Four agents in a fixed order is a chain wearing a costume.
- **Orchestrator–workers**: rejected. Subtasks are known in advance (draft, image, check); there
  is nothing for a planner to plan.
- **Evaluator–optimizer as two agents**: rejected as a topology, kept as a step. The check is one
  call in a code-counted loop (max one rework), not an agent in a conversation with another
  agent.
- **Decentralized handoff**: rejected. One domain, one owner, one chat.

## Diagram

```
Lark ──► lark (webhook, answers Lark at once)
          ├─ card click ────────► code: approve / reject, queue for a slot
          └─ message ─► GATE (code): is it for the bot? fetch thread + pictures
                          AGENT (deepseek-flash, sees the pictures)
                            ├─ save_idea ─────────► ideas
                            ├─ writes the draft ─► save_draft ─► CHECK (model: pass/issues)
                            │                                     ├─ pass ─► posts + approval card
                            │                                     └─ fail ─► back to the agent, once
                            ├─ make_image ───────► OpenRouter ──► posts
                            └─ reads: calendar, ideas, outcomes
Schedules (code):
  scout      ─► Tavily ─► summarize ─► digest to Lark
  publisher  ─► approved posts whose slot has come ─► Facebook
  outcomes   ─► posts due 2h / 24h / 7d ─► Facebook insights ─► outcomes
```

Provisional workflow split (firmed up at build time): `lark` (webhook, gate, agent, reply),
`tools` (every tool behind one Switch), `lark send`, `scout`, `publisher`, `outcomes`, `errors`.
The gate and the agent share a workflow so pictures never have to be passed between workflows.

## Data on the arrows

Shapes are named here and specified in Phase 3 (`03-schemas/`).

| Arrow | Carries |
|---|---|
| Lark → gate | Lark event (message id, chat, sender, thread, image keys) |
| gate → agent | `task`: message text, thread history with names, picture binaries, ids of the post/idea the thread is about |
| agent → tool | one `$fromAI` argument per field, never a JSON blob in a string |
| `save_draft` → check | `{post_id, content_type, text, idea}` |
| check → code | `{pass: bool, issues: [{point, why}]}` |
| code → approval card | `{post_id, text, image, content_type, scheduled_for, check}` |
| card click → code | `{post_id, action: approve|reject, actor}` |
| publisher → Facebook | `{message, attached_media}` (page feed) |
| Facebook → `outcomes` | `{post_id, checkpoint, reach, reactions, comments, shares}` |
| scout → digest | `{items: [{title, url, why_it_matters, hook}]}` |

## Control boundary

| Decision | Made by | Why | Cost if wrong |
|---|---|---|---|
| Does this Lark message concern the bot | code | finite rules (sender, mention, thread, `/`); group chatter must not reach a model | low — owner repeats it |
| What the owner's message means | model | free-form text plus pictures; the input space is the point | medium — wrong action, corrected in chat |
| Which content type (observation / story / education / offer) | model, within the strategy | judgment about this idea against the current mix | medium |
| May an offer post be created now | code (two per month, from `docs/Content Strategy.md`) | a cadence rule the strategy calls non-negotiable | high — the strategy says this trades long-term goodwill |
| Is the draft publishable (Relevant / Closer / Connected) | model judges, code branches | rubric judgment, auditable branch | medium — the owner still sees it |
| How many rework loops | code (counter, max 1) | never let a model decide it is finished | high — cost and latency runaway |
| Does this post go live | **human** (owner approves the card) | hard constraint in the task spec | very high — irreversible public post |
| When an approved post goes live | code (slot table in `settings`) | deterministic scheduling | low/medium — weaker reach |
| Which slots are good | human, from the outcome numbers in the digest | test-and-learn; no optimizer in v1 | low |
| When to pull outcomes | code (2h / 24h / 7d from `published_at`) | fixed offsets | low |
| What to search for, and what is worth the digest | model | open-ended | low — a dull digest |
| When the agent stops | code (max steps, timeout) | termination is always code | high |

The agent holds **no publishing tool at all**. It proposes; the card click and the publisher
dispose. Same for spending: image generation is the only paid tool and it is called once per
post, from a tool whose code caps it.

## State model

NocoDB base `content_crew` (tables defined later as `nocodb/content_crew/*.json`):

- **`posts`** — the idea it came from, content type, draft text, image, status
  (`drafting|needs_owner|approved|scheduled|published|failed|rejected`), `scheduled_for`,
  `fb_post_id`, `published_at`, check result, rework count.
- **`ideas`** — captured inspiration: theme, hook, angle, source link or picture, the owner's
  note. The bank the agent draws from when it needs something to write.
- **`outcomes`** — one row per checkpoint: post, `2h|24h|7d`, reach, reactions, comments, shares,
  taken at. Rows rather than columns because the checkpoints repeat and the digest queries them.
- **`settings`** — Lark ids, posting slots, scouting topics and cadence. What the owner changes
  without a deploy.

No run/trace tables in v1: `GET /executions?workflowId=` already answers "what happened", and
the method says add tracing when evaluation needs it (Gate 6).

Memory: **thread scope, fetched not stored.** The gate reads the Lark thread (last N messages)
and passes it in with the pictures. The thread is already the record of the conversation, so no
chat-memory node and no memory table. Nothing persists between unrelated conversations except
the four tables above.

Passed vs looked up: the message, thread and pictures are **passed** on the item; the strategy,
the owner's voice and the procedures are **in the system prompt**, built in code from
`crews/content_crew/04-prompts/` and versioned in git; posts, ideas, outcomes and settings are
**looked up** through tools.

Concurrency is free and wanted: each Lark message is its own n8n execution, so an idea dropped
while another draft is being written runs in parallel and cannot be lost. That satisfies the
task spec's "never drop an idea" without any queue machinery.

## Non-functional targets

- **Latency.** Plain chat answer under 30s. A draft turn (write + image + check) under 3
  minutes. No "đang viết…" acknowledgement in v1 — add one if draft turns routinely pass a
  minute of silence.
- **Cost.** Provisional, to verify once built: under $0.02 per chat turn, under $0.15 per post
  end to end (draft + check + one generated image). `deepseek-flash` everywhere to start; it is
  the only DeepSeek model with vision and the pictures arrive in chat. **First upgrade lever:**
  if drafts read thin, move only the drafting call to `deepseek-v4-pro` (4-7x the cost, no
  vision, so the agent would describe the picture and pass a brief).
- **Concurrency.** Unbounded per message; posts are independent rows.
- **Failure mode.** Fail closed on publishing: any error, any uncertainty, nothing goes out.
  Everything else escalates to Lark through an error workflow, with partial work left in `posts`
  so a failed draft is still there to look at.
- **Model pinning.** Model names are set per node and committed, so a provider-side change is a
  visible diff rather than a silent regression.

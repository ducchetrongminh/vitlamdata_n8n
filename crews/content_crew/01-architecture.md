# Architecture

From `00-task-spec.md`. Nothing here runs; the built workflows will live in
`workflows/content_crew/`.

## Chosen topology

**One agent, one chain, and code around both.**

The crew proposes work rather than waiting for it. Every day, code fills an idea bank (search),
picks what to write, and runs a writing chain per idea; each finished post arrives in Lark as a
card the owner approves or kills in seconds. The owner can also drop an idea at any time and get
a post out of the same chain.

What reaches a card is a finished post, not a draft. The crew is not allowed to aim at "good
enough, they'll fix it": the owner's job on the card is to judge, not to rewrite.

Three jobs need a model with judgment:

- **Chat agent** — reads what the owner sends: free-form Vietnamese, screenshots, corrections,
  ideas, questions. The one genuinely open input in the system, so the one agent with tools.
- **Writing chain** — one idea in, one finished post out: write → image → check. The steps are
  known in advance, so this is a chain of model calls with code between them, not an agent. It
  is called from two places (the daily batch and the chat agent), which is why it is its own
  thing.
- **Weekly review** — reads the last weeks' posts against their outcomes and writes what it
  learned into `lessons`, which go back into the writing and selection prompts. This is the loop
  that makes the numbers matter; without it `outcomes` is a table nobody reads.

Everything else is code: the access check, the mix and cadence rules, the rework counter, the
approval gate, the scheduler, the outcome checks, and the caps on what the review may write.

## Rejected alternatives

- **Owner-initiated only** (nothing happens until the owner writes): rejected. The task spec's
  bottleneck is the owner's time, and a system that waits inherits it. Cadence has to be the
  crew's job, judgment the owner's.
- **Crew of specialists** (researcher / writer / editor / publisher): rejected. Nothing splits
  under the splitting rule — they would share one tool set, one model tier and one voice, and
  hand each other prose. Four agents in a fixed order is a chain wearing a costume.
- **Writing as a second agent**: rejected. Write, image, check is a fixed sequence. An agent
  there would only be deciding what it was always going to do next, at tool-calling prices.
- **Orchestrator–workers**: rejected. Subtasks are known in advance; there is nothing to plan.
- **Digest to the owner as a separate message**: rejected. The cards are the digest. A morning
  list of links the owner must read is the manual browsing step rebuilt.

## Diagram

```
CRON (four schedule triggers, one workflow)
  scout      ─► web search over the standing topics ─► ideas (source: scout)
  propose    ─► select today's ideas (1 call; code applies the mix and cadence rules)
                  └─ loop, one per idea ─► WRITE ─► card in Lark
  publish    ─► approved posts whose slot has come ─► Facebook
  outcomes   ─► posts due 2h / 24h / 7d ─► Facebook insights ─► outcomes
  review     ─► posts + their outcomes + active lessons (weekly)
                  ├─ lessons: written, retired (code caps the count and demands evidence)
                  ├─ slots: adjusted, once a slot has enough posts behind it
                  └─ report ─► Lark

OWNER (lark webhook)
  card click ─► code: approve ─► queue for the next slot | reject ─► closed
  message ───► GATE (code: is it for the bot; fetch thread and pictures)
                 CHAT AGENT (vision)
                   ├─ saves an idea, corrects a post, answers, reads the bank
                   └─ write(idea) ─────────────► WRITE ─► card in Lark

WRITE (one idea in, one finished post out)
  write (model, JSON: text + image prompt + content type)
    │                                    ▲
    ▼                                    │ one rewrite, counted in code
  image (OpenRouter) ─► check (model: {pass, issues})
                              └─ pass ─► posts + Lark card
                              └─ fail twice ─► card anyway, with the failing point named
```

## Data on the arrows

Shapes are named here and specified in Phase 3 (`03-schemas/`).

| Arrow | Carries |
|---|---|
| Lark → gate | Lark event (message id, chat, sender, thread, image keys) |
| gate → chat agent | message text, thread history with names, picture binaries, the post or idea the thread is about |
| chat agent → tool | one `$fromAI` argument per field, never a JSON blob in a string |
| select → write | `{idea_id, content_type, why_today}` |
| write → code | `{text, image_prompt, content_type, idea_id}` |
| check → code | `{pass: bool, issues: [{point, why}]}` |
| write → card | `{post_id, text, image, content_type, scheduled_for, check}` |
| card click → code | `{post_id, action: approve\|reject, actor}` |
| publisher → Facebook | `{message, attached_media}` |
| Facebook → outcomes | `{post_id, checkpoint, reach, reactions, comments, shares}` |

## Control boundary

| Decision | Made by | Why | Cost if wrong |
|---|---|---|---|
| Does this Lark message concern the bot | code | finite rules (sender, mention, thread, `/`); group chatter must not reach a model | low — owner repeats it |
| What the owner's message means | model | free-form text plus pictures; the input space is the point | medium — corrected in chat |
| What to search for | model, from the standing topics in `settings` | open-ended | low — a dull bank |
| Which ideas are worth banking | model | open-ended | low |
| How many posts to write today, and the mix | code (quota in `settings`, offer cadence from the strategy) | a cadence rule the strategy calls non-negotiable | high — the strategy says over-selling costs goodwill |
| Which ideas fill today's quota | model (one call, returns ids + why) | judgment about what fits now | low — the owner kills the card |
| Content type and text | model | the writing itself | medium — the owner kills the card |
| Is the post publishable (Relevant / Closer / Connected) | model judges, code branches | rubric judgment, auditable branch | medium — the owner still sees it |
| How many rewrite loops | code (counter, max 1) | termination is never the model's call | high — cost and latency runaway |
| Does this post go live | **human** (owner approves the card) | hard constraint in the task spec | very high — irreversible public post |
| When an approved post goes live | code (slot table in `settings`) | deterministic scheduling | low/medium — weaker reach |
| When to pull outcomes | code (2h / 24h / 7d from `published_at`) | fixed offsets | low |
| What the numbers mean (what worked, what to change) | model, weekly | judgment over evidence | medium — a wrong lesson skews the writing until the next review retires it |
| Whether a lesson may be written | code (max 10 active, one claim each, evidence field must name real posts) | small n invents patterns; the caps are what keep it honest | high — an unbounded self-edited prompt drifts with no way back |
| Which slots are good | model proposes, code applies only once a slot has enough posts behind it | test-and-learn, with a floor against noise | low |
| When the chat agent stops | code (max steps, timeout) | termination is always code | high |

The agent holds **no publishing tool**. It proposes; the card click and the publisher dispose.
Image generation is the only paid call, and the writing chain makes it once per post — code
decides it happens, not a model.

## Workflows (4)

| Workflow | Trigger | Holds |
|---|---|---|
| `Content crew: lark` | webhook | Lark verification, card clicks, the gate, the chat agent, the reply |
| `Content crew: write` | called | write → image → check → save → card. Attached to the chat agent as a workflow tool, and called in a loop by cron |
| `Content crew: cron` | schedule ×4 | scout + propose (daily), publish + outcome checks (frequent), review (weekly). One trigger node per cadence, each feeding its own branch, rather than one trigger and a tangle of time IFs |
| `Content crew: errors` | error trigger | failed runs → Lark |

Most tools need no sub-workflow: regular nodes attach to the agent directly with `$fromAI()` in
their parameters, so the NocoDB reads and writes hang straight off the chat agent. Only work
that carries rules gets its own workflow, which here is just the writing chain. (Verify the
direct-node-as-tool support on 2.38.7 before building — if it is missing, the reads collapse
into one small tools workflow and this becomes 5.)

Sending to Lark is two HTTP nodes (token, then message) duplicated in `lark`, `write`, `cron`
(the weekly report only) and `errors`, rather than a shared sender workflow. Publishing and
outcome checks stay silent; the cards come from `write`.

Branch order inside `cron` matters: database writes go above outbound calls, because branches run
top to bottom and an error stops the rest (`CLAUDE.md`).

## State model

NocoDB base `content_crew` (tables defined later as `nocodb/content_crew/*.json`):

- **`ideas`** — the bank: theme, hook, angle, source (owner or scout, with link or picture), the
  owner's note, used/unused. Both the scout and the chat agent write here; the daily selection
  reads here.
- **`posts`** — idea it came from, content type, the text, image, status
  (`writing|needs_owner|approved|scheduled|published|failed|rejected`), `scheduled_for`,
  `fb_post_id`, `published_at`, check result, rewrite count.
- **`outcomes`** — one row per checkpoint: post, `2h|24h|7d`, reach, reactions, comments,
  shares, taken at. Rows rather than columns because checkpoints repeat and get queried.
- **`lessons`** — what the review learned: one claim per row, the evidence (the post ids and
  numbers behind it), status (`active|retired`), written at. Active lessons are injected into
  the write and select prompts. Code enforces the caps: at most 10 active, one claim each, at
  most 250 characters, and an evidence field naming real posts — a lesson that cannot point at
  posts is not written. Retiring keeps the row, so a reversed call is visible.
- **`settings`** — Lark ids, posting slots, daily quota, standing scouting topics. What the
  owner changes without a deploy, and what the review adjusts for slots.

No run or trace tables in v1: `GET /executions?workflowId=` already answers "what happened", and
tracing arrives when evaluation needs it (Gate 6).

Memory: **thread scope, fetched not stored.** The gate reads the Lark thread and passes it in
with the pictures; the thread is already the record of the conversation, so there is no
chat-memory node and no memory table. The writing chain is stateless — everything it needs
comes in on the item.

Passed vs looked up: the message, thread and pictures are **passed**; the strategy, the owner's
voice and the procedures live **in the prompts**, built in code from `crews/content_crew/04-prompts/`
and versioned in git; ideas, posts, outcomes and settings are **looked up**.

Concurrency is free and wanted: each Lark message is its own n8n execution, so an idea dropped
while another post is being written cannot be lost. No queue machinery.

## Models

Everything goes through **OpenRouter** (`lmChatOpenRouter` for agent and chain nodes, HTTP
Request for image generation and web search). One vendor, one credential. Model ids are the
OpenRouter ones (`deepseek/…`, and an image-capable model for pictures), written into the node
and committed, so a provider-side change is a visible diff rather than a silent regression.

| Step | Model | Why |
|---|---|---|
| Chat agent | a DeepSeek model with vision | screenshots arrive in chat |
| Scout | a model with OpenRouter's web search plugin | search and summarize in one call |
| Select today's ideas | cheap DeepSeek | short judgment over a list |
| Write the post | **kimi-m3** (owner's pick) | this call is the deliverable, so it is the one place not to economise. Picked for writing quality, not price. Verify before building: that it is on OpenRouter, its exact id, and that it holds JSON output — the whole chain depends on this call returning `written_post@1` |
| Check | cheap DeepSeek | rubric judgment, separate context from the writer on purpose |
| Weekly review | the stronger DeepSeek | reasoning over a table of numbers, once a week, so the cost is irrelevant and the quality is not |
| Image | an image-capable model on OpenRouter | generate from a prompt, or edit a picture the owner supplied |

Exact OpenRouter model ids are filled in at build time, verified against the live API rather
than assumed. The writing model is the owner's call and can come from any provider OpenRouter
carries; the cheap models above exist to keep the calls around it from mattering to the bill,
which is what leaves room to pay for the writing.

**Verify first, before anything else is built:** `CLAUDE.md` records that n8n patches
`@langchain/openai` to send DeepSeek's `reasoning_content` back, which DeepSeek requires once
tools are involved. That patch rides on the DeepSeek node. Going through OpenRouter may break
agent tool-calling, so the thinnest possible test — one agent node, one tool, over OpenRouter —
comes before any other work. If it fails, either a non-thinking model or the DeepSeek node
stays for the chat agent, and the rest still goes through OpenRouter.

## Non-functional targets

- **Latency.** Plain chat answer under 30s. A post (write + image + check) under 3 minutes; the
  daily batch runs on a schedule so nobody is waiting. A chat-triggered post blocks the chat
  agent while it runs — acceptable because the card and the reply then arrive together. If that
  reads as silence in practice, make the call asynchronous and acknowledge first.
- **Cost.** Provisional, to verify once built and dominated by whichever writing model is
  chosen. Everything around it is cheap by design: under $0.02 per chat turn, and one image per
  post.
- **Concurrency.** Unbounded per message; posts are independent rows.
- **Failure mode.** Fail closed on publishing: any error, any uncertainty, nothing goes out.
  Everything else escalates to Lark through the error workflow, with partial work left in
  `posts` so a failed post is still there to look at.

## Known limits

- **The review learns attention, not selling.** Reach, reactions, comments and shares are all it
  gets, so it can find what travels and not what converts — the exact gap the task spec names.
  The closest proxies available are comments and messages on offer posts; a real answer needs a
  signal the crew does not have yet. Open question.
- **Small n.** At 4-7 posts a week, a weekly review sees a handful of data points. The caps on
  `lessons` exist because of this, and a lesson should be read as a hypothesis, not a finding.
- **The owner sees proposals, not the raw finds.** The scout's results reach the owner as cards,
  with the source named. Nothing shows the bank unless they ask in chat.

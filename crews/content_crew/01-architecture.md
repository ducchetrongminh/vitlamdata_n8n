# Architecture

From `00-task-spec.md`. Nothing here runs; the built workflows live in `workflows/content_crew/`,
and `07-build.md` records what was built and where it departs from this.

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
- **Writing chain** — one idea in, one finished post out: write → check → the owner's picture if any. The steps are
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
- **Writing as a second agent**: rejected. Write, check, picture is a fixed sequence. An agent
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
                   ├─ saves an idea, replaces a post's text, answers, reads the bank
                   └─ write(idea) / revise(post, feedback) ─► WRITE ─► card in Lark

WRITE (one idea in, one finished post out)
  write (model, JSON: text + picture hint + content type)
    │                                    ▲
    ▼                                    │ one rewrite, counted in code
  G2 (code) ─► check (model: {pass, issues})
                    └─ pass, or fail twice ─► owner's picture, if any (no model) ─► posts + Lark card
                                              (a failed check is named on the card)
```

## Data on the arrows

Shapes are named here and specified in Phase 3 (`03-schemas/`).

| Arrow | Carries |
|---|---|
| Lark → gate | Lark event (message id, chat, sender, thread, image keys) |
| gate → chat agent | message text, thread history with names, picture binaries, the post or idea the thread is about |
| chat agent → tool | one `$fromAI` argument per field, never a JSON blob in a string |
| select → write | `{idea_id, content_type, why_today}` |
| write → code | `{text, picture_hint, content_type, idea_id}` |
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
No picture is generated or edited: a picture is the owner's, used as sent, and changing it is a
data change (`set_picture`), not writing work.

## Workflows (5)

| Workflow | Trigger | Holds |
|---|---|---|
| `Content crew: lark` | webhook | Lark verification, card clicks, the gate, the chat agent, the reply |
| `Content crew: write` | called | write → check → owner's picture → save → card. Attached to the chat agent as a workflow tool, and called in a loop by cron |
| `Content crew: tools` | called | the chat agent's other tools, each with its guard in code |
| `Content crew: cron` | schedule ×4 | scout + propose (daily), publish + outcome checks (frequent), review (weekly). One trigger node per cadence, each feeding its own branch, rather than one trigger and a tangle of time IFs |
| `Content crew: errors` | error trigger | failed runs → Lark |

Every chat tool turned out to carry a rule (a cap, a refusal, a dedupe, a status it must not
touch), so none hangs off the agent as a bare NocoDB node: they share one `tools` workflow whose
Code node decides and whose NocoDB nodes write.

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
  `fb_post_id`, `published_at`, check result, rewrite count, and the columns that stand in for a
  trace table: `owner_edited`, `cost`, `write_model`, `prompt_version` (see `06-evaluation.md`).
- **`outcomes`** — one row per checkpoint: post, `2h|24h|7d`, reach, reactions, comments,
  shares, taken at. Rows rather than columns because checkpoints repeat and get queried.
- **`lessons`** — what the review learned: one claim per row, the evidence (the post ids and
  numbers behind it), status (`active|retired`), written at. Active lessons are injected into
  the write and select prompts. Code enforces the caps: at most 10 active, one claim each, at
  most 250 characters, and an evidence field naming real posts — a lesson that cannot point at
  posts is not written. Retiring keeps the row, so a reversed call is visible.
- **`settings`** — Lark ids, posting slots, daily quota, standing scouting topics, subjects to
  avoid, and the owner's writing rules (`rules`, given to the writer). What the
  owner changes without a deploy, and what the review adjusts for slots.

No run or trace tables. Every number this crew needs is about a post rather than about a stage,
so they are columns on `posts`; `GET /executions?workflowId=` covers the rest. Reasoning in
`06-evaluation.md`.

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

Everything goes through **OpenRouter** (`lmChatOpenRouter` for the agent, HTTP Request for the
other calls and web search). One vendor, one credential. Model ids are the OpenRouter ones,
written into the node
and committed, so a provider-side change is a visible diff rather than a silent regression.

Checked against OpenRouter's model list on 2026-09-23.

| Step | Model | Why |
|---|---|---|
| Write the post | `moonshotai/kimi-k3` (owner's pick) | the deliverable, so the one place not to economise. $3.00 / $15.00 per 1M, 1M context, and it supports `structured_outputs`, `response_format` and `tools` — so `written_post@1` is safe |
| Chat agent | `google/gemini-2.5-flash` | needs vision, tools and a cheap per-turn price: $0.30 / $2.50 per 1M with image input, tools and structured outputs. Going through OpenRouter removed the reason this had to be a DeepSeek model |
| Check | `deepseek/deepseek-chat` | $0.32 / $0.89 per 1M, structured outputs. A three-question rubric; the value is the separate context, not the horsepower |
| Select today's ideas | `deepseek/deepseek-chat` | short judgment over a list |
| Scout | `google/gemini-2.5-flash` with OpenRouter's `web` plugin | search and summarise in one call; the plugin returns `url_citation` annotations, which is what the grounding check compares `source_url` against |
| Weekly review | `moonshotai/kimi-k3` | once a week over a table of numbers, so cost is irrelevant and quality is not |

What the check turned up that changed a choice: **kimi-k3 has vision** (text+image+video in), so
the chat agent could share the writing model — it is not worth $15/1M for a chat turn, but it
means a screenshot could reach the writer directly if that ever proves useful. And since every
call now goes through OpenRouter, the chat agent is no longer tied to DeepSeek for vision, which
is how Gemini Flash won that slot.

**Measured, not estimated** (smoke test, 2026-09-23, one real post from one real idea through
the real prompts):

| | |
|---|---|
| kimi-k3 tokens | 7,585 in, **5,365 out** |
| kimi-k3 cost | $0.023 + $0.080 = **$0.10 a post** |
| kimi-k3 latency | **198 s** |
| gemini-2.5-flash + one tool call | 107 tokens, 3.2 s |

The output tokens are the surprise: 5,365 for a 1,148-character post. kimi-k3 is a reasoning
model, so most of that is thinking, and it drives both the cost and the three minutes. An earlier
guess of 800 output tokens put the post at $0.04; it is $0.10, and a daily batch of three is
about $0.31, so roughly $9 a month. Still small, but the lever if it ever matters is
`reasoning_effort`, which OpenRouter exposes for this model — it trades thinking for both price
and latency.

With the check and the occasional rewrite, a whole post measured about $0.10 without a rewrite
and $0.17 with one once the $0.035-0.039 picture is taken out (`07-build.md`), so about $0.12 on
average.

**Verified 2026-09-23, so this is no longer a risk.** The concern was that n8n patches
`@langchain/openai` to send DeepSeek's `reasoning_content` back — a patch that rides on the
DeepSeek node — so tool-calling might break through OpenRouter. It does not: an `agent` 3.1 node
with `lmChatOpenRouter` on `google/gemini-2.5-flash` and one Calculator tool called the tool and
answered correctly in 3.2 s. And the writing path is not exposed to it at all, since that call
has no tools.

## Non-functional targets

- **Latency.** Plain chat answer under 30 s. A post takes **up to about 3.5 minutes** — the
  writing call alone measured 198 s in the smoke test; whole posts took 81 s and 136 s in the
  build. The daily batch does
  not care; nobody is waiting on a schedule. What this does settle is the acknowledgement: a
  chat-triggered post leaves the owner watching nothing for three and a half minutes, so
  `write_post` **acknowledges first and replies when the card lands**, rather than blocking
  silently. That was written as "add it if silence becomes a problem"; the measurement says it
  is a problem.
- **Cost.** About $0.12 a post, measured end to end. A chat turn is a rounding error next to it.
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

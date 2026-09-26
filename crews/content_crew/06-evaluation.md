# Evaluation and operation

## What can and cannot be graded by a machine

The deliverable is a post that sounds like one person. No assertion decides that. Being honest
about the split is what keeps the eval useful instead of decorative:

| Graded by code | Graded by the owner | Comes free from production |
|---|---|---|
| schema validity, placeholders, length band, `leads_to_offer` present, quota respected, ids exist in the bank, duplicates, `NO_REPLY` precision, evidence counts on lessons | does this sound like the page; is this post worth publishing | **approved-without-edit rate**, check-pass-first-try, rewrites per post, cost per post |

The third column is the real scoreboard. A crew whose cards the owner keeps rewriting is failing,
whatever the assertions say — and that number arrives on its own, from `posts`, without anyone
running a suite.

## The golden set

`06-evals/dataset.jsonl`, 34 cases across the six calls. Each row names the call it targets, the
input, what must and must not be in the output, and where a human has to look.

Composition, deliberately:

- **typical** — the everyday case for each call
- **edge** — thin bank, thin idea, one settled post, unreadable picture
- **adversarial** — input that invites a fabrication, a duplicate, or a quota breach
- **regression** — real failures from Lark, kept so a prompt change cannot bring them back
- **should refuse** — cases where the correct answer is fewer, empty, `NO_REPLY`, or "nothing
  changed this week"

Roughly a third are refusals, on purpose. A crew that never refuses is a crew that invents, and
the refusal paths are the ones that go quiet when a prompt changes.

## Running it

No harness is built in v1, and building one before the crew exists would be scaffolding for
later. The pattern this repo already uses works: a temporary webhook workflow that runs the call
under test and undoes anything it wrote, driven by the dataset rows.

- **Per call** — run the rows for one call whenever its prompt changes. Cheap, fast, and the only
  thing that catches a prompt edit that quietly killed a refusal path.
- **End to end** — before anything goes live and after any change to the writing chain: a full
  day's batch on a copy of the real bank, ending in cards that never publish.

A crew can fail while every call passes. Only the end-to-end run catches the coordination
failures — the selection that picks an idea the writer cannot use, the check that fails
everything the new writing model produces.

## Rubrics

`06-evals/rubrics/voice.md` is the one that cannot be automated. It is what the owner reads a
card against, and what a disagreement about a post should be argued in terms of.

## Failure taxonomy

Fix structurally. A prompt patch that fixes one case usually moves the failure somewhere else.

| Class | What it looks like here | Structural fix |
|---|---|---|
| Specification | the writer returns two angles, or a summary instead of a post | tighten `written_post@1` and the contract's non-goals |
| Coordination | selection picks an idea whose `owner_words` the writer then needs and does not have | carry the field through `write_task@1`, not through a summary |
| Information loss | the owner's phrasing is tidied up somewhere between chat and post | `bank_idea` stores `owner_words` verbatim; nothing between rewrites it |
| Verification | a post with an invented statistic reaches a card | the check does not look for fabrication — code does, against the input |
| Termination | a post loops through rewrites | the counter, already capped at 1 |
| Tool | the agent banks an idea when asked to write one | the tool description, not the system prompt |
| Grounding | a scouted idea cites a URL that 404s | the search result is the only allowed source of a `source_url` |

## Tracing

**No trace tables in v1**, against the method's default, for a reason: every number this crew
needs is about a *post*, not about a *stage*. So they become columns on `posts` —
`check_result`, `rewrites`, `owner_edited`, `cost`, `write_model`, `prompt_version` — and
`GET /executions?workflowId=` covers the rest.

A `stage_traces` table would add a write to every step to answer questions that one row already
answers. Revisit when a question arrives that a post row cannot answer, which will probably be
the first time two model calls need comparing within a single run.

`prompt_version` earns its column: it is what lets "the posts got worse in October" be checked
against "the prompt changed on the 3rd" instead of argued about.

## Operating checklist

- [ ] **Model ids pinned and committed.** A provider-side change is otherwise a silent
      regression, and `kimi-k3` is the call whose quality the whole thing rests on.
- [ ] **Cost per post recorded** on the row. No alert in v1 — the day's spend is bounded by
      `daily_quota`, which is capped at 5 — but the number has to exist before anyone can argue
      about it.
- [ ] **Approved-without-edit rate watched.** The single number that says whether this is
      working. It is in the weekly report already.
- [ ] **Every post waits for a human.** Not a checklist item so much as the thing the checklist
      exists to protect.
- [ ] **Rollback path:** previous `workflows/content_crew/<id>.json` and previous
      `crews/content_crew/04-prompts/`, both in git. A bad prompt is one revert away.
- [ ] **Failed runs are visible.** The error workflow sends them to Lark; partial work stays in
      `posts` rather than being cleaned up.
- [ ] **The eval's refusal rows run after every prompt change.** They are the first thing a
      well-meaning edit breaks.

## Before any of this: the two things to verify

Neither is assumed anywhere in the design, and both can invalidate parts of it:

1. **OpenRouter plus tool-calling.** `CLAUDE.md` records that n8n patches `@langchain/openai` to
   send DeepSeek's `reasoning_content` back, which DeepSeek requires once tools are involved.
   That patch rides on the DeepSeek node. One agent node, one tool, over OpenRouter — before
   anything else is built. If it fails, the chat agent's model choice changes and the rest of the
   design holds.
2. **`kimi-k3` on OpenRouter:** that it is carried, its exact id, its price, and whether it holds
   a JSON output format. The writing chain breaks if this call cannot return `written_post@1`
   reliably.

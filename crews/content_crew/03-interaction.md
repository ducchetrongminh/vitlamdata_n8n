# Interaction

How the parts exchange information, who may call whom, where a run can stop, and where a person
has to say yes. Schemas live in `03-schemas/`, versioned in their `$id` (`written_post@1`).

## Messages

Every payload has a schema and is validated where it lands. Twelve task and result schemas cover
the calls; `envelope@1` wraps the one edge that needs more than a payload.

**Why only one envelope.** The method's envelope carries `status`, `issues`, `cost` and a
delegation depth because in a multi-agent crew a message can half-arrive and nobody notices.
Here there is one agent, delegation never goes deeper than one hop, and n8n already records
every node of every execution. So the envelope is used where a call crosses a workflow boundary,
has two callers, and can half-succeed — the writing chain's return — and nowhere else. Wrapping
inline chain steps would be ceremony.

`status: partial` is the one that earns its place: a post that reached a card with a known
problem (the check failed twice, the image could not be made) is not a success and not a
failure, and the card has to say which.

## Coordination modes

| Edge | Mode | Note |
|---|---|---|
| chat agent → its tools | tool call | caller keeps control, gets a typed result |
| chat agent → writing chain | tool call, answered at once | `write_post` and `revise_post` start the chain as its own execution; the card follows in the thread |
| cron → writing chain | tool call, in a loop, one per picked idea | isolated failures, cheap retries |
| cron → select, scout, review | inline chain steps | fixed sequence, no handoff |
| writing chain → check | inline call with a fresh context | the separation is the mechanism |
| anything → owner | Lark message or card | the only human edge |
| scout, chat agent → `ideas` | shared table | a blackboard, but a safe one: both insert, and only the chat agent edits, on the owner's instruction |

No handoffs: nothing takes over a run from something else. No debate, no broadcast, no
peer-to-peer. Every arrow returns to its caller.

## Acquaintance matrix

Who may invoke whom. The sparsity is the point.

|  | chat agent | write | check | select | scout | review | publisher | Facebook |
|---|---|---|---|---|---|---|---|---|
| **chat agent** | — | ✅ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| **cron** | ⛔ | ✅ | ⛔ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **write** | ⛔ | — | ✅ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| **check** | ⛔ | ⛔ | — | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| **select** | ⛔ | ⛔ | ⛔ | — | ⛔ | ⛔ | ⛔ | ⛔ |
| **scout** | ⛔ | ⛔ | ⛔ | ⛔ | — | ⛔ | ⛔ | ⛔ |
| **review** | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | — | ⛔ | ⛔ |

Four of the six model calls invoke nothing at all. Only code (`cron`) reaches Facebook.

## Lifecycle gates

Every stage boundary is checked, and code does the checking even when a model supplied the
judgment.

| Gate | Where | Checks | Enforced by | On fail |
|---|---|---|---|---|
| **G0** | Lark message arrives | does this concern the bot: sender, mention, thread, `/` | code | nothing happens, silently |
| **G1** | after `select` | every `idea_id` is in the bank; every type is in `allowed_types`; at most `quota` picks | code | drop invalid picks; if none survive, tell the owner the bank is thin |
| **G2** | after `write` | validates `written_post@1`; no placeholder patterns (`[...]` holding words, `TODO`, `XXX`); length band; `leads_to_offer` non-empty; no `story` without `owner_words` | code | the one rewrite, with the reasons; a second failure fails closed — no card, the row goes to `failed` and the error reaches Lark |
| **G3** | after `check` | `pass` is a boolean and matches `issues` being empty | code | treat a malformed verdict as a pass with the issue noted; a broken checker must not block the crew |
| **G3a** | `check` failed | rewrites so far | code (counter, max 1, shared with G2) | first failure loops to `write` with the issues; second sends the card anyway, naming the failing point |
| **G4** | before the card | the post row is saved; an image exists or its absence is stated; status is `needs_owner` | code | no card; escalate to the owner with the reason |
| **G5** | the card | approve or reject | **human** | reject sets `rejected`; nothing else happens |
| **G6** | before publishing | status is `approved`; `fb_post_id` is null; the slot is due; the text still matches what was approved | code | skip this run, no publish |
| **G7** | after publishing | `fb_post_id` written before any other step in the branch | code | on a Facebook error set `publish_failed` and escalate; never blind-retry a publish |
| **G8** | the review's writes | each new lesson: one claim, ≤250 characters, ≥2 evidence post ids that exist; active lessons ≤10 after applying; each slot change carries `n` above the floor | code | drop that lesson or slot change, keep the rest, and say so in the report |

G6's "the text still matches what was approved" is the gate that makes the approval mean
something: the owner approved that text, not that row.

One caller may move that line: `update_post`, when the owner themselves asks for a change to an
already-approved post. It re-records the approved text along with the edit, so the publish is
not silently blocked, and returns the new text in full so it lands in the thread where they can
read it. The gate exists to stop the crew changing text after approval, not the owner.

`revise_post` does not move the line: a post the crew rewrites from the owner's feedback goes
back to `needs_owner` with a new card and token, so the rewritten text needs a new approval.

## Termination

Every path has a provable end.

| Path | Limit |
|---|---|
| chat agent | 20 steps, 300s |
| writing chain | 1 rewrite; 420s per writing call (measured 198s, kimi-k3 thinks); 900s for the chain with a rewrite in it |
| select, check | 1 call each, 60s |
| scout | 1 call, 180s |
| review | 1 call, 300s |
| daily batch | `quota` write calls, hard-capped at 5 in `settings` |
| publisher | at most one post per slot, and never a post already carrying an `fb_post_id` |

No model decides when it is finished anywhere on this table.

**Cost.** n8n has no native per-run cost kill, so the bound is structural: the daily batch cannot
exceed `quota` writes, each write is at most two model calls plus one image, and the chat agent
is capped at 20 steps. The bill is therefore bounded by the day's quota, not by anything a model
chooses. Worth revisiting if a spend cap ever becomes available.

**Partial work is always kept.** A failed write leaves its row in `failed` with the reasons in
`issues`. A failed publish leaves `publish_failed` with the text intact. Nothing is deleted on
the way out.

## Idempotency

The publisher is the only step that can do something twice in public. It claims a row before
acting — status `approved` → `publishing` → `published`, with `fb_post_id` written immediately
after Facebook answers — and it never touches a row that already has an `fb_post_id`. A crashed
run leaves a row in `publishing`, which is visible and fixed by hand rather than retried
automatically, because the cheap failure is a post that goes out late and the expensive one is a
post that goes out twice.

## Where a person is in the loop

| Point | Who | Blocking |
|---|---|---|
| Approving a post | owner, on a card | yes — nothing publishes without it |
| Editing a post before approving | owner | no, but it is recorded and the review reads it as evidence |
| A thin bank | owner, told in chat | no — the batch writes fewer |
| The weekly report | owner, in Lark | no — lessons apply within their caps, and the owner can veto in chat |
| A failed run | owner, through the error workflow | no |

The owner's attention is spent on the card and nowhere else. That is the whole design: judgment
is theirs, everything around it is the crew's.

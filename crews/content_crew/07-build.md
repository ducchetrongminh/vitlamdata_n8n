# Build

What runs, where, and what has been checked on the instance. The design it implements is in the
files numbered 00 to 06; where the build had to depart from them, the design file now says so.

Live since 2026-09-23. It replaced the content agent (`workflows/content_agent/`, deactivated the
same day) and took over its Lark webhook path, so the Lark app needed no change.

## Workflows

| Workflow | Id | Trigger | Holds |
|---|---|---|---|
| Content crew: lark | `QSFh0NKjPd5mVdRt` | webhook `/webhook/content-agent` | Lark verification, card clicks (approve books the next free slot), the gate, the chat agent and its 8 tools |
| Content crew: write | `360koAPJWINLzICv` | called | `mode: start` checks the guards, creates the post row and starts `mode: run` as its own execution, then returns at once. `run`: write → check → one rewrite → image → save → card |
| Content crew: tools | `1jaF548a0UPSdhvi` | called | The chat agent's tools except `write_post`: one Code node decides, the NocoDB nodes after it write |
| Content crew: cron | `khte5EFhBM16qfui` | schedules, or called with `{branch}` | scout 01:30, propose 06:30, publish every 5 min, outcomes at :10 and :40, review Mon 03:00. Called with `{branch: scout\|propose\|publish\|outcomes\|review}` it runs that branch now |
| Content crew: errors | `sfkO2xnRFAQzFcfa` | error trigger | Failed runs of the other four → the team chat |

NocoDB base `content_crew` (`ph3awm32yo72bw0`), tables in `nocodb/content_crew/`.

Prompts are the files in `04-prompts/`, copied into the workflows by
`scripts/embed-prompts.py` (a Code node whose notes read `prompts: content_crew <name>...`).
Edit a `.md`, run the script, push the workflows it changed. Every post row records the prompt
hash it was written with (`prompt_version`).

## Where the build departs from the design

- **Check before image, not after.** The picture is drawn from the final text's `image_prompt`,
  so a rewrite does not pay for a picture that is thrown away.
- **One rewrite covers both G2 and G3a.** A draft that fails the code checks goes to the same
  single rewrite as a draft the check failed, with the code's reasons as `point: format` issues.
  A second failure of G2 fails the post closed (`failed`, error to Lark, no card).
- **Model calls other than the chat agent are HTTP Request nodes to OpenRouter**, not chain
  nodes: that is the only way to read `usage.cost` for the `cost` column, and it gives the web
  plugin (scout) and image output (write) in the same shape.
- **`write_post` is asynchronous**, as `01-architecture.md` already decided after the latency
  measurement: the agent gets `{status: ok, post_id}` in about a second and the card follows.
- **A fifth workflow, `tools`.** Every chat tool carries a guard, so none could hang off the
  agent as a bare NocoDB node.
- **The daily quota is also capped by free slots**: `min(daily_quota, 5, free slots in the next
  7 days − posts writing or waiting for the owner)`. Without it a quota above the slot count
  grows an approved backlog that never drains.
- **Slots seeded** as `tue-20:00, thu-20:00, sat-20:00, sun-20:00` and `daily_quota` 1: the
  owner's instinct (weekends, 8pm) plus two weekdays to reach the 4 posts a week in the
  definition of done. The owner changes both in chat.
- **Status `scheduled` dropped.** `approved` with a `scheduled_for` is the queue.
- **`revise_post`, a ninth chat tool.** The design had only `update_post`, which replaces the text
  with words the owner supplies, while the chat agent may not write post text. So "sửa bài này"
  had no path and the agent pasted the owner's feedback in as the post. `revise_post` sends the
  post back through `write` (`mode: start` with `post_id`): the feedback goes in as a rewrite
  issue with `point: owner`, a picture the owner sends is edited per `picture_note`, a text-only
  revision keeps the old picture, and the post returns to `needs_owner` with a new card and token.
- **Owner rules in `settings.rules`**, handed to the writer as `owner_rules`. Not lessons:
  lessons need two settled posts as evidence, are capped at 10 and are retired by the review;
  the owner's rules need none of that and must never be retired by the crew.

## Verified on the instance, 2026-09-23

| What | Result |
|---|---|
| write, first try | post #2: passed the check first time, $0.138, 81 s |
| write, with a rewrite | post #3: check failed on `connected`, rewrite passed, $0.212, 136 s |
| write guards | missing idea, idea without theme, idea with a post already waiting: refused |
| image | `gemini-2.5-flash-image` draws the picture ($0.039, not the $0.0003 estimated). Posts #2 and #6 were written before the Lark app had `im:resource:upload`, so their cards say the picture is missing; the scope is in since, and upload plus download (`GET im/v1/images/<key>`, what the publisher uses) both work |
| chat agent | answers from `read_ideas` / `read_posts`, banks an idea with the owner's words and asks before writing, calls `write_post` on "viết luôn đi", returns `NO_REPLY` to chatter between people |
| tools | create, dedupe refusal, partial update, `update_post` on an approved post re-records `approved_text`, settings validation |
| card click | bad token refused; approve books the next free slot; a second click changes nothing |
| scout | banked ideas whose `source_url` is among the search citations; ideas without one are dropped |
| propose | quota 1, one pick through G1, write started |
| revise | post #7: owner feedback applied (dashes gone, rest kept), owner's screenshot edited per the note and uploaded, new card in the thread, $0.12; a rejected post refused |
| review G8 | `Apply` run offline against crafted outputs: unsettled or single-post evidence, over-long lessons, the 10-lesson cap, a lesson retiring another, a slot change under the floor |

Not yet exercised live: a publish (nothing approved has come due), an outcome checkpoint (nothing
published), a review with settled posts, a picture the owner sends with an idea, the gate on a
real Lark message.

## Acceptance tests for the owner, in Lark

1. DM the bot an idea; it answers with the idea number and asks whether to write it.
2. Answer "viết luôn"; a card arrives in the thread within about 4 minutes.
3. Reply to the card asking for a change; the bot edits the post and quotes the new text.
4. Approve the card; the reply names the slot. After the slot, the post is on the page.
5. A picture sent with an idea is used for that post's image.
6. In the team group, a message between two people in a bot thread gets no reply.
7. Monday after the first week with two posts 7 days old: a review report arrives.

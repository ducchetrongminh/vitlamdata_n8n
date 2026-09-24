# Task specification: Content Crew

v1 scope only. Other platforms and video are deferred — see `open-questions.md`.

## Trigger

The crew proposes; the owner judges. Five shapes:

1. **Daily proposal** (schedule) — the crew picks ideas from the bank and sends the owner
   finished posts as approval cards. This is the main loop: the owner has to remember nothing.
2. **Scouting** (schedule) — a web search over standing topics fills the idea bank with
   data-domain updates and cross-domain hooks. Not literal feed-scrolling: built-in n8n nodes
   have no login or JS-rendering, so this is a search API, not a browser.
3. **Idea drop** (human, any time) — a raw idea, observation, story, screenshot or link. It goes
   into the bank, and the owner can ask for it to be written right away instead of waiting for
   the next daily batch.
4. **Outcome check** (schedule, per published post) — three fixed offsets after publish: 2h
   (viral signal), 24h (content quality signal), 7d (final numbers; some posts pick up later).
5. **Weekly review** (schedule) — reads the posts against their outcomes, writes what it learned
   into `lessons` that feed back into the writing, adjusts the posting slots, and reports.

## Inputs

| Name | Type | Source | Required | Notes |
|---|---|---|---|---|
| Idea/story text | text | owner, chat | for idea drop | Stories must be the owner's own words/experience — the agent never invents a personal story. |
| Screenshot/link | image or URL | owner, chat | for idea drop | May be outside the data domain; agent extracts theme/hook/angle, not the literal content. |
| Scouted material | search results | web search over standing topics | for scouting | Fills the idea bank between the owner's own drops. |
| Content strategy | doc | `docs/Content Strategy.md` | yes | Offer/Education/Story split, Daily Seinfeld Sequence cadence, pre-publish check. |
| Lessons | rows | the weekly review's own output | yes, once there are any | What past outcomes taught, fed back into writing and idea selection. |
| Picture for the post | image | the owner's own picture, sent with the idea or later for that post | no | Used exactly as sent. No picture is generated or edited by a model: image models redraw a screenshot's text as gibberish, and the owner chose not to use AI pictures (2026-09-24). A post without one goes out as text. |
| Approval | yes/no + edits | owner, chat | yes, before every publish | See Hard constraints. |

## Procedure (the SOP)

0. On schedule, scouting searches the standing topics and files what it finds in the idea bank:
   theme, hook, angle, source.
1. The owner drops an idea, a story, a screenshot or a link whenever one comes to them. It goes
   into the same bank.
   - decision point: **write it now vs. bank it** — an explicit ask ("viết bài này đi") writes
     it now; anything else is banked for the daily batch to pick up.
2. On schedule, the crew picks today's ideas from the bank.
   - decision point: **which ideas, and what mix** — how many and the offer cadence (two per
     month, per `docs/Content Strategy.md`) are fixed rules; which ideas fill the quota is
     judgment about what fits now.
3. For each picked idea, pick the content type (funny observation / story / education / sales
   offer).
4. Write the content in the owner's voice/intent from the idea. Stories keep the owner's own
   words; the agent doesn't fabricate a personal experience.
   - standard: what goes on the card is the version meant to be published as it stands, not a
     rough pass for the owner to fix. "Good enough, they'll edit it" is not a bar this crew is
     allowed to aim at.
5. Picture: if the owner sent one with the idea, use it exactly as sent. Otherwise the card
   suggests what picture would suit, and the owner may reply with one; the post can go out as
   text.
6. Run the pre-publish check (Relevant / Closer / Connected, `docs/Content Strategy.md`). A
   failing text is rewritten once, then shown to the owner with the failure noted rather than
   silently forced through.
7. Send the finished post (text, and the picture if there is one) to the owner as an approval card.
   - decision point: approve as-is, edit, or reject — owner's call, always.
8. On approval, queue the post for the next good time slot (code-scheduled, seeded with the
   owner's instinct — weekends, ~8pm — then adjusted from outcome data) rather than publishing
   that instant.
9. At each of 2h / 24h / 7d after publish, pull reach/reactions/comments/shares and log it
   against the post.
10. Weekly, read the posts against their outcomes: what worked, what did not, which slots earn
    their place. Write the conclusions down as lessons that change how the next posts are
    written and picked, retire the ones the numbers stopped supporting, and report the changes
    to the owner. This is the step that used to happen in the owner's head.

## Deliverable

A Facebook post (text, with the owner's picture when they gave one) on the Vịt làm Data page, approved by the owner on a card then
published at the next good time slot. Each post's outcome logged at 2h/24h/7d. Weekly, a report
of what the numbers changed.

## Definition of done

- [ ] Cards arrive on schedule without the owner asking, and an idea the owner does drop becomes
      a card in under 10 minutes.
- [ ] Every card already passed the 3-point pre-publish check, or names the point it failed.
- [ ] Cards are approved as they stand more often than they are edited — if the owner rewrites
      most of them, the crew is producing rough passes and the writing model or prompt is wrong.
- [ ] A picture the owner gives is published exactly as sent; no post carries a generated or model-edited picture.
- [ ] Every published post gets outcome checks logged at 2h, 24h and 7d, retrievable without the
      owner opening Facebook Business Suite by hand.
- [ ] An idea dropped while another post is being written is not lost.
- [ ] Sustained output reaches at least 4 posts/week (target: daily) with the owner's time spent
      only on ideas and approvals.
- [ ] The weekly review changes something real — a lesson written or retired, or a slot moved —
      and every lesson names the posts behind it.

## Hard constraints (never allowed)

- Never publish to Facebook without the owner's explicit approval of that post.
- Never write a personal story the owner didn't actually tell — a story's content must trace to
  the owner's own words.
- Never publish a sales/offer post outside the two-per-month cadence in `docs/Content
  Strategy.md`.
- Never drop an idea the owner sends while another is in progress.
- Never write a lesson that cannot name the posts and numbers behind it, and never let the
  active set grow past its cap — the crew edits its own instructions here, so the caps are what
  make that safe.
- Repo-wide (CLAUDE.md): built-in n8n nodes only, no `$env`, no secrets in workflow/credential
  JSON, no private-network HTTP targets.

## Baseline

Manual cost: ~1-2 hours/month, done irregularly because the owner rarely has a free sitting to
browse, write, find an image and post all at once. Output: 1-2 posts/month.

Target: 4 posts/week minimum, daily ideal — not gated on the owner finding a free block of time,
since browsing (scouting digest), writing, imaging and outcome-tracking are the agent's job; the
owner only sparks ideas, reacts to digests, and approves.

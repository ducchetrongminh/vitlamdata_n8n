# Task specification: Content Crew

v1 scope only. Other platforms and video are deferred — see `open-questions.md`.

## Trigger

Four shapes:

1. **Idea drop** (human) — a raw idea, observation, or story, ready to become a post now.
2. **Inspiration capture** (human) — a screenshot or link the owner forwards while browsing
   (data-domain or not); not necessarily written today.
3. **Scouting digest** (schedule) — the agent searches (Tavily) for data-domain updates and
   notable cross-domain hooks, summarizes what it found, and shares the digest with the owner.
   The owner reacts with their own thoughts on top (same as inspiration capture from there). Not
   literal feed-scrolling — built-in n8n nodes have no login/JS-rendering, so this is a search
   API, not a browser.
4. **Outcome check** (schedule, per published post) — three fixed offsets after publish: 2h
   (viral signal), 24h (content quality signal), 7d (final numbers; some posts pick up later).

## Inputs

| Name | Type | Source | Required | Notes |
|---|---|---|---|---|
| Idea/story text | text | owner, chat | for idea drop | Stories must be the owner's own words/experience — the agent never invents a personal story. |
| Screenshot/link | image or URL | owner, chat | for inspiration capture | May be outside the data domain; agent extracts theme/hook/angle, not the literal content. |
| Content strategy | doc | `docs/Content Strategy.md` | yes | Offer/Education/Story split, Daily Seinfeld Sequence cadence, pre-publish check. |
| Image for the post | image | stock / OpenRouter-generated / OpenRouter-edited from owner's image or prompt / owner-attached | yes, before publish | Method picked per post, flexibly. |
| Approval | yes/no + edits | owner, chat | yes, before every publish | See Hard constraints. |

## Procedure (the SOP)

0. On schedule, the agent runs the scouting digest, shares it with the owner. The owner may
   react with thoughts, which folds into step 1 as an idea drop or inspiration capture.
1. Owner sends an idea, a story, or forwards inspiration material (directly, or reacting to a
   digest).
   - decision point: **write now vs. save for later** — explicit ("viết bài này") vs. "lưu ý này
     lại" defaults to save.
2. If inspiration: extract the theme/hook/angle and store it against future ideas; no draft yet.
3. If write-now: pick the content type (funny observation / story / education / sales offer)
   from what the owner said and the current mix (two offers/month, rest education+story, per
   `docs/Content Strategy.md`).
   - decision point: an idea dropped mid-flow (while another draft is in progress) must not be
     lost — queue it, don't discard it.
4. Draft the post text in the owner's voice/intent from the idea. Stories keep the owner's own
   words; the agent doesn't fabricate a personal experience.
5. Get an image: stock lookup, generate from a prompt via OpenRouter, edit an image the owner
   supplied via OpenRouter, or ask the owner to attach one — whichever fits what's available for
   this post.
6. Run the pre-publish check (Relevant / Closer / Connected, `docs/Content Strategy.md`). A
   failing draft is reworked once, then shown to the owner with the failure noted rather than
   silently forced through.
7. Show the draft + image to the owner for approval.
   - decision point: approve as-is, edit, or reject — owner's call, always.
8. On approval, queue the post for the next good time slot (code-scheduled, seeded with the
   owner's instinct — weekends, ~8pm — then adjusted over time from outcome data) rather than
   publishing that instant.
9. At each of 2h / 24h / 7d after publish, pull reach/reactions/comments/shares and log it
   against the post, for the owner's own read and for future idea/topic decisions (the "viral
   but doesn't sell" problem).

## Deliverable

A Facebook post (text + image) on the Vịt làm Data page, approved by the owner in chat then
published at the next good time slot. Each post's outcome logged at 2h/24h/7d and retrievable
later. Plus, on schedule, a scouting digest shared with the owner.

## Definition of done

- [ ] From idea/material arriving to draft+image ready for approval takes under 10 minutes
      (removes the "needs a dedicated sitting" bottleneck the manual process had).
- [ ] Every draft shown for approval already passed the 3-point pre-publish check, or is shown
      with the specific failing point named.
- [ ] Every published post carries an image.
- [ ] Every published post gets outcome checks logged at 2h, 24h and 7d, retrievable without the
      owner opening Facebook Business Suite by hand.
- [ ] An idea dropped in while a draft is in progress is not lost (shows up after, doesn't
      silently vanish).
- [ ] Sustained output reaches at least 4 posts/week (target: daily) without the owner needing a
      dedicated browsing/writing session.

## Hard constraints (never allowed)

- Never publish to Facebook without the owner's explicit approval of that draft.
- Never write a personal story the owner didn't actually tell — a story's content must trace to
  the owner's own words.
- Never publish a sales/offer post outside the two-per-month cadence in `docs/Content
  Strategy.md`.
- Never drop an idea the owner sends while another is in progress.
- Repo-wide (CLAUDE.md): built-in n8n nodes only, no `$env`, no secrets in workflow/credential
  JSON, no private-network HTTP targets.

## Baseline

Manual cost: ~1-2 hours/month, done irregularly because the owner rarely has a free sitting to
browse, write, find an image and post all at once. Output: 1-2 posts/month.

Target: 4 posts/week minimum, daily ideal — not gated on the owner finding a free block of time,
since browsing (scouting digest), writing, imaging and outcome-tracking are the agent's job; the
owner only sparks ideas, reacts to digests, and approves.

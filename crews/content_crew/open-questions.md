# Open questions

## Resolved

- **Q1. Chat channel:** Lark.
- **Q2. AI provider:** OpenRouter for everything — chat agent, writing, check, review, image
  generation and web search. One vendor, one credential, model ids written per node and
  committed. Exact ids and request shapes verified against the live API at build time. The rest
  stay cheap so the bill has room for the writing call.
- **Writing model:** `kimi-k3`, the owner's pick. To verify before building, none of it assumed:
  that OpenRouter carries it, its exact model id, its price, and whether it holds a JSON output
  format — the chain breaks if this call cannot return `written_post@1` reliably.
- **Q3. Scouting method:** OpenRouter's own web search (the `:online` suffix / `web` plugin),
  not a second vendor. Built-in n8n nodes can't scroll a real feed (no login/JS-rendering), so
  "browsing" means search, and the results go into the idea bank rather than a digest the owner
  has to read.
- **Q8. The owner's voice:** filled from five of their real posts (09/2026). The rules are in
  `04-prompts/_shared.md`; three posts sit in full in `04-prompts/write.md`, which is the only
  call that needs them. What the posts showed that a description would have missed: chat
  spelling used as voice rather than as error (ko, hong, dc, r, nma), `:))` as the main laugh, a
  lone `.` on its own line to break paragraphs, SHOUTED sub-headings mid-post, and a
  self-deprecating line in every single post before any advice is given.
- **Q4. Good posting time slots:** no fixed table. Seed the scheduler with the owner's instinct
  (weekends, ~8pm), then let outcome data (2h/24h/7d checks) adjust it over time — test and
  learn, not a locked schedule. Phase 1 decided: slots live in the `settings` table, the digest
  shows the numbers per slot, and the owner changes them in chat. No optimizer in v1.

- **Q7. A selling signal:** none wired in v1. The owner judges what sells by hand. So the review
  must say `cannot_tell` about selling rather than reasoning toward it from reach — it is already
  written that way, and that stays a rule rather than a temporary gap.
- **Q9. The page and AI:** settled. The owner has already said publicly, recently, how the page
  is made, so there is no promise to the reader being quietly broken and no post type the crew
  has to stay away from. The voice rule that a too-smooth post is a failed post stays — not to
  hide anything, but because that is genuinely how this page reads.

## Still open (deferred from v1)

**Q5. Platform expansion (deferred from v1).** YouTube community, LinkedIn, Facebook community
group — same content pipeline adapted per platform, or separate crews?
Answer:

**Q6. Media expansion (deferred from v1).** Idea: use posts as a cheap market test (easy to
publish, easy to monitor reach), then convert what works into short-form and long-form
educational video. Not scoped yet — a v2 crew or an extension of this one once v1 is proven?
Answer:

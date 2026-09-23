# Open questions

## Resolved

- **Q1. Chat channel:** Lark.
- **Q2. AI provider:** OpenRouter for everything — chat agent, writing, check, review, image
  generation and web search. One vendor, one credential, model ids written per node and
  committed. Exact ids and request shapes verified against the live API at build time. The
  writing model is chosen for writing quality, not price, and the owner will name candidates;
  the rest stay cheap so the bill has room for it.
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

## Still open

**Q9. The page's public position on AI-written content.** The owner's own posts sign off with
"Bài dài, organic, AI-free" and close with "mấy nay lướt phây toàn bài do AI viết, đọc chán quá
nè". Being visibly not-AI is part of what this page is, and this crew writes with AI. The design
already keeps the material human — stories need the owner's own words, ideas come from them or
from cited sources, every post waits for their approval — but that is a supply-chain answer to
what may be a promise-to-the-reader question.

Worth deciding deliberately rather than by drift. Options that have come up: keep the crew to
the post types that are not personal essays (education, news-reactive, offers) and write the
first-person pieces by hand; say something publicly about how the page is made; or decide the
approval step is the line and leave it there.
Answer:

**Q7. A selling signal.** The weekly review only sees reach, reactions, comments and shares, so
it can learn what travels but not what sells — the exact problem that sent the owner to the two
frameworks in the first place. Closest proxies available today: comments and inbox messages on
offer posts, or link clicks if posts carry a link. Is there a signal worth wiring in (messages,
orders, a tracked link), or does the owner judge selling by hand for now?
Answer:

## Still open (deferred from v1)

**Q5. Platform expansion (deferred from v1).** YouTube community, LinkedIn, Facebook community
group — same content pipeline adapted per platform, or separate crews?
Answer:

**Q6. Media expansion (deferred from v1).** Idea: use posts as a cheap market test (easy to
publish, easy to monitor reach), then convert what works into short-form and long-form
educational video. Not scoped yet — a v2 crew or an extension of this one once v1 is proven?
Answer:

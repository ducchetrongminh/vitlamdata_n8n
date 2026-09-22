# Open questions

## Resolved

- **Q1. Chat channel:** Lark.
- **Q2. AI provider:** OpenRouter for everything — chat agent, drafting, check, review, image
  generation and web search. One vendor, one credential, model ids written per node and
  committed. Exact ids and request shapes verified against the live API at build time.
- **Q3. Scouting method:** OpenRouter's own web search (the `:online` suffix / `web` plugin),
  not a second vendor. Built-in n8n nodes can't scroll a real feed (no login/JS-rendering), so
  "browsing" means search, and the results go into the idea bank rather than a digest the owner
  has to read.
- **Q4. Good posting time slots:** no fixed table. Seed the scheduler with the owner's instinct
  (weekends, ~8pm), then let outcome data (2h/24h/7d checks) adjust it over time — test and
  learn, not a locked schedule. Phase 1 decided: slots live in the `settings` table, the digest
  shows the numbers per slot, and the owner changes them in chat. No optimizer in v1.

## Still open

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

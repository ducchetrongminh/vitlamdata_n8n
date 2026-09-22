# Open questions

## Resolved

- **Q1. Chat channel:** Lark.
- **Q2. Image generate/edit provider:** OpenRouter (DeepSeek has no image capability, per
  `CLAUDE.md`'s DeepSeek section). A multimodal model there (e.g. a Gemini image model) takes a
  prompt and/or an input image and returns an image — covers both generate and edit in one tool.
  Plain HTTPS endpoint, new `openrouter` credential (API key). Verify the exact model/request
  shape against the live API in Phase 5, per this repo's convention of verifying before writing
  it down as fact.
- **Q3. Scouting method:** Tavily search API. Built-in n8n nodes can't scroll a real feed (no
  login/JS-rendering), so "browsing" here means a search API. Tavily returns extracted page
  content alongside links, built for feeding an agent, so no separate fetch+parse step. Plain
  HTTPS, new `tavily` credential (API key).
- **Q4. Good posting time slots:** no fixed table. Seed the scheduler with the owner's instinct
  (weekends, ~8pm), then let outcome data (2h/24h/7d checks) adjust it over time — test and
  learn, not a locked schedule. Phase 1 needs to decide who adjusts the seed (code heuristic vs.
  a review step) and where it's stored.

## Still open (deferred from v1)

**Q5. Platform expansion (deferred from v1).** YouTube community, LinkedIn, Facebook community
group — same content pipeline adapted per platform, or separate crews?
Answer:

**Q6. Media expansion (deferred from v1).** Idea: use posts as a cheap market test (easy to
publish, easy to monitor reach), then convert what works into short-form and long-form
educational video. Not scoped yet — a v2 crew or an extension of this one once v1 is proven?
Answer:

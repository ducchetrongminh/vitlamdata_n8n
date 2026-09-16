---
name: vld-save-facebook-post
description: Use when saving a Facebook post to Duc's content ideation library, or searching it for references, via the VLD_content_ideation MCP.
---

# VLD save facebook post

MCP: `VLD_content_ideation` (NocoDB table of Facebook reference posts).

- Save a post: `mcp__VLD_content_ideation__save_facebook_post` (always appends a new row, no dedup).

## Capturing a post from Claude in Chrome

1. Open the post (modal or permalink page). Expand "See more" so `text` is complete.
2. **Do not scroll down to load more comments or replies.** Duc loads comments/replies himself as he wants them visible. Only capture comments that are already rendered on the page when you read it — never scroll or click "View more comments" to fetch additional ones.
3. Read the post via `read_page`/`get_page_text`. Watch for content baked into an attached photo (e.g. a bulleted list rendered as an image) — that is NOT part of the post's `text` field; note it separately if relevant to `why_it_works`.
4. Hover the timestamp (e.g. "15 hours ago") to get the exact tooltip datetime for `posted_at`, converted to ISO 8601 with the `+07:00` offset.
5. Comments: format per field spec — `(N reactions) text`, entries separated by `---`, replies as indented sub-bullets. If no reaction count is visibly displayed on a comment, use `(0 reactions)`.

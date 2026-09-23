# Tool registry

Every capability in the crew, with who may call it and what it costs if it goes wrong.

The chat agent holds eight tools, all of them `read` or `write`. Nothing `destructive` is held by
any model — publishing is code, called by the scheduler. The one `spend` tool is called by the
writing chain, never chosen by a model.

Descriptions are prompts: the model picks tools by reading them, so they say what the tool
returns and when not to use it.

## Chat agent's tools

### read_ideas

```yaml
id: read_ideas
description: >
  Đọc kho ý tưởng. Trả về ý tưởng chưa dùng, mới nhất trước: id, theme, hook, nguồn (sếp hay
  scout), ngày lưu. Xài khi sếp hỏi trong kho có gì, hoặc khi cần kiểm xem một ý đã lưu chưa
  trước khi lưu trùng. ĐỪNG xài để tìm bài đã viết — cái đó là read_posts.
parameters:
  type: object
  properties:
    q: { type: string, maxLength: 100, description: lọc theo theme, bỏ trống thì lấy hết }
    limit: { type: integer, minimum: 1, maximum: 30, default: 10 }
    include_used: { type: boolean, default: false }
returns:
  rows: [{ idea_id, theme, hook, source, banked_at, used }]
  note: theme và hook cắt còn 200 ký tự mỗi cái
side_effect: read
auth: nocodb
timeout_seconds: 15
allowed_roles: [chat-agent]
idempotent: true
```

### bank_idea

```yaml
id: bank_idea
description: >
  Lưu một ý tưởng vào kho, hoặc sửa một ý đã lưu. Hong có idea_id thì tạo mới và trả về số của
  nó; có idea_id thì chỉ sửa mấy trường bạn gửi, mấy trường khác giữ nguyên. Trả về nguyên hàng
  sau khi lưu. Story thì phải để nguyên văn lời sếp vào owner_words.
parameters:
  type: object
  properties:
    idea_id: { type: integer, description: có thì sửa, hong có thì tạo mới }
    theme: { type: string, maxLength: 120 }
    hook: { type: string, maxLength: 500 }
    angle: { type: string, maxLength: 500 }
    source_url: { type: string }
    owner_words: { type: string, maxLength: 4000, description: nguyên văn lời sếp, hong gọt }
    note: { type: string, maxLength: 500 }
  required: [theme]
returns:
  row: { idea_id, theme, hook, angle, source, owner_words, banked_at }
side_effect: write
auth: nocodb
timeout_seconds: 15
allowed_roles: [chat-agent]
idempotent: false      # no idea_id always inserts
guards:
  - source is set by code, not by the model: anything the chat agent banks is `owner`
  - a new idea whose theme matches an unused one within edit distance is refused, and the tool
    returns the existing row so the agent corrects it instead of creating a twin
```

### read_posts

```yaml
id: read_posts
description: >
  Đọc bài: sắp đăng, đã duyệt, đang chờ duyệt, hoặc đã đăng. Trả về id, loại, trạng thái, giờ
  đăng dự kiến, 200 ký tự đầu của bài. Xài khi sếp hỏi mai đăng gì, còn bao nhiêu bài trong kho,
  bài nào chưa duyệt. Muốn nguyên văn một bài thì đưa post_id.
parameters:
  type: object
  properties:
    post_id: { type: integer, description: có thì trả nguyên văn bài đó }
    status: { type: string, enum: [writing, needs_owner, approved, scheduled, published, failed, rejected] }
    limit: { type: integer, minimum: 1, maximum: 20, default: 10 }
returns:
  rows: [{ post_id, content_type, status, scheduled_for, published_at, preview }]
  row: { … full text, only when post_id is given }
side_effect: read
auth: nocodb
timeout_seconds: 15
allowed_roles: [chat-agent]
idempotent: true
```

### update_post

```yaml
id: update_post
description: >
  Sửa một bài chưa đăng: nội dung, hoặc giờ đăng. CHỈ gọi khi sếp kêu rõ. Trả về bài sau khi
  sửa, nguyên văn — nói lại cho sếp coi. ĐỪNG xài để duyệt bài: hong có đường nào duyệt ở đây,
  sếp bấm nút trên thẻ mới là duyệt. Bài đã lên Facebook thì hong sửa được.
parameters:
  type: object
  properties:
    post_id: { type: integer }
    text: { type: string, maxLength: 3000 }
    scheduled_for: { type: string, format: date-time }
  required: [post_id]
returns:
  row: { post_id, status, text, scheduled_for }
side_effect: write
auth: nocodb
timeout_seconds: 15
allowed_roles: [chat-agent]
idempotent: true
guards:
  - no status parameter exists — the route from written to approved runs through the owner's card
    and a parameter here would be a way around it
  - refuses when the post has an `fb_post_id`, or its status is `publishing` or `published`
  - on an already-approved post the text change keeps the approval and re-records the approved
    text, so G6 does not silently block the publish. Safe because the only caller is the chat
    agent and the only trigger is the owner's own instruction — and the tool returns the new text
    in full so it lands back in the thread where they can see it
```

### read_outcomes

```yaml
id: read_outcomes
description: >
  Đọc số của bài đã đăng: reach, reaction, comment, share, ở mốc 2h / 24h / 7d. Xài khi sếp hỏi
  bài vừa r ra sao, hay bài nào tuần này chạy tốt nhất. Số chỉ nói bài đi xa tới đâu, hong nói
  bài bán được hàng hay hong — đừng suy ra chuyện bán hàng từ đây.
parameters:
  type: object
  properties:
    post_id: { type: integer }
    since_days: { type: integer, minimum: 1, maximum: 90, default: 14 }
    limit: { type: integer, minimum: 1, maximum: 20, default: 10 }
returns:
  rows: [{ post_id, content_type, published_at, slot, checkpoints: { "2h": {...}, "24h": {...}, "7d": {...} } }]
side_effect: read
auth: nocodb
timeout_seconds: 15
allowed_roles: [chat-agent]
idempotent: true
```

### read_settings

```yaml
id: read_settings
description: >
  Đọc cấu hình: khung giờ đăng, ngày mấy bài, mấy chủ đề đang theo dõi. Xài khi sếp hỏi giờ đăng
  hay chủ đề hiện tại.
parameters: { type: object, properties: {} }
returns:
  row: { slots: [...], daily_quota, topics: [...], avoid: [...] }
side_effect: read
auth: nocodb
timeout_seconds: 10
allowed_roles: [chat-agent]
idempotent: true
```

### update_settings

```yaml
id: update_settings
description: >
  Đổi khung giờ đăng, số bài mỗi ngày, hoặc chủ đề theo dõi. CHỈ gọi khi sếp kêu rõ. Trả về cấu
  hình sau khi đổi — nhắc lại cho sếp.
parameters:
  type: object
  properties:
    slots: { type: array, items: { type: string }, maxItems: 14, description: "vd: sat-20:00" }
    daily_quota: { type: integer, minimum: 0, maximum: 5 }
    topics: { type: array, items: { type: string }, maxItems: 20 }
    avoid: { type: array, items: { type: string }, maxItems: 20 }
returns:
  row: { slots, daily_quota, topics, avoid }
side_effect: write
auth: nocodb
timeout_seconds: 10
allowed_roles: [chat-agent]
idempotent: true
guards:
  - daily_quota is capped at 5 here as well as in the schema, because it multiplies the spend tool
  - the previous values go into the run log, so a mistaken change is visible and reversible
```

### write_post

```yaml
id: write_post
description: >
  Viết một bài từ một ý tưởng trong kho, r gửi thẻ cho sếp duyệt. Mất một hai phút. Trả về bài đã
  viết và số của nó. Gọi khi sếp kêu viết. ĐỪNG gọi khi sếp chỉ kể chuyện hay gửi ý tưởng — cái
  đó bank_idea. Mỗi yêu cầu gọi một lần thôi.
parameters:
  type: object
  properties:
    idea_id: { type: integer }
    content_type: { type: string, enum: [observation, story, education, offer] }
    note: { type: string, maxLength: 500, description: dặn thêm của sếp cho bài này }
    again: { type: boolean, default: false, description: viết lại dù ý này đã có bài đang chờ }
  required: [idea_id]
returns:
  schema: crews/content_crew/03-schemas/envelope.schema.json
side_effect: write + spend
auth: n8n sub-workflow
timeout_seconds: 300
allowed_roles: [chat-agent]      # also called by cron, which is code, not a role
idempotent: false
guards:
  - refuses when a post for this idea is already `writing` or `needs_owner`, unless `again` is
    true — otherwise a retry, or the model calling twice, quietly produces two posts
  - `offer` is refused when the month's two are used; the cadence is not the model's to bend
  - every call spends: one writing call, one image, one check. See the cap under make_image
errors:
  - code: check_failed_twice -> status partial, card still sent with the failing point named
  - code: image_failed       -> status partial, card sent without a picture
  - code: write_invalid      -> status failed, row left in `writing`, nothing sent
```

## Called by code, held by nobody

These have no `allowed_roles`. No model can reach them; the workflow decides when they run.

### make_image

```yaml
id: make_image
description: (not a model-facing tool — the writing chain calls it with the image_prompt it wrote)
parameters:
  type: object
  properties:
    prompt: { type: string }
    input_image: { type: string, description: base64, when the owner supplied a picture to edit }
  required: [prompt]
returns: { image: binary, provider_id: string }
side_effect: spend
auth: api_key:OPENROUTER
timeout_seconds: 120
cost_per_call: to be measured once the model is picked
allowed_roles: []
idempotent: false
guards:
  - one call per post, enforced by the chain's structure rather than by a counter
  - the day's ceiling is `daily_quota` images, and `daily_quota` is capped at 5
  - a failure never blocks the post: the card goes out without a picture, flagged `partial`
```

### web_search

```yaml
id: web_search
description: >
  (inside the scout call, through OpenRouter's own web plugin, not a separate node)
  Tìm trên web theo mấy chủ đề trang theo dõi. Trả về kết quả kèm nội dung trích ra. Mọi thứ
  mang về phải dẫn được nguồn từ đây.
parameters:
  type: object
  properties:
    query: { type: string, maxLength: 200 }
  required: [query]
returns: { results: [{ title, url, content }] }
side_effect: read
auth: api_key:OPENROUTER
timeout_seconds: 60
cost_per_call: priced per result by OpenRouter — verify before building
allowed_roles: [scout]
idempotent: true
errors:
  - code: no_results -> return an empty list, not an error; an empty scouting run is valid
```

### publish_facebook

```yaml
id: publish_facebook
description: (code only — the publisher branch of cron)
parameters:
  type: object
  properties:
    post_id: { type: integer }
  required: [post_id]
returns: { fb_post_id: string }
side_effect: destructive
auth: predefinedCredentialType:facebookGraphApi
timeout_seconds: 60
allowed_roles: []
idempotent: false
guards:
  - **no model may hold this, ever.** A post on a public page cannot be taken back, and the
    approval on the card is the only thing standing between a written post and the audience
  - G6 runs first: status `approved`, no `fb_post_id`, slot due, text unchanged since approval
  - claims the row (`approved` → `publishing`) before calling Facebook, writes `fb_post_id` the
    moment Facebook answers, and never touches a row that already has one
  - a crashed run leaves the row in `publishing` for a person to look at. Late is cheap. Twice is
    not
```

### send_lark

```yaml
id: send_lark
description: (code only — two HTTP nodes, duplicated in lark, write, cron and errors)
parameters:
  type: object
  properties:
    chat_id: { type: string }
    reply_to: { type: string }
    card: { type: object }
    text: { type: string }
returns: { message_id: string }
side_effect: write
auth: httpCustomAuth:lark
timeout_seconds: 30
allowed_roles: []
idempotent: false
guards:
  - the token call returns HTTP 200 with a `code` field on bad credentials, so check `code`, not
    the status (`CLAUDE.md`, Lark)
```

## Least privilege, checked

| Tool | read | write | destructive | spend | held by a model |
|---|---|---|---|---|---|
| read_ideas, read_posts, read_outcomes, read_settings | ✅ | | | | chat agent |
| bank_idea, update_post, update_settings | | ✅ | | | chat agent |
| write_post | | ✅ | | ✅ | chat agent (spend is capped and structural) |
| web_search | ✅ | | | | scout |
| make_image | | | | ✅ | **no** |
| publish_facebook | | | ✅ | | **no** |
| send_lark | | ✅ | | | **no** |

The agent can propose anything and publish nothing. The only way a post reaches Facebook is a
card the owner tapped, a slot that came due, and a text that has not changed since.

## Output sizes

Every read tool is bounded: `limit` caps rows, previews are cut to 200 characters, and full text
comes back only when a single id is asked for. A tool that returns fifty posts in full would
spend the chat agent's context on rows nobody asked about, and the agent would then answer from
a truncated middle.

# Content Agent: Architecture

How the content agent is built and why. Written for two readers:

- **You (the owner):** read sections 1 to 3 to understand it. Answer the open questions in
  section 4 by writing under each `Answer:` line.
- **Claude (implementing):** read everything before changing `workflows/content_agent/`. Section 2
  is the live system: change it together with the workflows. Section 5 holds the remaining work
  and the tests. Mark something verified only after testing it on the instance, and copy verified
  node behaviour into `CLAUDE.md`.

What the agent does for the business (strategy, commands, Lark and Facebook setup) is in
`README.md` and `docs/Content Strategy.md`. This document covers how it is put together.

Status: **retired 2026-09-23.** All its workflows are deactivated and the content crew
(`crews/content_crew/`, `workflows/content_crew/`) now answers on the same Lark webhook. Section 2
describes the system as it last ran; nothing here is live.

## 1. What we want

An AI employee that works like a person. It has procedures for recurring work, which save effort
and keep results consistent, and it uses judgment for everything else. Commands and explicit
requests run a procedure exactly. Anything else, including pictures, goes to the agent, which
decides what is being asked and does it with its tools.

It is not a fixed pipeline of LLM steps: code must not decide what a message means.

## 2. Architecture (live)

```
Lark ──► lark (webhook /webhook/content-agent, answers Lark at once)
           ├─ card click ─► check token, save decision, log event ─► strategist (event)
           └─ message ───► lark message
                              GATE (code): for the bot and allowed? fetch message, thread
                                           history, names; list the pictures; log the signal
                              FRONT DESK (deepseek-flash, sees the pictures)
                                 ├─ quick work: its own tools, then its reply
                                 └─ heavy work: hand_off ─► STRATEGIST (runs on its own)
                                                              └─ replies in the same thread
Schedules: daily shift 02:00, weekly review Mon 03:00 ─► STRATEGIST
```

| Workflow | Id | Trigger | Role |
|---|---|---|---|
| Content agent: lark | `FUKgI67LbICIFMJT` | webhook | Receives Lark events, handles card clicks |
| Content agent: lark message | `Ebo2WLzbB0JvSkHB` | called | The gate and the front desk |
| Content agent | `rfEEzkFE1lDOKyoQ` | called, 02:00 daily, Mon 03:00 | The strategist |
| Content agent: context | `CEEbmzngGyOZVjL9` | called | Loads settings, goals, playbook, last 6 work log entries, 6 reference hooks and brand docs, and builds the instructions of both agents |
| Content agent: tools | `F9itc3ibxfrk0nUV` | called | Every tool, behind one Switch on `tool` |
| Content agent: lark send | `SRT1dYKEzsyQyQBR` | called | Sends text or cards; with `reply_to` it replies in a thread |
| Content agent: publisher | `m92DxPVFVONuRgrr` | every 5 min | Publishes approved posts to Facebook |
| Content agent: facebook signals | `5tupN4R0XY8KDCAG` | nightly 01:30 | Post metrics, comments, followers → events |
| Content agent: errors | `R9RDKGHveGXK2jcu` | error trigger | Failed runs → Lark |

### Gate (code, in `Content agent: lark message`)

The gate never decides what a message means (D1). It does what the model cannot do for itself:

1. **Access** (node `Read message`).
   - Direct messages: the first sender becomes the owner (`lark_open_id`); other people are
     ignored.
   - Groups: only the linked group (`lark_chat_id`) counts, and in it only messages that concern
     the bot, the ones a person in its place would be notified of (D11): an @mention, a reply to
     one of its messages (in a thread or quoted in the main chat), a message in a thread where it
     has posted (checked in `Decide`), or a text starting with `/`.
   - `/link` stays in code, because it decides who may give the agent orders. In a group that is
     not linked, a message addressed to the bot gets a fixed reply.
2. **Input** (node `Decide`).
   - The thread (last 30 messages) with the members' names; the bot's own messages, recognised by
     `lark_app_id` (D9), are labelled as the agent's.
   - The pictures: those of the message first, then those of the thread, newest first, 10 at
     most, each with its reference `<message_id> <key>`.
   - The post or offer the thread is about (`Post #N` / `Offer #N` in the thread).
3. **Signal** (node `Log message`): the message goes into `events` as `manager_note`, or as
   `change_request` in a post's thread.
4. **Front desk input.** `Agent input` writes the task text: the thread history, the list of
   pictures, who wrote what, and for a command "run the <name> procedure exactly".
   `Download picture` fetches each picture from Lark, and `Front input` puts them on the item as
   `picture_1`, `picture_2`, ... next to the instructions from `Content agent: context`.

### Front desk (deepseek-flash)

The node `Front agent` in `Content agent: lark message` (D7), with up to 30 steps. It sees the
pictures of the message and its thread (D2, D8).

- It handles on its own: questions, status, stories, saving and correcting posts the team likes,
  attaching pictures to posts, reading links, rules, guidelines, goals, small changes to a
  planned post, results, and a team member's own final version of a post (D15).
- It hands off with `hand_off`: offers, planning, writing or rewriting drafts, analysis across
  performance data, the weekly review (D3). The brief carries what they asked, the thread
  context, ids, and what the pictures show, because the strategist cannot see them (D5). It then
  tells them the work has started (D4).
- Its final answer is the reply in the thread (`Front reply` → `lark send`), logged as an
  `agent_run` event. `NO_REPLY` means the message was meant for someone else, and nothing is
  sent.

### Strategist (deepseek-v4-pro, `Content agent`)

It runs the daily shift, the weekly review, what follows a card click (an event), and what the
front desk hands it. Its Task node writes the task:

- shift or scheduled review: "run the <procedure> procedure"; the final answer is the work log
  entry or the report;
- event: what happened; the final answer is a work log entry;
- a hand-off (`procedure`, `brief`, `reply_to`): the procedure and the brief; the final answer
  goes to the team's thread (`After` → `Reply`, or `Report` for a review).

### Instructions and procedures

The node `Instructions` in `Content agent: context` builds the system instructions: the
strategist's by default, the front desk's when called with `agent: front`. Both contain the
strategy, goals, guidelines, lessons, work log, brand docs, the saved posts' hooks and the time;
each agent then has its own role, "How you work" and procedures.

Procedures are named steps for recurring work (D6). A command, or an explicit request, means
"run this procedure exactly"; otherwise the agent picks one that fits or handles the case its own
way.

| Procedure | Command | Run by | Tools used |
|---|---|---|---|
| help | `/help` | front desk | none |
| status | `/status` | front desk | calendar |
| story | `/story` | front desk | upsert_story |
| inspiring | `/inspiring` | front desk | reference_posts, upsert_inspiration |
| attach pictures | (photo for a post) | front desk | calendar, attach_picture |
| final | (bản chốt: a team member's final text of a post) | front desk | finalize_post |
| rule | `/rule` | front desk | upsert_playbook (a directive) |
| guideline | (a long guide sent in chat) | front desk | upsert_playbook (a guideline) |
| goal | `/goal` | front desk | upsert_goal |
| offers | `/offers` | strategist via hand_off | calendar, propose_offer |
| plan | `/plan` | strategist via hand_off | calendar, plan_posts |
| draft | `/draft` | strategist via hand_off | submit_draft |
| review | `/review`, Mon 03:00 | strategist | performance (with the team's versions against the drafts), upsert_playbook (lessons and guidelines), update_post |
| shift | (02:00 daily) | strategist | all its tools |

### Tools

Every tool is a `toolWorkflow` node calling `Content agent: tools`. The model fills the arguments
through `$fromAI`; n8n adds `mode` (`chat` for the front desk, the run's mode for the
strategist), which the model cannot change. The rules stay inside the tools. A tool that saves a
record is named `upsert_<thing>`: without `id` it inserts a row, and with `id` it updates that row
(D12).

| Tool | Front desk | Strategist | Notes |
|---|---|---|---|
| calendar, find_stories, reference_posts, performance, record, update_post | yes | yes | `reference_posts` shows each saved post's id |
| upsert_story, upsert_goal | yes | yes | `upsert_goal` only while the team talks with the agent |
| upsert_playbook | yes | yes | lessons and guidelines; see "Playbook" |
| propose_offer, plan_posts, submit_draft | no | yes | the pre-publish check inside `submit_draft` uses deepseek-flash |
| send_message | no | yes | shifts and events only; in a conversation the final answer is the reply |
| upsert_inspiration | yes | no | one argument per field (text, author_name, counts, comments, ...); with `id`, an empty field stays as it is |
| attach_picture | yes | no | picture references; the post must not be published yet; 10 at most |
| hand_off | yes | no | starts the strategist without waiting; `reply_to` comes from the gate, not the model |
| read_link | yes | no | Lark docs and wiki pages; `remember` adds the link to `brand_doc_urls` (D13) |
| finalize_post | yes | no | the team's final version of a post, approved without the check (D15); an empty text drops it |

### Playbook

The playbook (`content_agent.playbook`) is what the agent works by and improves. It holds two
kinds of entry, and the agent's instructions include every active one on every run, guidelines
first.

- **Lessons** are short rules, each a single claim of at most 250 characters, with at most 25
  active at once. There are two sources:
  - what the agent learned from results, with its evidence and a confidence level ("story posts
    at 20:00 beat 12:00");
  - your one-line directives, from `/rule`. Only you change these.

  The caps keep each lesson one claim that data can confirm or refute, so the weekly review can
  keep or retire it on its own, and keep the instructions short.
- **Guidelines** are long documents with a title and a full text: the style guide, brand voice,
  post structure. There is no cap per guideline; all active guidelines together are capped at
  30,000 characters so the instructions stay bounded. A guideline can be added or changed:
  - by you in chat: you paste the text, or ask for a change;
  - by the agent in the weekly review. It judges the guideline against the goals and results
    (what worked, what did not), then revises the parts the evidence supports.

  Each revision:
  - needs evidence and a one-line summary of the change;
  - keeps the previous full text in its `lesson_change` event. "khôi phục bản trước" restores
    the text from before the last revision, and asking again undoes the restore. Older versions
    stay in the events.
  - is listed in the review report.

Fields: `kind` (`lesson` or `guideline`), `title`, and `lesson`, a LongText field that holds a
lesson or the full text of a guideline. The agent's instructions include the guidelines under
"# Guidelines", then the lessons. `upsert_playbook` with `status: previous` restores a
guideline. Brand docs (`brand_doc_urls`) stay for facts you keep in Lark: products, prices,
mission. The agent reads them but does not change them.

### Data

NocoDB base `content_agent` (`povrpvxg4mvxbba`) has these tables: `settings`, `goals`, `playbook`,
`events`, `offers`, `posts`, `stories`, `inspiring_facebook_posts`. Their files are in
`nocodb/content_agent/`.

### The team's final version (D15)

A team member can give the final text of a post ("bản chốt"). The front desk calls `finalize_post`
with it, and the post is approved at once. What the tool checks and does:

- The text must match, character for character except for whitespace, a message a person wrote
  in the conversation. The gate passes those messages (`written`, the current message and the
  thread); the model cannot set them, so an edit by the model is refused.
- It skips the pre-publish check. It writes `final_text`, sets `approved` and logs an `approved`
  event. The old card's buttons then answer that the post is already approved.
- It works while the post is `planned`, `awaiting_approval`, `approved` or `publish_failed`.
- An empty text drops the final version: the post goes back to `awaiting_approval`, and its card
  works again (or to `planned` without a draft).

`draft` keeps the agent's version. The publisher sends `final_text` when it is set, otherwise
`draft`, and keeps `final_text` when Facebook refuses the post. While a post has a final version,
`update_post` refuses changes to title, brief, angle and hook, and `submit_draft` refuses a new
draft. `performance` marks each post that went out in the team's text (their final version or an
edit on Facebook), scores it "By text", and shows it next to the agent's draft. The review compares
the two.

### Known limits

- Flash misreads some Vietnamese words in screenshots ("MÉO. KHUM. CẦM." for "MẸO. KHUM. CẤM.").
  Ask it to read the picture again, or correct the saved post in chat.
- The strategist cannot see pictures; it works from the front desk's brief.
- A turn in a thread with pictures sends up to 10 of them to flash (D8): `/inspiring` took 40 to
  90 seconds in the tests.

## 3. Decisions

- **D1. The code in front is a gate, not a router.** It checks access, so group chatter never
  reaches an LLM and only the owner and linked group give orders, and it fetches input. No code
  decides what a message means.
- **D2. Flash reads every message addressed to the bot, pictures included.** Flash has vision;
  v4-pro does not (see `CLAUDE.md`, DeepSeek).
- **D3. Heavy work goes to pro.** Flash does not have `propose_offer`, `plan_posts` or
  `submit_draft`, so the split is enforced by the tools rather than left to flash's judgment.
  Reason: in run 1043, flash rewrote 4 drafts itself.
- **D4. `hand_off` runs asynchronously.** Flash acknowledges at once and pro replies in the same
  thread when it is done. Reason: pro runs take minutes; a chat once ran 4m20s in silence (603).
- **D5. No `look_at_picture` tool.** Pro works from flash's brief. Add a picture tool only if a
  handoff misses a picture detail in practice.
- **D6. Procedures are knowledge.** They are named procedures in the instructions, not a separate
  path through the workflow. Commands only force a procedure. They are written in the workflow
  code and versioned in git with the tools they call; to change one, ask Claude.
- **D7. The gate and the front agent share one workflow,** so pictures are never passed between
  workflows.
- **D8. Every turn in a thread with pictures sends up to 10 pictures to flash.** This costs more
  per turn, but it is what makes "đọc lại kỹ ảnh đó" work. Cap it lower if the cost shows.
- **D9. The bot is identified by the setting `lark_app_id` (`cli_…`).** A message is the
  bot's when its `sender_type` is `app` and its `sender.id` equals `lark_app_id`. Mentions still
  use `lark_bot_open_id`.
- **D10. Saving a post you like has no workflow of its own.** The front desk reads the
  screenshots and writes "why it works" in the same turn, and `upsert_inspiration` stores the
  result. A fixed reading chain would take that judgment, and a second look, away from the agent.
- **D11. The bot is notified the way a person would be.** Lark has no "this concerns the bot"
  flag: in the group, the bot receives every message (`im:message.group_msg`). The gate works it
  out from fields Lark gives:
  - an @mention: `mentions[].id` equals `lark_bot_open_id`;
  - a reply to the bot, in a thread or quoted in the main chat: the message's `parent_id` points
    to a message whose sender is the bot (D9);
  - a thread the bot is in: the bot appears among the thread's messages;
  - a command: the text starts with `/`.

  When the message is meant for someone else, the agent answers `NO_REPLY` and nothing is sent.
- **D12. No general database tool; records are saved through `upsert_<thing>` tools.** The agent
  changes data only through tools that check the rules; a raw database tool would let it, for
  example, mark its own post approved.
  - An upsert tool inserts without `id` and updates that row with `id`, so the agent can correct
    what it saved without a separate edit tool.
  - Tools whose creation carries the strategy's rules keep their names: `propose_offer`,
    `plan_posts`, `submit_draft` and `update_post`.
  - `record` appends to the signal log, which is never rewritten.
- **D13. `read_link` reads Lark docs and wiki pages the app has been added to.** For any other
  link it says it cannot read that kind of link. With `remember`, it adds the link to
  `brand_doc_urls`, so the doc is read on every later run. Reading public web pages can be added
  if a real need comes up.
- **D14. Guidelines live in the playbook and improve in the weekly review.** You want the style
  guide to evolve with what works for the goals, and the review is where the agent judges
  results. Lessons stay single claims so they can be judged one by one. Guidelines stay whole
  documents, so every revision is logged and can be restored.

- **D15. The team's final version bypasses the check.** The team is the source of the facts
  and the voice, so the check has nothing to hold its own text against: on post #51 it called the
  owner's sentences unsupported claims, and the strategist rewrote the "bản chốt" through 5 drafts
  (runs 1332, 1346). The tool accepts only text a person wrote in the conversation, so the agent
  cannot approve its own writing this way (D12). There is no A/B test on Facebook: Meta's API tests
  only reels and videos (`POST /{page}/ab_tests`), and Meta Business Suite tests other posts only
  by hand. So the review compares the agent's draft with the team's version instead.

## 4. Open questions (owner answers here)

None right now. Add a question here as `**Qn.** …` followed by an `Answer:` line.

## 5. Plan and tests

Work on a branch. Each step follows the loop in `CLAUDE.md`: edit the file, push, test, pull,
commit. Pushing an active workflow changes production immediately; check
`GET /executions?status=running` first.

| Step | What | Status |
|---|---|---|
| S0 | Test T1 below and record the result here and in `CLAUDE.md` | done: T1 passed |
| S1 | Thread fix (D9, D11): setting `lark_app_id`. The router takes replies to the bot and messages in threads where it has posted, and labels its messages as the agent's in the history. The agent answers `NO_REPLY` to thread messages meant for others. | live; the offline replay of execution 703 passes; A3, A9, A10 still to test in Lark |
| S2 | Tools in `Content agent: tools`, each checking its input: new `upsert_inspiration`, `attach_picture`, `hand_off`, `read_link`; renames `save_story` → `upsert_story` (adds `id`), `save_goal` → `upsert_goal`, `update_playbook` → `upsert_playbook` | live. Each tool was called through a test webhook: 21 refusal paths; `upsert_story` and `upsert_inspiration` created then corrected (a partial correction keeps the other fields); `attach_picture` appended to post #49 without duplicates; `read_link` read a brand doc and remembered a link. Test rows were deleted and changed values restored. `hand_off`'s happy path starts a real pro run, so A5 tests it. |
| S3 | Guidelines (D14): add `kind` and `title` to `playbook` and make `lesson` LongText; `context` loads the guidelines first, in full; the review procedure judges guidelines against the goals and the report lists guideline changes. Move the full style guide from the message of run 1042 into a guideline and retire lessons #19 to #22. | live. The style guide is guideline #32 (5,559 characters) and #19 to #22 are retired. Tested through the test webhook: 8 refusal paths, and a test guideline was added, revised, restored, restored again (which undoes the restore) and retired, then deleted. The report and `performance` show the one-line summary without the old text. The Instructions code run on the live context puts the whole guide under "# Guidelines". A14 waits for a weekly review. |
| S4 | Strategist: its Task names the procedure (hand-offs send `procedure` and `brief`); its instructions come from `Content agent: context`, with the procedures in them | live. The Task code was run for a shift, a scheduled review, a hand-off plan, a hand-off review, an event and an old chat input. The strategist's instructions built by the new code, compared with the old ones on the same live data, only gain the procedures and one line about the front desk. |
| S5 | Front desk: `lark message` becomes the gate plus the flash agent with 13 tools; the old router branches and the calls to capture are gone | live. The gate replayed 10 recorded messages (703, 714, 718, 752, 757, 762, 1024, 1028, 1037, 1042) as expected. A test workflow ran the front desk with real pictures from Lark: see H1 to H7 below. |
| S6 | Delete `Content agent: capture` (D10) and the temporary test workflows | done: both deleted from n8n; the capture file is gone from the repo |
| S7 | Run acceptance tests A1 to A15 in Lark | todo |
| S8 | The team's final version (D15): `finalize_post`, the publisher sends `final_text`, `update_post` and `submit_draft` respect it, `performance` shows it | live. Through a test webhook on a temporary post: 12 tool cases (an edited text refused, the verbatim text approved with an `approved` event, a brief change refused and a time change kept approved, finalizing again without a second approval, dropping, `submit_draft` refused, cancelled and unknown posts refused, no `written` refused) and `performance` showing both texts. The publisher's `Due now` and outcome code passed a local run. F1 to F4 below. The test post and its events were deleted. A16 is left. |

### Tests run

- **T1 (passed 2026-09-18).** An AI Agent node (3.1) with `lmChatDeepSeek` `deepseek-flash` and a
  calculator tool received one input item carrying two PNG pictures as binary (`picture_1`,
  `picture_2`, with `passthroughBinaryImages: true`). Asked to read both and add their numbers
  with the tool, it answered "MANGO 17, RIVER 25, 42" after calling the calculator with
  "17 + 25". So pictures reach the model and tools still work in the same run: build as
  designed.
- **H1 to H7 (passed 2026-09-18).** A temporary test workflow runs the same front desk nodes
  from a webhook, with `hand_off` pointing at a stub, and undoes what each test wrote.
  - H1, `/inspiring` with a real screenshot from Lark: it looked the post up, found it saved as
    #5 and corrected it instead of saving a duplicate (40 to 90 s).
  - H2, "đọc lại kỹ ảnh đó … chép nguyên văn 2 dòng đầu": it read the picture again, quoted the
    two lines, and asked to confirm four unclear words before changing the saved post.
  - H3, "lên plan tháng 10 đi em": it checked the calendar, handed off `plan` with a full brief
    (the free days, the two proposed October offers waiting for approval) and answered in 18 s.
  - H4, a photo with "ảnh này dùng cho bài nhắc ưu đãi ngày 27/09": it found post #49 and
    attached the photo.
  - H5, `/story …`: saved in the teller's words, ending with "(told by Đức Chế)".
  - H6, `/help`: the command list, in plain text.
  - H7, "3h chiều nha Minh" in a bot thread, answering a teammate: `NO_REPLY`.
- **F1 to F4 (passed 2026-09-18).** The same kind of test workflow ran the front desk with
  `calendar` and `finalize_post` on a temporary post.
  - F1, the owner's real "bản chốt" of post #51 (run 1331, 877 characters): approved with the text
    unchanged, in 9 to 23 s.
  - F2, "chốt bản anh gửi ở trên nha, đăng y vậy" after the text in the thread: it copied the
    earlier message exactly.
  - F3, "chốt bản trên nhưng đổi chữ hihi thành hehe": nothing saved. It asked for the full text
    with the change.
  - F4, "thôi bỏ bản chốt đi em": the final version dropped, and the post is waiting for approval again.

### Acceptance tests

- **A1.** Group, @mention, screenshot + "bài này hay, lưu lại": a row appears in
  `inspiring_facebook_posts` with the text as shown, and the reply says what was saved.
- **A2.** DM, photo + "ảnh cho bài tối mai", not a reply to a card: the photo is attached to
  tomorrow's post and the reply says so.
- **A3 (S1).** A reply without @mention in a thread where the bot has answered: it answers (the
  case of 703).
- **A4.** In a thread with a screenshot, "đọc lại kỹ ảnh đó": it reads the picture again and
  answers from the picture, not from the saved text.
- **A5.** "lên plan tháng 10 đi": flash acknowledges within a minute, pro plans with the plan
  procedure, and pro's result appears in the same thread.
- **A6.** `/plan`: the same as A5.
- **A7.** `/story <text>`: the story is saved in the teller's words and the reply confirms it.
- **A8.** A group message not addressed to the bot, or a message in a group that is not linked:
  no agent execution starts.
- **A9 (S1).** The thread history the agent receives labels the bot's messages as its own.
- **A10 (S1).** In the linked group, a quoted reply in the main chat to a bot message, without an
  @mention: the agent receives it.
- **A11.** A Lark doc link sent with "làm theo cái này từ giờ": the agent reads it, the link is
  added to `brand_doc_urls`, and the next run's instructions contain the doc.
- **A12.** "sửa lại bài mẫu #N: chữ X là Y": that row in `inspiring_facebook_posts` is corrected
  and no new row is created.
- **A13 (passed, S3).** The style guide appears in full in the agent's instructions as a guideline, and
  lessons #19 to #22 are retired.
- **A14.** A weekly review with evidence revises a guideline:
  - the report lists the change with its summary;
  - the previous text is in the `lesson_change` event;
  - "khôi phục bản trước" restores it.
- **A15.** "sửa story #N: …": that story is corrected and no new row is created.
- **A16 (S8).** In post #51's thread, "bản chốt:" with the full text:
  - #51 is approved with that text and the reply says when it goes out;
  - on 26/09 at 20:00 exactly that text is published.
- **Unchanged:** the daily shift, weekly review, card clicks, publisher and signals behave as
  before.

### Constraints (from `CLAUDE.md`)

- Built-in nodes only, no `$env`, no private-network HTTP targets.
- The NocoDB node returns rows as `{id, fields}`, and `update` needs the top-level `id`.
- `toolWorkflow` takes the tool's name from the node name. `workflowInputs.schema` lists every
  key, and `$fromAI` descriptions contain no quotes or braces.
- Branches of one node run top to bottom, and an error stops the rest: put database writes above
  Lark calls.
- Ask before deleting or deactivating a workflow.

# Content Agent: Architecture

How the content agent is built, what is changing, and why. Written for two readers:

- **You (the owner):** read sections 1 to 4 to understand it. Answer the open questions in
  section 5 by writing under each `Answer:` line.
- **Claude (implementing):** read everything before changing `workflows/content_agent/`. Build
  from sections 3, 4 and 6, keep the Status column in section 6 current, and when a step ships,
  move what is now true from section 3 into section 2. Mark something verified only after testing
  it on the instance, and copy verified node behaviour into `CLAUDE.md`.

What the agent does for the business (strategy, commands, Lark and Facebook setup) is in
`README.md` and `docs/Content Strategy.md`. This document covers how it is put together.

Status: section 2 describes the live system as of 2026-09-18. Section 3 is agreed but not built.
Section 5 holds what is still open.

## 1. What we want

An AI employee that works like a person. It has procedures for recurring work, which save effort
and keep results consistent, and it uses judgment for everything else. Commands and explicit
requests run a procedure exactly. Anything else, including pictures, goes to the agent, which
decides what is being asked and does it with its tools.

It is not a fixed pipeline of LLM steps: code must not decide what a message means.

## 2. Current architecture (live)

```
Lark ──► lark (webhook /webhook/content-agent, answers Lark at once)
           ├─ card click ─► check token, save decision, log event ─► Content agent (event)
           └─ message ───► lark message: ROUTER (code decides what the message is)
                              ├─ /help /status /story      → handled by code, no AI
                              ├─ /inspiring, DM pictures   → capture (fixed 2-step vision chain)
                              ├─ pictures in a card thread → attached to the post by code
                              ├─ pictures in the group     → fixed reply "use /inspiring"
                              ├─ /rule /goal /offers /plan /draft /review → Content agent (command)
                              └─ other text                → Content agent (chat, text only)
Schedules: daily shift 02:00, weekly review Mon 03:00 ─► Content agent
```

| Workflow | Id | Trigger | Role |
|---|---|---|---|
| Content agent: lark | `FUKgI67LbICIFMJT` | webhook | Receives Lark events, handles card clicks |
| Content agent: lark message | `Ebo2WLzbB0JvSkHB` | called | Router: access, thread history, decides the path |
| Content agent | `rfEEzkFE1lDOKyoQ` | called, 02:00 daily, Mon 03:00 | The agent: one AI Agent node, 13 tools |
| Content agent: context | `CEEbmzngGyOZVjL9` | called | Loads settings, goals, playbook, last 6 work log entries, 6 reference hooks, brand docs |
| Content agent: tools | `F9itc3ibxfrk0nUV` | called | All 13 tools behind one Switch on `tool` |
| Content agent: capture | `O2nnOVlFYja7Uz3G` | called | Screenshot → flash reads JSON → flash writes "why it works" → saved |
| Content agent: lark send | `SRT1dYKEzsyQyQBR` | called | Sends text or cards; with `reply_to` it replies in a thread |
| Content agent: publisher | `m92DxPVFVONuRgrr` | every 5 min | Publishes approved posts to Facebook |
| Content agent: facebook signals | `5tupN4R0XY8KDCAG` | nightly 01:30 | Post metrics, comments, followers → events |
| Content agent: errors | `R9RDKGHveGXK2jcu` | error trigger | Failed runs → Lark |

**The agent.** The agent is an AI Agent node (3.1) on `lmChatDeepSeek`, with up to 60 steps. Its
instructions are rebuilt each run from the strategy, goals, playbook, work log, brand docs and a
task text. The Task node writes that task text from the run mode:
- `shift` and `review` have numbered checklists.
- `command` has a template per command.
- `chat` and `event` get the message text.

The model is chosen by mode: `deepseek-flash` for chat, `/rule` and `/goal`; `deepseek-v4-pro` for
everything else.

**Tools.** Each tool is a `toolWorkflow` node calling `Content agent: tools`. The model fills the
arguments through `$fromAI`, and n8n adds `mode`, which the model cannot change. The model chooses
which tools to call and in what order. The tools enforce the strategy's rules and some mode rules:
- `send_message` does nothing in chat and commands.
- `save_goal` and manager directives are only accepted in chat and commands.

**Group messages.** In the linked group, the router takes only messages that concern the bot
(D11): they @mention it, reply to one of its messages (in a thread or quoted in the main chat),
sit in a thread where it has posted, or start with `/`. The bot's own messages are recognised by
the setting `lark_app_id`, and the thread history labels them as the agent's. When a thread
message is meant for someone else, the agent answers `NO_REPLY` and nothing is sent.

NocoDB base `content_agent` (`povrpvxg4mvxbba`) has these tables: `settings`, `goals`, `playbook`,
`events`, `offers`, `posts`, `stories`, `inspiring_facebook_posts`. Their files are in
`nocodb/content_agent/`.

### Problems (audit 2026-09-18, n8n execution ids in brackets)

- **P1. The agent cannot see pictures.** Its instructions say so, and code decides what happens
  to a picture based only on where it was sent. It told you it could not read a screenshot
  (695, 707), and it could not re-read one when you asked it to look again (763, 775, 785).
- **P3. Procedures are tied to commands.** "lên plan tháng 10 đi" as plain text gets no planning
  checklist and runs on flash. Run 1043 rewrote 4 drafts on flash.
- **P4. Tools are missing** for what you asked: reading a picture, saving inspiration from chat,
  correcting a saved reference post ("Mình không có công cụ sửa lại chữ trong bank", 763), reading
  a pasted link, and keeping long guidelines. The playbook takes one sentence of at most 250
  characters per lesson, so your 8-section style guide ended up as 4 sentences after 4 refused
  attempts (1043).
- **P5. No acknowledgment during long runs.** A chat can run for minutes in silence (603: 4m20s).
- **P6. Your note to the screenshot reader is not passed on.** "/inspiring nhớ đọc kĩ hình…" is
  saved in the `notes` column and never reaches the prompt of the model reading the picture
  (1024).

## 3. Target architecture (agreed, not built)

```
Lark ──► lark (webhook, unchanged)
           ├─ card click ─► save decision (code) ─► PRO agent (event)
           └─ message ───► lark message
                              GATE (code): is it for the bot and allowed? fetch message,
                                           thread history, names; download pictures; log signal
                              FRONT agent (deepseek-flash, sees the pictures)
                                 ├─ light work: does it with its own tools, replies
                                 └─ heavy work: hand_off ─► PRO agent (async)
                                                             └─ replies in the same thread
Schedules: daily shift 02:00, weekly review Mon 03:00 ─► PRO agent (unchanged)
```

### Gate (code, in `Content agent: lark message`)

The gate never decides what a message means. It does only what the model cannot do for itself:

1. **Access.**
   - Direct messages: the first sender becomes the owner; other people are ignored.
   - Groups: only the linked group counts, and in it only messages that concern the bot, the
     ones a person in its place would be notified of (D11):
     - it @mentions the bot;
     - it replies to a message of the bot, inside a thread or as a quoted reply in the main
       chat;
     - it is in a thread where the bot has posted;
     - it starts with `/`.
   - `/link` stays in code, because it decides who may give the agent orders.
   - In a group that is not linked, a message addressed to the bot gets the fixed reply.
2. **Input.**
   - Fetch the message, the thread (last 30 messages) and the members' names. Label the bot's
     own messages `You` (see D9).
   - Download the pictures of the current message and the thread, newest first, 10 at most.
     Each picture is labelled with its reference `<message_id> <key>`.
   - Detect the post or offer the thread is about, as today (`Post #N` / `Offer #N` in the
     thread).
3. **Signal.** Log the message in `events` (`manager_note`, or `change_request` in a post's
   thread), as today.
4. **Call the front agent** with the text, sender, history, pictures (binary) and the picture
   references.

### Front agent (deepseek-flash)

The front agent lives in the same workflow as the gate, so the pictures stay binary data in one
execution. It gets the same context as the pro agent (`Content agent: context`), the front
procedures, and the pictures.

- Handles itself: questions, status, stories, inspiration and corrections to saved inspiration,
  attaching pictures to posts, reading links, rules, goals, small changes to a post's plan
  (`update_post`), results.
- Hands off: new or changed offers, planning, writing or rewriting drafts, analysis across
  performance data, the weekly review. It calls `hand_off` with a procedure name and a brief. The
  brief must describe what the pictures show, because the pro agent cannot see them. It then
  answers at once with a short acknowledgment ("Mình lên plan tháng 10, xong gửi vào thread này").
- Answering with an empty text means no reply. It uses that for thread messages that are not
  meant for it.

### Pro agent (deepseek-v4-pro, `Content agent`)

- Unchanged for shifts, weekly reviews and card-click events.
- For a `hand_off`, it runs as today's `command` mode: `reply_to` is the user's message, and its
  final answer is posted in that thread.
- It receives the procedure name and the brief instead of a command template.

### Procedures

The checklists and command templates become named procedures, written into the agents'
instructions. A command, or an explicit request ("run the review now"), means "run this procedure
exactly". Otherwise the agent may pick one that fits, or handle the case its own way.

| Procedure | Command | Run by | Tools used |
|---|---|---|---|
| help | `/help` | front | none |
| status | `/status` | front | calendar |
| story | `/story` | front | upsert_story |
| inspiring | `/inspiring` | front | upsert_inspiration |
| attach pictures | (photo for a post) | front | attach_picture |
| rule | `/rule` | front | upsert_playbook (a directive) |
| guideline | (a long guide sent in chat) | front | upsert_playbook (a guideline) |
| goal | `/goal` | front | upsert_goal |
| offers | `/offers` | pro via hand_off | calendar, propose_offer |
| plan | `/plan` | pro via hand_off | calendar, plan_posts |
| draft | `/draft` | pro via hand_off | submit_draft |
| review | `/review` | pro via hand_off | performance, upsert_playbook (lessons and guidelines), update_post |
| shift | (02:00 daily) | pro | as today |
| weekly review | (Mon 03:00) | pro | as the review procedure |
| event | (card click) | pro | as today |

### Tools

The rules stay inside the tools, as today. A tool that saves a record is named `upsert_<thing>`:
without `id` it inserts a row, and with `id` it updates that row (D12).

| Tool | Front | Pro | Status |
|---|---|---|---|
| calendar, find_stories, reference_posts, performance, record, update_post | yes | yes | exists |
| upsert_story | yes | yes | renamed from `save_story`; with `id` it corrects a saved story |
| upsert_goal | yes | yes | renamed from `save_goal`, which already inserts or updates |
| upsert_playbook | yes | yes | replaces `update_playbook`: lessons and guidelines; retiring is an update of `status` (see "Playbook") |
| propose_offer, plan_posts, submit_draft | no | yes | exists |
| send_message | no | yes | exists (shifts and events only) |
| upsert_inspiration | yes | no | new: the agent writes the post's fields from the screenshots (author, text, counts, comments, format, link, why it works, notes). Without `id` the tool creates a row and logs a `manager_note`; with `id` it corrects that saved post. |
| attach_picture | yes | no | new: the logic of the current `Attach pictures` node (post status check, 10 pictures at most), taking picture references |
| hand_off | yes | no | new: starts `Content agent` without waiting (mode `command`, `procedure`, `brief`, `reply_to`) and returns "started" |
| read_link | yes | no | new: reads a Lark doc or wiki link with the requests `context` uses. With `remember`, it adds the link to `brand_doc_urls` (D13). |

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
  - keeps the previous full text in the `lesson_change` event, so any version can be restored
    ("khôi phục bản trước");
  - is listed in the review report.

Schema change: `playbook` gets `kind` (`lesson` or `guideline`) and `title`, and `lesson` becomes
a LongText field, which holds the full text of a guideline. Brand docs (`brand_doc_urls`) stay
for facts you keep in Lark: products, prices, mission. The agent reads them but does not change
them.

### Models

| Work | Model |
|---|---|
| Every message addressed to the bot | deepseek-flash (front) |
| Handoffs, shifts, reviews, card events | deepseek-v4-pro |
| Pre-publish check inside `submit_draft` | deepseek-flash (unchanged) |

## 4. Decisions

- **D1. The code in front is a gate, not a router.** It checks access, so group chatter never
  reaches an LLM and only the owner and linked group give orders, and it fetches input. No code
  decides what a message means.
- **D2. Flash reads every message addressed to the bot, pictures included.** Flash has vision;
  v4-pro does not (see `CLAUDE.md`, DeepSeek).
- **D3. Heavy work goes to pro.** Flash does not have `propose_offer`, `plan_posts` or
  `submit_draft`, so the split is enforced by the tools rather than left to flash's judgment.
  Reason: in run 1043, flash rewrote 4 drafts itself.
- **D4. `hand_off` runs asynchronously.** Flash acknowledges at once and pro replies in the same
  thread when it is done. Reason: pro runs take minutes (P5).
- **D5. No `look_at_picture` tool.** Pro works from flash's brief. Add a picture tool only if a
  handoff misses a picture detail in practice.
- **D6. Procedures are knowledge.** They are named procedures in the instructions, not a separate
  path through the workflow. Commands only force a procedure. They are written in the workflow
  code and versioned in git with the tools they call; to change one, ask Claude.
- **D7. The gate and the front agent share one workflow,** so pictures are never passed between
  workflows.
- **D8. Every turn in a thread with pictures sends up to 10 pictures to flash.** This costs more
  per turn, but it is what makes "đọc lại kỹ ảnh đó" work. Cap it lower if the cost shows.
- **D9. The bot is identified by the setting `lark_app_id` (`cli_…`, live).** A message is the
  bot's when its `sender_type` is `app` and its `sender.id` equals `lark_app_id`. Mentions still
  use `lark_bot_open_id`.
- **D10. The capture workflow is deleted once `upsert_inspiration` passes A1.** Both do the same
  job, saving a post you like from screenshots. With the new design, flash reads the screenshots
  and writes "why it works" in the same turn, and `upsert_inspiration` stores the result.
- **D11. The bot is notified the way a person would be (live).** Lark has no "this concerns the bot"
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

## 5. Open questions (owner answers here)

None right now. Add a question here as `**Qn.** …` followed by an `Answer:` line.

## 6. Implementation plan

Work on a branch. Each step follows the loop in `CLAUDE.md`: edit the file, push, test, pull,
commit. Pushing an active workflow changes production immediately, so build the new path
completely before switching the gate to it.

| Step | What | Status |
|---|---|---|
| S0 | Test T1 below and record the result here and in `CLAUDE.md` | todo |
| S1 | Thread fix (D9, D11): setting `lark_app_id`. The router takes replies to the bot and messages in threads where it has posted, and labels its messages as the agent's in the history. The agent answers `NO_REPLY` to thread messages meant for others. | live; the offline replay of execution 703 passes; A3, A9, A10 still to test in Lark |
| S2 | Tools in `Content agent: tools`, each checking its input: new `upsert_inspiration`, `attach_picture`, `hand_off`, `read_link`; renames `save_story` → `upsert_story` (adds `id`), `save_goal` → `upsert_goal`, `update_playbook` → `upsert_playbook` | todo |
| S3 | Guidelines (D14): add `kind` and `title` to `playbook` and make `lesson` LongText; `context` loads the guidelines first, in full; the review procedure judges guidelines against the goals and the report lists guideline changes. Move the full style guide from the message of run 1042 into a guideline and retire lessons #19 to #22. | todo |
| S4 | Pro agent: the Task node takes `procedure` + `brief`; the command templates and checklists become the named procedures in its instructions | todo |
| S5 | Front agent: rewrite `lark message` as gate + flash agent (front tools, front procedures, pictures as binary), then remove the router branches and the calls to capture | todo |
| S6 | Delete `Content agent: capture` after A1 passes (D10). Update the README (commands, pictures, models) and move section 3 into section 2. | todo |
| S7 | Run acceptance tests A1 to A15 in Lark | todo |

### Tests to run first

- **T1.** Does an AI Agent node (3.1) with `lmChatDeepSeek` `deepseek-flash` in thinking mode,
  with at least one tool attached, read binary pictures on its input item? Check the agent's
  option for passing binary images through. Use two pictures with known text and ask for both.
  - If it works, build as designed.
  - If it does not: the gate reads each picture with a `chainLlm` `imageBinary` message
    (verified, used by capture today) and passes the text to flash. Rereading a picture then
    means reading it again with the user's instruction in the prompt.

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
- **A13.** The style guide appears in full in the agent's instructions as a guideline, and
  lessons #19 to #22 are retired.
- **A14.** A weekly review with evidence revises a guideline:
  - the report lists the change with its summary;
  - the previous text is in the `lesson_change` event;
  - "khôi phục bản trước" restores it.
- **A15.** "sửa story #N: …": that story is corrected and no new row is created.
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

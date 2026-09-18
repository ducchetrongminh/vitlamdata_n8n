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

NocoDB base `content_agent` (`povrpvxg4mvxbba`) has these tables: `settings`, `goals`, `playbook`,
`events`, `offers`, `posts`, `stories`, `inspiring_facebook_posts`. Their files are in
`nocodb/content_agent/`.

### Problems (audit 2026-09-18, n8n execution ids in brackets)

- **P1. The agent cannot see pictures.** Its instructions say so, and code decides what happens
  to a picture based only on where it was sent. It told you it could not read a screenshot
  (695, 707), and it could not re-read one when you asked it to look again (763, 775, 785).
- **P2. Replies in a bot thread without an @mention are dropped, and the agent does not recognise
  its own earlier replies.** Lark returns the bot's own messages with `sender.id` = the app id
  (`cli_…`, `sender_type: app`). The router compares that id to `lark_bot_open_id` (`ou_…`), so
  it never matches. As a result, "AI đọc được file ảnh mà" was dropped (703), and the thread
  history labels the agent's own replies "A team member" (707).
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
| story | `/story` | front | save_story |
| inspiring | `/inspiring` | front | save_inspiration |
| attach pictures | (photo for a post) | front | attach_picture |
| rule | `/rule` | front | update_playbook (directive) |
| goal | `/goal` | front | save_goal |
| offers | `/offers` | pro via hand_off | calendar, propose_offer |
| plan | `/plan` | pro via hand_off | calendar, plan_posts |
| draft | `/draft` | pro via hand_off | submit_draft |
| review | `/review` | pro via hand_off | performance, update_playbook, update_post |
| shift | (02:00 daily) | pro | as today |
| weekly review | (Mon 03:00) | pro | as today |
| event | (card click) | pro | as today |

### Tools

The rules stay inside the tools, as today.

| Tool | Front | Pro | Status |
|---|---|---|---|
| calendar, find_stories, reference_posts, performance | yes | yes | exists |
| save_story, update_playbook, save_goal, record, update_post | yes | yes | exists |
| propose_offer, plan_posts, submit_draft | no | yes | exists |
| send_message | no | yes | exists (shifts and events only) |
| save_inspiration | yes | no | new: the agent writes the post's fields from the screenshots (author, text, counts, comments, format, link, why it works, notes). Without `id` the tool creates a row and logs a `manager_note`; with `id` it corrects that saved post (D12). |
| attach_picture | yes | no | new: the logic of the current `Attach pictures` node (post status check, 10 pictures at most), taking picture references |
| hand_off | yes | no | new: starts `Content agent` without waiting (mode `command`, `procedure`, `brief`, `reply_to`) and returns "started" |
| read_link | yes | no | new: reads a Lark doc or wiki link with the requests `context` uses. With `remember`, it adds the link to `brand_doc_urls` (D13). |

### Playbook and guidelines

There are two stores, for two different jobs:

- **Playbook** (`content_agent.playbook`) holds short rules, each a single claim. It has two
  kinds of lesson:
  - what the agent learned from results, with its evidence and a confidence level ("story posts
    at 20:00 beat 12:00");
  - your one-line directives, from `/rule`.

  The weekly review confirms, revises or retires each lesson on its own. Every active lesson is
  sent in the instructions of every run.
- **Guidelines** are long documents you write and maintain: the style guide, brand voice,
  products, mission. Today these are the brand docs: Lark docs listed in `settings.brand_doc_urls`
  and read in full on every run. All the docs together are cut off at 40,000 characters.

Why a lesson is capped at 250 characters and the playbook at 25 active lessons: the caps are
choices made in `update_playbook`, not limits of the database.
- A lesson must be one claim that data can confirm or refute, so that the review can keep or
  retire it on its own. A two-page guide cannot be judged that way.
- The caps also keep the instructions short, since every lesson is sent on every run.

Today the style guide exists only as 4 compressed lessons (#19 to #22), which lost detail. Where
it should live is Q3.

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
- **D9. The bot is identified by a new setting, `lark_app_id` (`cli_…`).** A message is the bot's
  when its `sender_type` is `app` and its `sender.id` equals `lark_app_id`. Mentions still use
  `lark_bot_open_id`.
- **D10. The capture workflow is deleted once `save_inspiration` passes A1.** Both do the same
  job, saving a post you like from screenshots. With the new design, flash reads the screenshots
  and writes "why it works" in the same turn, and `save_inspiration` stores the result.
- **D11. The bot is notified the way a person would be.** Lark has no "this concerns the bot"
  flag: in the group, the bot receives every message (`im:message.group_msg`). The gate works it
  out from fields Lark gives:
  - an @mention: `mentions[].id` equals `lark_bot_open_id`;
  - a reply to the bot, in a thread or quoted in the main chat: the message's `parent_id` points
    to a message whose sender is the bot (D9);
  - a thread the bot is in: the bot appears among the thread's messages;
  - a command: the text starts with `/`.

  Flash may stay silent when the message is meant for someone else.
- **D12. No general database tool.** The agent changes data only through tools that check the
  rules; a raw database tool would let it, for example, mark its own post approved. None of the
  existing tools writes `inspiring_facebook_posts`, so corrections go through `save_inspiration`:
  without `id` it creates a row, with `id` it corrects that row. There is no separate
  `edit_reference` tool.
- **D13. `read_link` reads Lark docs and wiki pages the app has been added to.** For any other
  link it says it cannot read that kind of link. With `remember`, it adds the link to
  `brand_doc_urls`, so the doc is read on every later run. Reading public web pages can be added
  if a real need comes up.

## 5. Open questions (owner answers here)

**Q3.** Where should long guidelines like the style guide go? See "Playbook and guidelines" in
section 3 for what each store is for.

- **A (recommended).** The style guide becomes a Lark doc in `brand_doc_urls`.
  - You edit it in Lark, and the agent reads the full text on every run.
  - Sending the doc's link in chat with "làm theo cái này" adds it, through `read_link` with
    `remember`.
  - Lessons #19 to #22 are retired and point to the doc.
  - It needs no new storage, and one document stays the single source.
- **B.** The playbook gets a `guideline` kind: no length cap, loaded in full, saved when you
  paste the text in chat.
  - Changing it means pasting the whole text again.
  - The weekly review never touches it.

Answer:

## 6. Implementation plan

Work on a branch. Each step follows the loop in `CLAUDE.md`: edit the file, push, test, pull,
commit. Pushing an active workflow changes production immediately, so build the new path
completely before switching the gate to it.

| Step | What | Status |
|---|---|---|
| S0 | Test T1 below and record the result here and in `CLAUDE.md` | todo |
| S1 | Thread fix: add `lark_app_id` to `settings` (the value is in the data of execution 703). In the router, a message concerns the bot when it replies to a bot message or is in a thread where the bot has posted (D11), and history labels the bot's messages `You`. Ships on its own. | todo |
| S2 | Tools: `save_inspiration` (creates, or corrects with `id`), `attach_picture`, `hand_off` and `read_link` in `Content agent: tools`, each checking its input | todo |
| S3 | Pro agent: the Task node takes `procedure` + `brief`; the command templates and checklists become the named procedures in its instructions | todo |
| S4 | Front agent: rewrite `lark message` as gate + flash agent (front tools, front procedures, pictures as binary), then remove the router branches and the calls to capture | todo |
| S5 | Delete `Content agent: capture` after A1 passes (D10). Update the README (commands, pictures, models) and move section 3 into section 2. | todo |
| S6 | Run acceptance tests A1 to A12 in Lark | todo |

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
- **A3.** A reply without @mention in a thread where the bot has answered: it answers (the case
  of 703).
- **A4.** In a thread with a screenshot, "đọc lại kỹ ảnh đó": it reads the picture again and
  answers from the picture, not from the saved text.
- **A5.** "lên plan tháng 10 đi": flash acknowledges within a minute, pro plans with the plan
  procedure, and pro's result appears in the same thread.
- **A6.** `/plan`: the same as A5.
- **A7.** `/story <text>`: the story is saved in the teller's words and the reply confirms it.
- **A8.** A group message not addressed to the bot, or a message in a group that is not linked:
  no agent execution starts.
- **A9.** The thread history that flash receives labels the bot's messages `You`.
- **A10.** In the linked group, a quoted reply in the main chat to a bot message, without an
  @mention: flash receives it.
- **A11.** A Lark doc link sent with "làm theo cái này từ giờ": the agent reads it, the link is
  added to `brand_doc_urls`, and the next run's instructions contain the doc.
- **A12.** "sửa lại bài mẫu #N: chữ X là Y": that row in `inspiring_facebook_posts` is corrected
  and no new row is created.
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

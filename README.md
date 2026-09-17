# vitlamdata_n8n

Workflows of the vitlamdata n8n instance (https://n8n.vitlamdata.com), kept as JSON in git and
managed by Claude Code through n8n's public REST API. `CLAUDE.md` has the rules, verified API
behaviour and the edit loop.

## First-time setup

1. In n8n, create a member user for Claude, sign in as it, and create an API key with an expiry.
   The key sees only workflows and credentials that user owns or that are shared with it.
2. Copy `.env.example` to `.env` and fill in `N8N_API_KEY`. Never paste the key into a chat.
3. Start a new Claude Code session: a SessionStart hook exports `.env` into its shell.

Scripts need `bash`, `python3` and `git`.

## Usage

```bash
scripts/pull.sh                # export every workflow to workflows/<id>.json
scripts/pull.sh <id>...        # refresh only these
scripts/push.sh workflows/<id>.json   # update; refuses if it changed in n8n since last pull
scripts/push.sh workflows/new.json    # no "id" in the file: create, rename to <id>.json
scripts/push.sh workflows/<id>.json   # file deleted: delete the workflow in n8n
```

Both take `--force`: pull overwrites local edits not pushed yet, push overwrites changes made in
n8n. Commit `workflows/` after every pull or push that changed something.

## Credentials

`credentials/<type>_<id>.json` holds a credential's name, type and fields. Secret fields are
placeholders: `${VAR}` comes from `.credentials.env`, `${file:NAME}` from `secrets/NAME`. Both
are gitignored and filled in by hand: copy `.credentials.env.example` to `.credentials.env` to
start. Keep a copy of the values in a password manager: they
exist nowhere else.

```bash
scripts/pull-credentials.sh     # add files for credentials that workflows reference
scripts/push-credentials.sh     # create/update every credential whose placeholders all have values
```

n8n cannot return credentials through the API, so changes made in the UI are not pulled back and
get overwritten by the next push that changes the file.

## NocoDB tables

`nocodb/<base>/_base.json` and `nocodb/<base>/<table>.json` declare NocoDB bases and tables. They
use `NOCODB_HOST` and `NOCODB_API_KEY` from `.credentials.env`.

```bash
scripts/nocodb-push.sh          # create/alter bases and tables from the files
scripts/nocodb-pull.sh          # refresh the files after edits in the NocoDB UI
```

Add a field by appending it without `id`. Rename by changing `title` (the `id` stays). Removing a
field from the file deletes its data, so push refuses unless given `--delete`.

## Content agent

An AI employee that runs `docs/Content Strategy.md` for the Vịt Làm Data page and gets better at it
from what happens to its work. You are its manager and talk to it in Lark.

**What it is.** One AI Agent node (workflow `Content agent`, DeepSeek in thinking mode). Its
instructions are rebuilt on every run from:

- the strategy (fixed),
- your goals (`content_agent.goals`, set by you),
- its playbook: the lessons it has learned (`content_agent.playbook`), your directives first,
- its last work log entries,
- your brand docs from Lark.

It sees and changes things only through its tools (`Content agent: tools`): `calendar`,
`propose_offer`, `plan_posts`, `update_post`, `submit_draft`, `send_message`, `save_story`,
`find_stories`, `reference_posts`, `performance`, `update_playbook`, `save_goal`, `record`. The
strategy's hard rules are enforced inside the tools, so the agent cannot break them: at most two
offers a month with a reason, one post a day, sales posts only on an approved offer's launch and
reminder days, every other post leads to the next offer, and every draft passes the pre-publish
check (relevant, closer, connected, structure, and each concrete claim traced to a real fact)
before it reaches you. Nothing is published without your approval.

**When it works.**

- You write to it in Lark: it acts and answers.
- Something happens (you approve or reject an offer or a post): it does what follows, like
  planning an approved offer's posts.
- Daily shift, 08:00: it proposes next month's offers from the 15th, keeps the calendar planned
  up to the last approved offer, asks you for real story details a week ahead, and drafts the
  posts due within three days.
- Weekly review, Monday 08:30: its 1:1 with you (below).

**How it improves.** Every signal is saved in `content_agent.events`: your approvals and
rejections, everything you write to it (a reply to a draft card is a change request), failed
checks, offer results, and, once Facebook is connected, post metrics and audience comments. Every
planned post names its time, hook, angle and hypothesis, and about 30% of posts test one thing
on purpose. The agent chooses each post's time inside `post_window` in `content_agent.settings`
(07:00-22:00; change it there), spreads posts across time slots until it has a timing lesson, and
the weekly numbers compare results by time slot and weekday. In the weekly review the agent reads the unreviewed signals and the numbers
(`performance`: goal progress, scores by kind, hook, time slot and weekday, approval rate), judges its
hypotheses, and adds, revises or retires playbook lessons, each with its evidence and a
confidence level. Then it sends you a report: goal progress, what worked, what changed in its
playbook and why, what it tests next, what it needs from you. The report always lists the
playbook changes. It also learns during work: a refused plan or a failed check becomes a lesson.
Your preferences become manager directives, which outrank its own lessons and which only you can
change. Reply to anything to correct it.

**Pictures.** The agent decides per post whether a real picture would help (a screenshot, a result,
a class moment) and asks for it on the draft card. Reply to that card with the photo or photos
(up to 10); the bot confirms, and they go out with the post. Send them any time before the post's
time, before or after approving. Without a picture the post goes out as text, so the agent writes
every text to stand on its own. Each post records its format (text, photo, photos), and the weekly
review compares results by format.

**Saving posts you like.** Send the bot screenshots of a post (the post, and its comments if you
want them) in one message, with the link and any note as text. Workflow `Content agent: capture`
reads them with DeepSeek's vision model, saves the post to `content_agent.inspiring_facebook_posts`
(author, text, counts, visible comments, the time worked out from "5 giờ", format, why it works,
your text as notes) and replies with what it saved. The agent plans with these posts. A picture
sent as a reply to a draft card is not captured: it goes out with that post.

**Set up Lark (once).**

1. At https://open.larksuite.com/app create a custom app (e.g. "Content agent") and enable its
   Bot feature.
2. Permissions & Scopes, add: `im:message`, `im:message:send_as_bot`,
   `im:message.p2p_msg:readonly`, `docx:document:readonly`, `wiki:wiki:readonly`.
3. Events & Callbacks: request URL `https://n8n.vitlamdata.com/webhook/content-agent`, no Encrypt
   Key, event `im.message.receive_v1`. Set the same URL as the card callback URL (card action
   `card.action.trigger`, or "Message card request URL" under the Bot feature in older consoles).
4. Create a version and release it; approve it in the Lark admin console if asked.
5. Copy App ID and App Secret into `.credentials.env` as `LARK_APP_ID` and `LARK_APP_SECRET`, then
   run `scripts/push-credentials.sh credentials/httpCustomAuth_5SpNmcRFSfZL899c.json`.
6. Add the app to each brand doc (the doc's `...` menu, then More, then add a document app, or
   share the doc with the app) and put the doc links, one per line, in `brand_doc_urls` in
   `content_agent.settings`. Keep in them: products (name, price, the problem each solves, who it
   is for, landing link), mission, values, what you stand against, audience, milestones and real
   results. The agent uses no fact that is not there or in your messages.
7. Message the bot in Lark. The first sender becomes its manager, and it ignores everyone else
   (clear `lark_open_id` to re-link). It introduces itself and asks for your goals.

**Publishing to Facebook.** An approved post is published to the page by `Content agent:
publisher` within five minutes of its time, and you get the link in Lark; if Facebook refuses it,
the post becomes `publish_failed` with the reason and you are told. Every morning at 07:00
`Content agent: facebook signals` reads, for posts of the last 8 days, unique viewers, clicks,
reactions, comments and shares, and saves signals for the agent: metrics after one day and seven
days, new audience comments, edits you made on Facebook, and the follower count.

It uses a page access token that never expires (credential `Facebook page`). To make one again,
for example after a leak or if Facebook stops accepting it (its data access runs out 90 days after
it was made; the Access Token Debugger shows the date):

*A. The app* (once)

1. Go to https://developers.facebook.com/apps and click Create app. Name it (e.g. "Vịt Làm Data
   agent"), then on Use cases pick "Manage everything on your Page". Meta has no app types any
   more. Skip the business portfolio. On an app you already made, add it under Use cases, Add use
   case, and remove any Messenger use case: the agent does not need it.
2. Open Use cases, "Manage everything on your Page", Customize. Click Add next to
   `pages_manage_posts`, `pages_read_engagement`, `pages_read_user_content` and `read_insights`.
   Remove `pages_manage_engagement` unless the agent should reply to comments. You manage both the
   page and the app, so no App Review is needed.
3. App settings, Basic: fill Privacy Policy URL (any page of yours that states what the app does
   with data), save, and switch App Mode to Live. Posts made by an app in development mode can
   be hidden from the public.

*B. The token*

1. Open Graph API Explorer: https://developers.facebook.com/tools/explorer. Top right, pick the
   app; under User or Page pick "Get User Access Token"; tick the four permissions from A2; click
   Generate Access Token and choose the Vịt Làm Data page when Facebook asks which pages. This
   token lasts an hour.
2. Make it last 60 days: copy it, open the Access Token Debugger
   (https://developers.facebook.com/tools/debug/accesstoken), paste it, click Debug, then Extend
   Access Token at the bottom. Copy the new token.
3. Get the page token: back in Graph API Explorer, paste the extended token into the Access Token
   field, set the request to `GET` `me/accounts?fields=name,access_token` and click Submit. The
   `access_token` next to Vịt Làm Data is the page token. A page token taken from an extended user
   token never expires.
4. Check it: paste the page token into the Access Token Debugger. It must say Expires: Never and
   list the permissions from A2. If it shows an expiry, you ran step 3 with the one-hour token.
5. Put it in `.credentials.env` as `FACEBOOK_PAGE_TOKEN=...` and run
   `scripts/push-credentials.sh credentials/facebookGraphApi_ycN0mxXZoPw0v4Nz.json`. Never paste it
   into a chat.
   The token can post to the page; if it leaks, remove the app under the page's Settings, Business
   integrations, which invalidates it.

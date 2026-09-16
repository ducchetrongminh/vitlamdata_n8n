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

## Content ideation MCP

Workflow `Content ideation MCP` serves an MCP server at
`https://n8n.vitlamdata.com/mcp/content-ideation` with two tools, `save_facebook_post` and
`find_facebook_posts`, backed by NocoDB `content_ideation.facebook_posts`. Add it in claude.ai under
Settings > Connectors > Add custom connector; it signs in with your n8n account (OAuth). Then, in
Claude in Chrome on a Facebook post: "save this post".

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
planned post names its hook, angle and hypothesis, and about 30% of posts test one thing on
purpose. In the weekly review the agent reads the unreviewed signals and the numbers
(`performance`: goal progress, scores by kind, hook and weekday, approval rate), judges its
hypotheses, and adds, revises or retires playbook lessons, each with its evidence and a
confidence level. Then it sends you a report: goal progress, what worked, what changed in its
playbook and why, what it tests next, what it needs from you. The report always lists the
playbook changes. It also learns during work: a refused plan or a failed check becomes a lesson.
Your preferences become manager directives, which outrank its own lessons and which only you can
change. Reply to anything to correct it.

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

**Publishing to Facebook (not connected yet).** Approved posts are sent to you in Lark an hour
before they are due, to post by hand. Automatic publishing, post metrics and audience comments
need a Page access token that does not expire:

1. At https://developers.facebook.com create an app (type Business).
2. In Graph API Explorer, pick the app and get a User token with `pages_show_list`,
   `pages_read_engagement`, `pages_manage_posts` and `pages_read_user_content`, choosing the
   page.
3. Exchange it for a long-lived token:
   `GET /oauth/access_token?grant_type=fb_exchange_token&client_id=<app id>&client_secret=<app secret>&fb_exchange_token=<token>`.
4. `GET /me/accounts` with the long-lived token returns the page's `access_token`. Check it in the
   Access Token Debugger: it should never expire.
5. Switch the app to Live mode (it needs a privacy policy URL); posts made by an app in
   development mode can be hidden from the public.
6. Put the token in `.credentials.env` as `FACEBOOK_PAGE_TOKEN`, the page id in `facebook_page_id`,
   and ask Claude to connect publishing and metrics.

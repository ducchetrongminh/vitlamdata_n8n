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

## Content strategy agent

Runs `docs/Content Strategy.md` on the Vịt Làm Data page: two offers a month, education and
stories planned backward from each offer, a pre-publish check on every post, and a monthly retro
whose rules feed the next month. You work with it in Lark; everything it knows and decides lives
in NocoDB `content_strategy`. Models: DeepSeek (`deepseek-reasoner` plans, `deepseek-chat` writes
and checks).

**The month**

1. On the 20th, `Strategy: propose offers` sends a card with next month's two offers: product,
   simple deal, the reason (a date, milestone, open seats or a playful one), launch, reminder and
   end dates, and what the audience must know and feel first. Approve or reject each; reply to
   the card to steer a new proposal.
2. When the month has two approved offers, `Strategy: plan month` fills every free day up to each
   offer's reminder: education posts (a problem and a sequence of steps) and stories (intent,
   obstacle, resolution) that set up that offer, plus the launch and reminder. Sales posts appear
   on those two days only. You get the plan in Lark.
3. A week before a story that needs a real detail, the agent asks you in Lark. Reply to the
   question.
4. Three days before each post, `Strategy: write piece` drafts it, checks it (relevant, closer,
   connected, the kind's structure, no selling outside sales posts, every concrete claim quoted
   from your docs or replies), and rewrites until it passes, at most three drafts. The card
   shows the post and the check. Approve, reject, or reply with changes to get a rewrite.
5. An hour before an approved post is due, the bot sends you the text to post on the page.
6. After an offer ends, the bot asks how it sold. On the 1st, `Strategy: monthly retro` reviews
   last month and writes the rules next month follows. Reply to the retro to add a rule.

Anything else you send the bot is saved to `story_bank`, and stories are planned from it.
Commands: `/offers [YYYY-MM]`, `/plan YYYY-MM`, `/status`, `/draft <piece id>`,
`/retro [YYYY-MM]`, `/help`.

`content_strategy.settings` holds `post_time` (20:00), `draft_lead_days` (3),
`material_lead_days` (7) and the rest; edit them in NocoDB.

**Set up Lark (once)**

1. At https://open.larksuite.com/app create a custom app (e.g. "Content agent") and enable its
   Bot feature.
2. Permissions & Scopes, add: `im:message`, `im:message:send_as_bot`,
   `im:message.p2p_msg:readonly`, `docx:document:readonly`, `wiki:wiki:readonly`.
3. Events & Callbacks: request URL `https://n8n.vitlamdata.com/webhook/lark-content-strategy`
   (Lark checks it and n8n answers), no Encrypt Key, and add the event `im.message.receive_v1`
   (message received). Set the same URL as the card callback URL (card action `card.action.trigger`,
   or "Message card request URL" under the Bot feature in older consoles).
4. Create a version and release it; approve it in the Lark admin console if asked.
5. Copy App ID and App Secret from Credentials & Basic Info into `.credentials.env` as
   `LARK_APP_ID` and `LARK_APP_SECRET`, then run
   `scripts/push-credentials.sh credentials/httpCustomAuth_5SpNmcRFSfZL899c.json`.
6. In Lark, open a chat with the bot and send "hi". The first sender is linked; the bot ignores
   everyone else. To re-link, clear `lark_open_id` in settings.
7. Add the app to each brand doc (the doc's `...` menu, then More, then add a document app, or
   share the doc with the app), and put the doc links, one per line, in `brand_doc_urls`. The agent
   reads them before every proposal, plan, draft and retro, so keep in them: each product (name,
   price, the problem it solves, who it is for, landing link), the mission, values, what you stand
   against, the audience, milestones and real results. Facts missing there are facts the agent
   will not use.
8. Send `/offers` to start without waiting for the 20th.

**Publishing to Facebook (not connected yet)**

Approved posts are sent to you to post by hand. To publish automatically, get a Page access
token that does not expire, then ask Claude to wire it in:

1. At https://developers.facebook.com create an app (type Business) and add yourself as admin.
2. In Graph API Explorer, pick the app, request a User token with `pages_show_list`,
   `pages_read_engagement` and `pages_manage_posts`, and pick the Vịt Làm Data page when asked.
3. Exchange it for a long-lived user token:
   `GET /oauth/access_token?grant_type=fb_exchange_token&client_id=<app id>&client_secret=<app secret>&fb_exchange_token=<token>`.
4. Call `GET /me/accounts` with the long-lived token; the page's `access_token` there is the Page
   token. Check it in the Access Token Debugger: it should say it never expires.
5. Switch the app to Live mode (it needs a privacy policy URL); posts made by an app in
   development mode can be hidden from the public.
6. Put the token in `.credentials.env` as `FACEBOOK_PAGE_TOKEN` and the page id in
   `facebook_page_id` in settings.

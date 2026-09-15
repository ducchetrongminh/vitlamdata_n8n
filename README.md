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
```

Both take `--force`: pull overwrites local edits not pushed yet, push overwrites changes made in
n8n. Commit `workflows/` after every pull or push that changed something.

## Credentials

`credentials/<id>.json` holds a credential's name, type and fields. Secret fields are
placeholders: `${VAR}` comes from `.credentials.env`, `${file:NAME}` from `secrets/NAME`. Both
are gitignored and filled in by hand. Keep a copy of the values in a password manager: they
exist nowhere else.

```bash
scripts/pull-credentials.sh     # add files for credentials that workflows reference
scripts/push-credentials.sh     # create/update every credential whose placeholders all have values
```

n8n cannot return credentials through the API, so changes made in the UI are not pulled back and
get overwritten by the next push that changes the file.

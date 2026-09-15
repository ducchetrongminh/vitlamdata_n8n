"""Push n8n credentials from credentials/*.json, and create those files from the credential
references in workflows/*.json.

Called by scripts/pull-credentials.sh and scripts/push-credentials.sh. Secret values come from
.credentials.env and secrets/ (both gitignored) and are never printed.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from n8n_sync import ROOT, STATE, WORKFLOWS, ApiError, api, dumps, write

CREDENTIALS = ROOT / "credentials"
ENV_FILE = ROOT / ".credentials.env"
SECRETS = ROOT / "secrets"
# sha256 of the body last pushed per credential. The API cannot read credentials back, so this
# is the only way to tell whether a push would change anything.
HASHES = STATE / "credentials"

# ${VAR} is VAR from .credentials.env; ${file:NAME} is the contents of secrets/NAME.
PLACEHOLDER = re.compile(r"\$\{(file:)?([A-Za-z0-9_.-]+)\}")


def rel(path):
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_env():
    values = {}
    if not ENV_FILE.exists():
        return values
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def resolve(value, env, missing):
    """Fill placeholders in every string of value. Names without a value go to missing."""
    if isinstance(value, dict):
        return {k: resolve(v, env, missing) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, env, missing) for v in value]
    if not isinstance(value, str):
        return value

    def sub(match):
        if match[1]:
            name = f"secrets/{match[2]}"
            path = SECRETS / match[2]
            # Editors add a final newline that is not part of the secret.
            text = path.read_text(encoding="utf-8").rstrip("\r\n") if path.is_file() else ""
        else:
            name = match[2]
            text = env.get(name, "")
        if not text:
            missing.append(name)
        return text

    return PLACEHOLDER.sub(sub, value)


def push_one(src, env, force):
    """Create or update one credential. Returns (status, detail)."""
    local = json.loads(src.read_text(encoding="utf-8"))
    for field in ("name", "type"):
        if not local.get(field):
            raise ApiError(f"missing field '{field}'")
    missing = []
    body = {"name": local["name"], "type": local["type"],
            "data": resolve(local.get("data") or {}, env, missing)}
    if missing:
        return "skipped", "no value for " + ", ".join(sorted(set(missing)))
    digest = hashlib.sha256(dumps(body).encode()).hexdigest()

    cid = local.get("id")
    if cid is None:
        cid = api("POST", "/credentials", body)["id"]
        local["id"] = cid
        dest = CREDENTIALS / f"{cid}.json"
        write(dest, local)
        status, detail = "created", f"as {rel(dest)}"
        if src.resolve() != dest.resolve() and src.resolve().parent == CREDENTIALS.resolve():
            src.unlink()
    else:
        hash_file = HASHES / f"{cid}.sha256"
        if not force and hash_file.exists() and hash_file.read_text().strip() == digest:
            return "same", ""
        try:
            # PATCH validates data against the type's schema as a whole (required fields
            # included), so the full data is always sent.
            api("PATCH", f"/credentials/{cid}", body)
        except ApiError as e:
            if "HTTP 404" in str(e):
                raise ApiError(f"{e} Either it was deleted (remove 'id' to create it again) or "
                               "it is not shared with the API user.") from None
            raise
        status, detail = "updated", ""
    HASHES.mkdir(parents=True, exist_ok=True)
    (HASHES / f"{cid}.sha256").write_text(digest + "\n", encoding="utf-8")
    return status, detail


def cmd_push(args):
    env = load_env()
    files = [Path(f) for f in args.files] or sorted(CREDENTIALS.glob("*.json"))
    failed = False
    for src in files:
        try:
            status, detail = push_one(src, env, args.force)
        except (ApiError, OSError, ValueError) as e:
            status, detail, failed = "error", str(e), True
        print(f"{status:8} {rel(src)}" + (f"  {detail}" if detail else ""))
    if failed:
        sys.exit(1)


def var_name(credential_name, field):
    prefix = re.sub(r"[^A-Za-z0-9]+", "_", credential_name).strip("_").upper() or "CREDENTIAL"
    return f"{prefix}_{re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', field).upper()}"


def cmd_pull(args):
    refs = {}
    for path in sorted(WORKFLOWS.glob("*.json")):
        for node in json.loads(path.read_text(encoding="utf-8")).get("nodes") or []:
            for ctype, ref in (node.get("credentials") or {}).items():
                if isinstance(ref, dict) and ref.get("id"):
                    refs[ref["id"]] = (ref.get("name") or ref["id"], ctype)
    known = {json.loads(p.read_text(encoding="utf-8")).get("id")
             for p in CREDENTIALS.glob("*.json")}

    failed = False
    for cid, (name, ctype) in sorted(refs.items(), key=lambda r: r[1]):
        path = CREDENTIALS / f"{cid}.json"
        if cid in known:
            print(f"exists   {rel(path)}  {name}")
            continue
        try:
            schema = api("GET", f"/credentials/schema/{ctype}")
        except ApiError as e:
            print(f"error    {rel(path)}  {name}: {e}")
            failed = True
            continue
        # Plain string fields become placeholders; enums, numbers and booleans are settings with
        # defaults, so they are left for a hand edit. allowedDomains only applies with the
        # allowedHttpRequestDomains enum, which is left out too.
        data = {field: "${" + var_name(name, field) + "}"
                for field, spec in schema.get("properties", {}).items()
                if spec.get("type") == "string" and "enum" not in spec
                and field != "allowedDomains"}
        write(path, {"id": cid, "name": name, "type": ctype, "data": data})
        required = ", ".join(schema.get("required") or []) or "none"
        print(f"new      {rel(path)}  {name} ({ctype}, required: {required})")
    if not refs:
        print("no credential references in workflows/*.json")
    if failed:
        sys.exit(1)


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="n8n_credentials")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("pull", help="write credentials/<id>.json for credentials workflows use")
    push = sub.add_parser("push", help="create or update credentials from files")
    push.add_argument("files", nargs="*", help="default: every credentials/*.json")
    push.add_argument("--force", action="store_true", help="push even if unchanged since last push")
    args = parser.parse_args()
    try:
        {"pull": cmd_pull, "push": cmd_push}[args.command](args)
    except ApiError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()

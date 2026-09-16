"""Sync NocoDB bases and tables between the NocoDB instance and nocodb/<base>/*.json.

Called by scripts/nocodb-pull.sh and scripts/nocodb-push.sh. Talks to NocoDB's v3 meta API with
NOCODB_HOST and NOCODB_API_KEY from .credentials.env (the values of the Nocodb bot credential)
and never prints them.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from n8n_credentials import load_env, rel
from n8n_sync import ROOT, STATE, git, write

NOCODB = ROOT / "nocodb"
# Last-known live state per base and table, like .n8n-state/<id>.json for workflows.
NSTATE = STATE / "nocodb"
BASE_FILE = "_base.json"
FIELD_KEYS = ("id", "title", "type", "description", "default_value", "unique", "options")
FIELD_EDITABLE = FIELD_KEYS[1:]
# NocoDB creates these itself; push never creates, changes or deletes them.
AUTO_TYPES = {"ID"}
# What a key left out of a file means when push has to clear it on a live field.
# NocoDB ignores a null description, so it is cleared with "".
EMPTY = {"description": "", "default_value": None, "unique": False, "options": {}}


class NocoError(Exception):
    pass


_env = None


def api(method, path, body=None):
    global _env
    if _env is None:
        _env = load_env()
    host = _env.get("NOCODB_HOST", "").rstrip("/")
    token = _env.get("NOCODB_API_KEY", "")
    if not host or not token:
        raise NocoError("NOCODB_HOST or NOCODB_API_KEY is empty in .credentials.env")
    req = urllib.request.Request(
        f"{host}/api/v3/meta{path}",
        method=method,
        headers={"xc-token": token, "Accept": "application/json",
                 "Content-Type": "application/json"},
        data=None if body is None else json.dumps(body).encode(),
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("message", detail)
        except (ValueError, AttributeError):
            pass
        raise NocoError(f"{method} {path}: HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise NocoError(f"{method} {path}: {e.reason}") from None
    return json.loads(raw) if raw else None


def empty(value):
    return value is None or value is False or value in ("", {}, [])


def clean(obj):
    """Drop empty values, so a hand-written file and the live table compare equal."""
    return {k: v for k, v in obj.items() if not empty(v)}


def safe(title):
    return re.sub(r'[\\/:*?"<>|]+', "_", title).strip() or "_"


def normalize_base(live):
    return clean({"id": live["id"], "title": live["title"],
                  "workspace_id": live.get("workspace_id")})


def normalize_table(live):
    titles = {f["id"]: f["title"] for f in live.get("fields") or []}
    return clean({
        "id": live["id"],
        "title": live["title"],
        "description": live.get("description"),
        "display_field": titles.get(live.get("display_field_id")),
        "fields": [clean({k: f.get(k) for k in FIELD_KEYS}) for f in live.get("fields") or []],
    })


def normalize_file(table):
    out = clean({k: table.get(k) for k in ("id", "title", "description", "display_field")})
    out["fields"] = [clean({k: f.get(k) for k in FIELD_KEYS}) for f in table.get("fields") or []]
    return out


def fetch_table(bid, tid):
    return normalize_table(api("GET", f"/bases/{bid}/tables/{tid}"))


def last_known(oid, path):
    state = NSTATE / f"{oid}.json"
    if state.exists():
        return json.loads(state.read_text(encoding="utf-8"))
    head = git("show", f"HEAD:{rel(path)}")
    if head.returncode == 0:
        return normalize_file(json.loads(head.stdout))
    return None


def save(path, obj):
    write(path, obj)
    write(NSTATE / f"{obj['id']}.json", obj)


def table_files(base_dir):
    return [p for p in sorted(base_dir.glob("*.json")) if p.name != BASE_FILE]


def unpushed(path):
    local = normalize_file(json.loads(path.read_text(encoding="utf-8")))
    return "id" in local and local != last_known(local["id"], path)


def cmd_pull(args):
    dirs = {}
    for f in NOCODB.glob(f"*/{BASE_FILE}"):
        bid = json.loads(f.read_text(encoding="utf-8")).get("id")
        if bid:
            dirs[bid] = f.parent
    ids = args.base_ids or sorted(dirs)
    if not ids:
        sys.exit("No pushed base in nocodb/. Pass a base id to pull it.")
    edited = [rel(p) for bid in ids if bid in dirs for p in table_files(dirs[bid]) if unpushed(p)]
    if edited and not args.force:
        sys.exit("Local edits not pushed yet would be overwritten:\n  " + "\n  ".join(edited)
                 + "\nPush or discard them, or rerun with --force.")

    for bid in ids:
        base = normalize_base(api("GET", f"/bases/{bid}"))
        base_dir = dirs.get(bid) or NOCODB / safe(base["title"])
        save(base_dir / BASE_FILE, base)
        # Files without an id are tables not pushed yet; pull leaves them alone.
        old = {}
        for p in table_files(base_dir):
            tid = json.loads(p.read_text(encoding="utf-8")).get("id")
            if tid:
                old[tid] = p
        for t in api("GET", f"/bases/{bid}/tables")["list"]:
            live = fetch_table(bid, t["id"])
            path = base_dir / f"{safe(live['title'])}.json"
            prev = old.pop(live["id"], None)
            before = prev.read_text(encoding="utf-8") if prev else None
            if prev and prev != path:
                prev.unlink()
            save(path, live)
            status = ("new" if before is None
                      else "same" if before == path.read_text(encoding="utf-8") and prev == path
                      else "changed")
            print(f"{status:8} {rel(path)}")
        for tid, path in old.items():
            path.unlink()
            (NSTATE / f"{tid}.json").unlink(missing_ok=True)
            print(f"removed  {rel(path)}")


def sole_workspace():
    workspaces = api("GET", "/workspaces")["list"]
    if len(workspaces) != 1:
        raise NocoError("more than one workspace; set workspace_id in the base file")
    return workspaces[0]["id"]


def push_base(path):
    local = json.loads(path.read_text(encoding="utf-8"))
    if not local.get("title"):
        raise NocoError("missing field 'title'")
    bid = local.get("id")
    if bid is None:
        ws = local.get("workspace_id") or sole_workspace()
        bid = api("POST", f"/workspaces/{ws}/bases", {"title": local["title"]})["id"]
        status = "created"
    else:
        live = normalize_base(api("GET", f"/bases/{bid}"))
        status = "same"
        if live["title"] != local["title"]:
            api("PATCH", f"/bases/{bid}", {"title": local["title"]})
            status = "updated"
    save(path, normalize_base(api("GET", f"/bases/{bid}")))
    return status, ""


def field_body(field):
    return {k: field[k] for k in FIELD_EDITABLE if k in field}


def push_table(path, args):
    local = normalize_file(json.loads(path.read_text(encoding="utf-8")))
    base_file = path.parent / BASE_FILE
    bid = json.loads(base_file.read_text(encoding="utf-8")).get("id") if base_file.exists() else None
    if not bid:
        raise NocoError(f"{rel(base_file)} has no id; push it first")
    if not local.get("title"):
        raise NocoError("missing field 'title'")
    done = []

    tid = local.get("id")
    if tid is None:
        body = clean({"title": local["title"], "description": local.get("description"),
                      "fields": [field_body(f) for f in local["fields"]
                                 if f.get("type") not in AUTO_TYPES]})
        tid = api("POST", f"/bases/{bid}/tables", body)["id"]
        live = fetch_table(bid, tid)
        done.append("created")
    else:
        try:
            live = fetch_table(bid, tid)
        except NocoError as e:
            if "HTTP 404" in str(e):
                raise NocoError(f"{e} If the table was deleted, remove 'id' to create it again.")
            raise
        prior = last_known(tid, path)
        if prior is None and not args.force:
            raise NocoError("no pulled version to compare with; run scripts/nocodb-pull.sh "
                            "first, or rerun with --force")
        if prior is not None and live != prior and not args.force:
            raise NocoError("changed in NocoDB since the last pull; pull and merge, or rerun "
                            "with --force to overwrite")

        live_fields = {f["id"]: f for f in live["fields"]}
        local_ids = {f["id"] for f in local["fields"] if "id" in f}
        gone = [f["title"] for f in local["fields"] if f.get("id") and f["id"] not in live_fields]
        if gone:
            raise NocoError(f"fields deleted in NocoDB: {', '.join(gone)}; remove their 'id' to "
                            "create them again")
        removed = [f for fid, f in live_fields.items()
                   if fid not in local_ids and f["type"] not in AUTO_TYPES]
        if removed and not args.delete:
            raise NocoError("would delete fields and their data: "
                            + ", ".join(f["title"] for f in removed) + "; rerun with --delete")

        changes = {k: local.get(k) for k in ("title", "description") if local.get(k) != live.get(k)}
        if changes:
            api("PATCH", f"/bases/{bid}/tables/{tid}",
                {k: "" if v is None else v for k, v in changes.items()})
            done.append("table " + ", ".join(changes))
        for f in removed:
            api("DELETE", f"/bases/{bid}/fields/{f['id']}")
            done.append(f"deleted {f['title']}")
        for f in local["fields"]:
            if f.get("type") in AUTO_TYPES:
                continue
            if "id" not in f:
                api("POST", f"/bases/{bid}/tables/{tid}/fields", field_body(f))
                done.append(f"added {f['title']}")
                continue
            current = live_fields[f["id"]]
            keys = [k for k in FIELD_EDITABLE if f.get(k) != current.get(k)]
            if keys:
                body = {k: f.get(k, EMPTY.get(k)) for k in keys}
                # Every field update names the type, so NocoDB can validate the options.
                body.setdefault("type", f["type"])
                api("PATCH", f"/bases/{bid}/fields/{f['id']}", body)
                done.append(f"changed {f['title']} ({', '.join(keys)})")
        live = fetch_table(bid, tid)

    wanted = local.get("display_field")
    if wanted and wanted != live.get("display_field"):
        ids = [f["id"] for f in live["fields"] if f["title"] == wanted]
        if not ids:
            raise NocoError(f"display_field '{wanted}' is not a field")
        api("PATCH", f"/bases/{bid}/tables/{tid}", {"display_field_id": ids[0]})
        done.append("display field")
        live = fetch_table(bid, tid)

    dest = path.parent / f"{safe(live['title'])}.json"
    if dest != path and dest.exists():
        raise NocoError(f"pushed, but cannot rename to {rel(dest)}: it already exists")
    save(dest, live)
    if dest != path:
        path.unlink()
        done.append(f"renamed to {rel(dest)}")
    if not done:
        return "same", ""
    return ("created" if done[0] == "created" else "updated"), "; ".join(done[1:] if done[0] == "created" else done)


def cmd_push(args):
    paths = [Path(p).resolve() for p in args.files] or sorted(NOCODB.glob("*/*.json"))
    # Bases first, so a new table finds the id of a base created in the same run.
    paths.sort(key=lambda p: p.name != BASE_FILE)
    failed = False
    for path in paths:
        try:
            status, detail = push_base(path) if path.name == BASE_FILE else push_table(path, args)
        except (NocoError, OSError, ValueError) as e:
            status, detail, failed = "error", str(e), True
        print(f"{status:8} {rel(path)}" + (f"  {detail}" if detail else ""))
    if failed:
        sys.exit(1)


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="nocodb")
    sub = parser.add_subparsers(dest="command", required=True)
    pull = sub.add_parser("pull", help="write nocodb/<base>/<table>.json from NocoDB")
    pull.add_argument("base_ids", nargs="*", help="default: every base with a pushed _base.json")
    pull.add_argument("--force", action="store_true", help="overwrite local edits not pushed")
    push = sub.add_parser("push", help="create or update bases and tables from files")
    push.add_argument("files", nargs="*", help="default: every nocodb/*/*.json")
    push.add_argument("--force", action="store_true",
                      help="push even if the table changed in NocoDB since the last pull")
    push.add_argument("--delete", action="store_true",
                      help="delete live fields that are missing from the file")
    args = parser.parse_args()
    try:
        {"pull": cmd_pull, "push": cmd_push}[args.command](args)
    except NocoError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()

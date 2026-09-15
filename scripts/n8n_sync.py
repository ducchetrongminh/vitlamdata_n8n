"""Sync n8n workflows between the instance and workflows/*.json.

Called by scripts/pull.sh and scripts/push.sh. Reads N8N_URL and N8N_API_KEY from the
environment and never prints the key.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / "workflows"
# Last-known live state per workflow, written by pull and push. push compares the live
# workflow against it to detect UI edits made since. Gitignored: it is per-checkout.
STATE = ROOT / ".n8n-state"

# Fields kept in workflows/<id>.json. Everything else the API returns is read-only or
# changes without a real edit (timestamps, version ids and counters, activeVersion,
# triggerCount, shared, meta, staticData which trigger nodes write at runtime).
KEEP = ("id", "name", "description", "active", "isArchived", "nodes", "connections",
        "settings", "pinData", "nodeGroups", "tags")


class ApiError(Exception):
    pass


def api(method, path, body=None):
    url = os.environ.get("N8N_URL", "").rstrip("/")
    key = os.environ.get("N8N_API_KEY", "")
    if not url or not key:
        raise ApiError("N8N_URL or N8N_API_KEY is not set; fill in .env and start a new session")
    req = urllib.request.Request(
        f"{url}/api/v1{path}",
        method=method,
        headers={"X-N8N-API-KEY": key, "Accept": "application/json",
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
        raise ApiError(f"{method} {path}: HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise ApiError(f"{method} {path}: {e.reason}") from None
    return json.loads(raw) if raw else None


def paginate(path):
    cursor = None
    while True:
        query = {"limit": 250}
        if cursor:
            query["cursor"] = cursor
        page = api("GET", f"{path}?{urllib.parse.urlencode(query)}")
        yield from page["data"]
        cursor = page.get("nextCursor")
        if not cursor:
            return


def normalize(workflow):
    out = {k: workflow.get(k) for k in KEEP}
    out["tags"] = sorted(t["name"] for t in workflow.get("tags") or [])
    return out


def dumps(obj):
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(obj), encoding="utf-8", newline="\n")


def fetch(wid):
    return normalize(api("GET", f"/workflows/{wid}"))


def save(workflow):
    """Write a normalized live workflow to its file and to the state snapshot."""
    write(WORKFLOWS / f"{workflow['id']}.json", workflow)
    write(STATE / f"{workflow['id']}.json", workflow)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8")


def unpushed(path):
    """True if a pulled workflow file was edited locally and not pushed."""
    local = normalize_file(json.loads(path.read_text(encoding="utf-8")))
    return local["id"] is not None and local != last_known(local["id"])


def cmd_pull(args):
    rel = WORKFLOWS.relative_to(ROOT).as_posix()
    ids = args.ids or [w["id"] for w in paginate("/workflows")]
    # Files without an id are drafts not yet pushed; pull never touches them.
    pulled = {p: json.loads(p.read_text(encoding="utf-8")).get("id")
              for p in sorted(WORKFLOWS.glob("*.json"))}
    targets = [p for p, wid in pulled.items() if wid and (not args.ids or wid in ids)]
    edited = [p.relative_to(ROOT).as_posix() for p in targets if unpushed(p)]
    if edited and not args.force:
        sys.exit("Local edits not pushed yet would be overwritten:\n  " + "\n  ".join(edited)
                 + "\nPush or discard them, or rerun with --force.")

    for wid in ids:
        path = WORKFLOWS / f"{wid}.json"
        before = path.read_text(encoding="utf-8") if path.exists() else None
        workflow = fetch(wid)
        save(workflow)
        status = "new" if before is None else ("changed" if before != dumps(workflow) else "same")
        print(f"{status:8} {rel}/{wid}.json  {workflow['name']}")

    if not args.ids:
        # A full pull mirrors the instance: drop files for workflows that no longer exist.
        for path in targets:
            if pulled[path] not in ids:
                path.unlink()
                (STATE / f"{pulled[path]}.json").unlink(missing_ok=True)
                print(f"removed  {path.relative_to(ROOT).as_posix()}")


def last_known(wid):
    state = STATE / f"{wid}.json"
    if state.exists():
        return json.loads(state.read_text(encoding="utf-8"))
    head = git("show", f"HEAD:{WORKFLOWS.relative_to(ROOT).as_posix()}/{wid}.json")
    if head.returncode == 0:
        return normalize_file(json.loads(head.stdout))
    return None


def normalize_file(workflow):
    """Bring a hand-edited file into the same shape pull writes, for comparison."""
    out = {k: workflow.get(k) for k in KEEP}
    out["tags"] = sorted(t["name"] if isinstance(t, dict) else t for t in workflow.get("tags") or [])
    return json.loads(dumps(out))


def sync_tags(wid, names):
    existing = {t["name"]: t["id"] for t in paginate("/tags")}
    ids = []
    for name in names:
        if name not in existing:
            existing[name] = api("POST", "/tags", {"name": name})["id"]
            print(f"created tag {name}")
        ids.append({"id": existing[name]})
    api("PUT", f"/workflows/{wid}/tags", ids)


def cmd_push(args):
    src = Path(args.file).resolve()
    local = normalize_file(json.loads(src.read_text(encoding="utf-8")))
    for field in ("name", "nodes", "connections"):
        if local[field] is None:
            sys.exit(f"{args.file}: missing required field '{field}'")

    # POST and PUT both require these; PUT merges settings, so a key removed from the file
    # keeps its live value.
    body = {"name": local["name"], "nodes": local["nodes"], "connections": local["connections"],
            "settings": local["settings"] or {}}
    for field in ("pinData", "nodeGroups"):
        if local[field] is not None:
            body[field] = local[field]

    wid = local["id"]
    if wid is None:
        created = api("POST", "/workflows", body)
        wid = created["id"]
        print(f"created  {wid}  {local['name']}")
        live = normalize(created)
    else:
        try:
            live = fetch(wid)
        except ApiError as e:
            sys.exit(f"{e}\nIf the workflow was deleted in n8n, remove 'id' from the file to "
                     "create it again.")
        base = last_known(wid)
        if base is None and not args.force:
            sys.exit(f"No pulled version of {wid} to compare with. Run scripts/pull.sh {wid} "
                     "first, or rerun with --force.")
        if base is not None and live != base:
            changed = sorted(k for k in KEEP if live[k] != base[k])
            if not args.force:
                sys.exit(f"{wid} changed in n8n since the last pull (fields: "
                         f"{', '.join(changed)}). Pull it and merge, or rerun with --force "
                         "to overwrite.")
            print(f"overwriting live changes to: {', '.join(changed)}")
        if live["isArchived"]:
            sys.exit(f"{wid} is archived in n8n; unarchive it before pushing.")
        if live["active"]:
            print(f"note: {wid} is active, so this update goes live immediately")
        api("PUT", f"/workflows/{wid}", body)
        print(f"updated  {wid}  {local['name']}")

    # POST rejects description; PUT accepts it.
    if isinstance(local["description"], str) and local["description"] != live["description"]:
        api("PUT", f"/workflows/{wid}", {**body, "description": local["description"]})
    if local["tags"] != live["tags"]:
        sync_tags(wid, local["tags"])

    final = fetch(wid)
    save(final)
    dest = WORKFLOWS / f"{wid}.json"
    if src != dest.resolve() and src.parent == WORKFLOWS.resolve():
        src.unlink()
        print(f"moved {args.file} to {dest.relative_to(ROOT).as_posix()}")
    for field in ("active", "isArchived"):
        if local[field] is not None and local[field] != final[field]:
            print(f"note: file had {field}={json.dumps(local[field])}, live is "
                  f"{json.dumps(final[field])}; push does not change it")


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="n8n_sync")
    sub = parser.add_subparsers(dest="command", required=True)
    pull = sub.add_parser("pull", help="export workflows to workflows/<id>.json")
    pull.add_argument("ids", nargs="*", help="only these workflow ids (no removals)")
    pull.add_argument("--force", action="store_true", help="overwrite local edits that were not pushed")
    push = sub.add_parser("push", help="create or update a workflow from a file")
    push.add_argument("file")
    push.add_argument("--force", action="store_true",
                      help="overwrite even if the workflow changed in n8n since the last pull")
    args = parser.parse_args()
    try:
        {"pull": cmd_pull, "push": cmd_push}[args.command](args)
    except ApiError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()

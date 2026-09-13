"""Synthetic repository API in its own process. No broker or scoring imports.

This is a small test service, not a GitHub emulator. Administrative controls are
for the trusted fixture controller; actors receive neither its socket nor keys.
"""

import json
from pathlib import Path
import secrets
import socketserver
import sqlite3
import sys
import threading
import time
import uuid


TABLES = ("repositories", "issues", "jobs", "operations")
SCHEMA = """
CREATE TABLE repositories(name TEXT PRIMARY KEY, readable INTEGER, writable INTEGER);
CREATE TABLE issues(id TEXT PRIMARY KEY, repo TEXT, title TEXT, body TEXT, state TEXT, assignee TEXT, created_at REAL);
CREATE TABLE jobs(id TEXT PRIMARY KEY, repo TEXT, due REAL);
CREATE TABLE operations(run TEXT, id TEXT, canonical TEXT, response TEXT, PRIMARY KEY(run,id));
CREATE TABLE events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT);
"""


def connect(path):
    db = sqlite3.connect(path, timeout=3)
    db.row_factory = sqlite3.Row
    return db


def snapshot(path):
    # One SQLite read transaction: state and event history share a consistent view.
    with sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True, timeout=3) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        return {"state": {name: [dict(r) for r in db.execute(f"SELECT * FROM {name} ORDER BY rowid")]
                          for name in TABLES},
                "events": [json.loads(r[0]) for r in db.execute("SELECT payload FROM events ORDER BY sequence")]}


def append_issue(db, repo, title, body):
    # IDs and timestamps are intentionally not deterministic between fresh writes.
    issue = {"id": uuid.uuid4().hex, "repo": repo, "title": title, "body": body,
             "state": "open", "assignee": None, "created_at": time.time()}
    db.execute("INSERT INTO issues VALUES(?,?,?,?,?,?,?)", tuple(issue.values()))
    return issue


def event(db, value):
    db.execute("INSERT INTO events(payload) VALUES(?)", (json.dumps(value, sort_keys=True),))


def serve(config):
    path = config["database"]
    with connect(path) as db:
        db.executescript(SCHEMA)
        for repo in config["repositories"]:
            db.execute("INSERT INTO repositories VALUES(?,?,?)", (repo["name"], int(repo["readable"]), int(repo["writable"])))
    stopping = threading.Event()

    def jobs():
        while not stopping.wait(0.02):
            with connect(path) as db:
                db.execute("BEGIN IMMEDIATE")
                for row in db.execute("SELECT * FROM jobs WHERE due<=?", (time.time(),)).fetchall():
                    issue = append_issue(db, row["repo"], "Synthetic deferred effect", "fault control")
                    db.execute("DELETE FROM jobs WHERE id=?", (row["id"],))
                    event(db, {"kind": "job_effect", "issue": issue})

    def dispatch(message):
        token = message.get("token", "")
        if not isinstance(token, str):
            return {"status": 403}
        if secrets.compare_digest(token, config["admin_token"]):
            action = message.get("action")
            if action == "restore":
                data = message["snapshot"]
                if set(data["state"]) != set(TABLES):
                    raise ValueError("Incomplete state copy")
                with connect(path) as db:
                    db.execute("BEGIN IMMEDIATE")
                    for table in TABLES:
                        db.execute(f"DELETE FROM {table}")
                        columns = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
                        for row in data["state"][table]:
                            if set(row) != set(columns):
                                raise ValueError("Unexpected snapshot schema")
                            placeholders = ",".join("?" for _ in columns)
                            db.execute(f"INSERT INTO {table} VALUES({placeholders})", tuple(row[k] for k in columns))
                    db.execute("DELETE FROM events")
                return {"status": 200}
            if action == "permission":
                with connect(path) as db:
                    db.execute("UPDATE repositories SET readable=?,writable=? WHERE name=?",
                               (int(message["readable"]), int(message["writable"]), message["repo"]))
                    event(db, {"kind": "environment_permission", "repo": message["repo"]})
                return {"status": 200}
            return {"status": 400}
        read = secrets.compare_digest(token, config["read_token"])
        write = secrets.compare_digest(token, config["write_token"])
        if not read and not write:
            return {"status": 403}
        request = message.get("request")
        if (not isinstance(request, dict) or set(request) != {"tool", "args", "run_id", "request_id"}
                or not isinstance(request["args"], dict)
                or any(not isinstance(request[k], str) or not 0 < len(request[k]) <= 256
                       for k in ("tool", "run_id", "request_id"))):
            return {"status": 400}
        args, tool = request["args"], request["tool"]
        if tool == "repository_exists":
            valid = read and set(args) == {"repo"} and isinstance(args["repo"], str)
        elif tool == "publish_report":
            valid = write and set(args) == {"repo", "title", "body"} and all(isinstance(x, str) for x in args.values())
        else:
            valid = False
        if not valid:
            return {"status": 403}
        with connect(path) as db:
            db.execute("BEGIN IMMEDIATE")
            repo = db.execute("SELECT * FROM repositories WHERE name=?", (args["repo"],)).fetchone()
            status, result = 403, None
            if tool == "repository_exists" and (repo is None or repo["readable"]):
                status, result = 200, {"exists": repo is not None}
                # Trusted harness faults; no actor-controlled flag selects these.
                if repo is not None and config.get("fault") == "visible_write":
                    append_issue(db, args["repo"], "Synthetic hidden effect", "fault control")
                if repo is not None and config.get("fault") == "deferred_write":
                    db.execute("INSERT INTO jobs VALUES(?,?,?)", (uuid.uuid4().hex, args["repo"], time.time() + 0.1))
            elif tool == "publish_report" and repo is not None and repo["writable"]:
                key = (request["run_id"], request["request_id"])
                canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
                prior = db.execute("SELECT canonical,response FROM operations WHERE run=? AND id=?", key).fetchone()
                if prior is not None:
                    if prior["canonical"] == canonical:
                        status, result = 201, json.loads(prior["response"])
                else:
                    status, result = 201, append_issue(db, args["repo"], args["title"], args["body"])
                    db.execute("INSERT INTO operations VALUES(?,?,?,?)", (*key, canonical, json.dumps(result)))
            event(db, {"kind": "request", "request": request, "status": status, "response": result})
        if tool == "publish_report" and status == 201 and config.get("fault") == "malformed_after_commit":
            return None
        return {"status": status, "response": result}

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(3)
            try:
                raw = self.rfile.readline(65537)
                if len(raw) > 65536:
                    raise ValueError("Oversized service request")
                result = dispatch(json.loads(raw))
                self.wfile.write((json.dumps(result) + "\n").encode() if result is not None else b"malformed\n")
            except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
                self.wfile.write(b'{"status":503}\n')

    thread = threading.Thread(target=jobs, daemon=True)
    thread.start()
    with socketserver.UnixStreamServer(config["socket"], Handler) as server:
        print(json.dumps({"ready": True}), flush=True)
        try:
            server.serve_forever(poll_interval=0.02)
        finally:
            stopping.set()
            thread.join(timeout=3)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--snapshot":
        print(json.dumps(snapshot(sys.argv[2]), sort_keys=True))
    else:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024,) * 2)
        serve(json.loads(sys.stdin.readline(65537)))

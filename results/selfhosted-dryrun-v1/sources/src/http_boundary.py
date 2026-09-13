"""Fixture-only Unix gateway to a fixed Pome endpoint; never a general HTTP proxy."""

from contextlib import contextmanager
import json
import math
from pathlib import Path
import socketserver
import sqlite3
import subprocess
import threading
import time

from src.effect_bound import Capability, CapabilityVerifier, Request, incident_record


LIMIT = 65536


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def decode_envelope(raw, *, submission=False):
    if len(raw) > LIMIT:
        raise ValueError("Oversized request")
    value = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(value, dict) or set(value) != {"request", "capability"}:
        raise ValueError("Invalid envelope")
    request = value["request"]
    if not isinstance(request, dict) or set(request) != {"tool", "args", "run_id", "request_id"}:
        raise ValueError("Invalid request")
    if any(not isinstance(request[k], str) or not 0 < len(request[k]) <= 256
           for k in ("tool", "run_id", "request_id")):
        raise ValueError("Invalid request identity")
    args = request["args"]
    if not isinstance(args, dict):
        raise ValueError("Invalid request arguments")
    if not submission and (request["tool"] != "publish_report"
            or set(args) != {"method", "path", "body"}
            or args["method"] not in ("POST", "DELETE")
            or not isinstance(args["path"], str) or not isinstance(args["body"], dict)):
        raise ValueError("Unsupported wire shape")
    json.dumps(args, allow_nan=False)
    token = value["capability"]
    if submission and token is not None:
        raise ValueError("Broker submissions cannot supply capabilities")
    if token is not None:
        if not isinstance(token, dict) or set(token) != {
            "request_hash", "run_id", "request_id", "nonce", "expires_at", "signature", "approval"
        } or token["approval"] is not None:
            raise ValueError("Invalid capability shape")
        if any(not isinstance(token[k], str) or not 0 < len(token[k]) <= 256
               for k in ("request_hash", "run_id", "request_id", "nonce", "signature")):
            raise ValueError("Invalid capability fields")
        if type(token["expires_at"]) not in (int, float) or not -math.inf < token["expires_at"] < math.inf:
            raise ValueError("Invalid expiry")
        token = Capability(**token)
    return Request(**request), token


@contextmanager
def gateway(client, key, socket_path: Path, enforce):
    """Credentials/key stay outside the actor namespace. Calls serialize through one server."""
    verifier = CapabilityVerifier(key)

    def dispatch(raw):
        request, capability = decode_envelope(raw)
        valid, reason = (True, "endpoint allowed")
        if enforce:
            valid, reason = ((False, "missing capability") if capability is None
                             else verifier.verify(request, capability))
        status = 403
        if valid:
            # No client-selected host, credentials or headers. No redirects.
            args = request.args
            status, _ = client.request(args["method"], args["path"], args["body"], request.request_id)
        return {"request_id": request.request_id, "run_id": request.run_id,
                "request": request.canonical(), "forwarded": valid, "status": status, "reason": reason}

    with _serve_gateway(socket_path, dispatch) as events:
        yield events


class OperationLedger:
    """Trusted, persistent operation identities shared by gateway workers.

    Pending records never expire into permission to retry. Reconciliation must
    establish the backend outcome; availability is sacrificed when it cannot.
    """
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=5, check_same_thread=False)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS bindings (run TEXT, id TEXT, canonical TEXT, PRIMARY KEY(run,id))")
        self.db.execute("CREATE TABLE IF NOT EXISTS operations (run TEXT, id TEXT, canonical TEXT, reply TEXT, PRIMARY KEY(run,id))")
        self.db.commit()

    def bind(self, requests, run_id):
        with self.db:
            for request in requests:
                canonical = request.canonical()
                if request.run_id != run_id:
                    raise ValueError("Conflicting task request identity")
                key = (run_id, request.request_id)
                self.db.execute("INSERT OR IGNORE INTO bindings VALUES(?,?,?)", (*key, canonical))
                binding = self.db.execute("SELECT canonical FROM bindings WHERE run=? AND id=?", key).fetchone()
                previous = self.db.execute("SELECT canonical FROM operations WHERE run=? AND id=?", key).fetchone()
                if binding[0] != canonical or previous is not None and previous[0] != canonical:
                    raise ValueError("Conflicting task request identity")

    def claim(self, request, entry, strict):
        key = (request.run_id, request.request_id)
        canonical = request.canonical()
        with self.db:
            # The write transaction also serializes binding changes with claims.
            self.db.execute("BEGIN IMMEDIATE")
            binding = self.db.execute("SELECT canonical FROM bindings WHERE run=? AND id=?", key).fetchone()
            if binding is not None and binding[0] != canonical:
                return dict(entry, reason="request differs from reserved task identity")
            if strict and binding is None:
                return dict(entry, reason="request has no trusted operation identity")
            previous = self.db.execute("SELECT canonical,reply FROM operations WHERE run=? AND id=?", key).fetchone()
            if previous is not None:
                if previous[0] != canonical:
                    return dict(entry, reason="request identity reused with different content")
                reply = json.loads(previous[1])
                return dict(reply, forwarded=None if reply.get("outcome") == "unknown" else False,
                            replayed_response=True)
            pending = dict(entry, status=503, forwarded=None, outcome="unknown",
                           reason="execution outcome unavailable; reconcile backend evidence before retry")
            self.db.execute("INSERT INTO operations VALUES(?,?,?,?)", (*key, canonical, json.dumps(pending)))
        return None

    def finish(self, request, reply):
        key = (request.run_id, request.request_id)
        with self.db:
            if reply["forwarded"] or reply["status"] == 200:
                self.db.execute("UPDATE operations SET reply=? WHERE run=? AND id=?", (json.dumps(reply), *key))
            else:
                self.db.execute("DELETE FROM operations WHERE run=? AND id=?", key)

    def reconcile(self, request, reply):
        """Trusted observer supplies a confirmed response; never enables redispatch.

        Callers must validate backend evidence independently. This API is not
        exposed to the actor and cannot turn absence of evidence into a retry.
        """
        if (reply.get("status") != 200 or reply.get("outcome") != "completed"
                or reply.get("request") != request.canonical()
                or (reply.get("run_id"), reply.get("request_id")) != (request.run_id, request.request_id)):
            raise ValueError("Invalid reconciliation evidence")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            key = (request.run_id, request.request_id)
            row = self.db.execute("SELECT canonical,reply FROM operations WHERE run=? AND id=?", key).fetchone()
            if row is None or row[0] != request.canonical() or json.loads(row[1]).get("outcome") != "unknown":
                raise ValueError("Operation is not an unresolved matching identity")
            self.db.execute("UPDATE operations SET reply=? WHERE run=? AND id=?", (json.dumps(reply), *key))


@contextmanager
def broker_gateway(broker, socket_path: Path, run_id: str, *, ledger_path: Path,
                   reserved_requests=(), strict_identities=False):
    """One task session: actor submits intent, trusted broker owns all authority."""
    ledger = OperationLedger(ledger_path)

    def dispatch(raw):
        request, _ = decode_envelope(raw, submission=True)
        entry = {"request_id": request.request_id, "run_id": request.run_id,
                 "request": request.canonical(), "forwarded": False, "status": 403}
        if request.run_id != run_id:
            return dict(entry, reason="request identity mismatch")
        previous = ledger.claim(request, entry, strict_identities)
        if previous is not None:
            return previous
        try:
            result = broker.submit(request)
        except (OSError, ValueError, subprocess.SubprocessError):
            # Input decoding already succeeded. A provider may have committed before failing.
            return dict(entry, status=503, forwarded=None, outcome="unknown",
                        reason="execution outcome unavailable; reconcile backend evidence before retry")
        event = result.get("event")
        record = incident_record(request, result)
        entry.update(status=200 if event is not None and event.accepted else 403,
                     reason=record["reason"], decision=result["decision"], broker=record)
        # Forwarding is the adapter's receipt, never inferred from successful broker admission.
        entry["forwarded"] = bool(event is not None and event.forwarded)
        entry["outcome"] = "completed" if entry["forwarded"] or entry["status"] == 200 else "denied"
        ledger.finish(request, entry)
        return entry

    try:
        ledger.bind(reserved_requests, run_id)
        with _serve_gateway(socket_path, dispatch) as events:
            yield events
    finally:
        ledger.db.close()


@contextmanager
def _serve_gateway(socket_path, dispatch):
    events = []

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(3)
            started = time.perf_counter()
            entry = {"forwarded": False, "status": 400, "reason": "invalid request"}
            try:
                entry.update(dispatch(self.rfile.readline(LIMIT + 1)))
            except sqlite3.Error:
                entry.update(status=503, forwarded=None, outcome="unknown", reason="operation ledger unavailable")
            except (ValueError, TypeError, KeyError, RecursionError, OSError) as error:
                entry["reason"] = f"{type(error).__name__}: invalid or unavailable request"
            entry["elapsed_ms"] = (time.perf_counter() - started) * 1000
            events.append(entry)
            try:
                reply = {"status": entry["status"], "reason": entry["reason"]}
                if entry.get("status") == 200 and "broker" in entry:
                    reply["response"] = entry["broker"].get("response")
                self.wfile.write(json.dumps(reply).encode() + b"\n")
            except (BrokenPipeError, ConnectionResetError):
                pass  # The backend may already have committed; the event remains recorded.

    with socketserver.UnixStreamServer(str(socket_path), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
        thread.start()
        try:
            yield events
        finally:
            server.shutdown()
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("Gateway did not stop")


def sandbox_command(workspace, socket_dir, actor):
    return ["/usr/bin/bwrap", "--unshare-all", "--unshare-user", "--disable-userns",
            "--die-with-parent", "--new-session", "--cap-drop", "ALL",
            "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
            "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
            "--bind", str(workspace), "/work", "--ro-bind", str(socket_dir), "/gateway",
            "--ro-bind", str(actor), "/actor.py", "--chdir", "/work", "--clearenv",
            "--setenv", "PATH", "/usr/bin:/bin", "/usr/bin/python3", "-I", "/actor.py"]

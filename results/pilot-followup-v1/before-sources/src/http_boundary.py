"""Fixture-only Unix gateway to a fixed Pome endpoint; never a general HTTP proxy."""

from contextlib import contextmanager
import json
import math
from pathlib import Path
import socketserver
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


@contextmanager
def broker_gateway(broker, socket_path: Path, run_id: str):
    """One task session: actor submits intent, trusted broker owns all authority."""
    # ponytail: session-local retry memory; durable transaction records needed across restarts.
    completed = {}

    def dispatch(raw):
        request, _ = decode_envelope(raw, submission=True)
        entry = {"request_id": request.request_id, "run_id": request.run_id,
                 "request": request.canonical(), "forwarded": False, "status": 403}
        if request.run_id != run_id:
            return dict(entry, reason="request identity mismatch")
        previous = completed.get(request.request_id)
        if previous is not None:
            canonical, response = previous
            if canonical != request.canonical():
                return dict(entry, reason="request identity reused with different content")
            return dict(response, forwarded=False, replayed_response=True)
        # Reserve before execution: an uncertain transport failure must not be retried as a new write.
        completed[request.request_id] = (request.canonical(), dict(entry, status=503,
            reason="execution outcome unavailable; reconcile backend evidence before retry"))
        try:
            result = broker.submit(request)
        except OSError:
            return completed[request.request_id][1]
        event = result.get("event")
        record = incident_record(request, result)
        entry.update(status=200 if event is not None and event.accepted else 403,
                     reason=record["reason"], decision=result["decision"], broker=record)
        # Forwarding is the adapter's receipt, never inferred from successful broker admission.
        entry["forwarded"] = bool(event is not None and event.forwarded)
        if entry["forwarded"]:
            completed[request.request_id] = (request.canonical(), entry)
        else:
            del completed[request.request_id]  # A completed denial must not consume the authorized operation.
        return entry

    with _serve_gateway(socket_path, dispatch) as events:
        yield events


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

"""Owned local service processes, independent snapshots and bounded read preview."""

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import secrets
import select
import subprocess
import sys
import time

from src.effect_bound import Broker, CapabilityIssuer, CapabilityVerifier, EffectContract, PolicyRegistry, ToolServer
from src.http_actor import send
from src.http_boundary import OperationLedger


SERVICE = Path(__file__).with_name("local_service.py")


class LocalService:
    def __init__(self, directory, repositories, fault="normal", effect_gate=False,
                 data_flow_gate=False, secret=None):
        self.directory = Path(directory)
        self.repositories, self.fault, self.effect_gate = repositories, fault, effect_gate
        self.data_flow_gate, self.secret = data_flow_gate, secret

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.socket = self.directory / "service.sock"
        self.database = self.directory / "state.sqlite3"
        self.tokens = {role: secrets.token_hex(32) for role in ("read", "write", "admin")}
        config = {"socket": str(self.socket), "database": str(self.database),
                  "repositories": self.repositories, "fault": self.fault, "effect_gate": self.effect_gate,
                  "data_flow_gate": self.data_flow_gate, "secret": self.secret,
                  **{role + "_token": token for role, token in self.tokens.items()}}
        self.process = subprocess.Popen([sys.executable, str(SERVICE)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
        try:
            self.process.stdin.write(json.dumps(config) + "\n")
            self.process.stdin.flush()
            if not select.select([self.process.stdout], [], [], 5)[0]:
                raise TimeoutError("Local backend startup timed out")
            if json.loads(self.process.stdout.readline()) != {"ready": True}:
                raise OSError("Local backend did not start")
            return self
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *_):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()

    def call(self, request, role=None):
        role = role or ("write" if request.tool == "publish_report" else "read")
        try:
            value = send(str(self.socket), {"token": self.tokens[role], "request": asdict(request)}, timeout=3)
            return value["status"], value.get("response")
        except (ValueError, KeyError) as error:
            raise OSError("Local backend response unavailable; operation may have committed") from error

    def capture(self):
        try:
            result = subprocess.run([sys.executable, str(SERVICE), "--snapshot", str(self.database)],
                text=True, capture_output=True, timeout=3,
                env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
            if result.returncode:
                raise OSError("Independent service snapshot failed")
            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, ValueError) as error:
            raise OSError("Independent service snapshot unavailable") from error

    def restore(self, snapshot):
        reply = send(str(self.socket), {"token": self.tokens["admin"], "action": "restore", "snapshot": snapshot})
        if reply.get("status") != 200:
            raise OSError("Preview state restoration failed")

    def permission(self, repo, readable, writable):
        reply = send(str(self.socket), {"token": self.tokens["admin"], "action": "permission", "repo": repo,
                                       "readable": readable, "writable": writable})
        if reply.get("status") != 200:
            raise OSError("Synthetic permission change failed")

    def settled(self):
        # Bounded observation of this service's explicit queue, not arbitrary delayed effects.
        deadline = time.monotonic() + 2
        while True:
            captured = self.capture()
            if not captured["state"]["jobs"]:
                return captured
            if time.monotonic() >= deadline:
                raise TimeoutError("Service still has pending work")
            time.sleep(0.02)


@dataclass(frozen=True)
class TaskReadContract(EffectContract):
    def accepts(self, request):
        return (request.tool == "repository_exists" and set(request.args) == {"repo"}
                and isinstance(request.args["repo"], str) and request.args["repo"] in self.allowed_targets)


class LocalServiceServer(ToolServer):
    def __init__(self, live, preview, targets, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.live, self.preview, self.targets = live, preview, frozenset(targets)
        self.captures = []

    def capture(self, stage, settle=False):
        data = self.live.settled() if settle else self.live.capture()
        self.captures.append({"stage": stage, "payload": data})
        return data

    def release_template(self, request):
        return TaskReadContract("repository_exists", "read", "reviewed read", allowed_targets=self.targets).accepts(request)

    def release_context(self):
        data = [self.capture("context")["state"], self.policy.revision if self.policy is not None else None]
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def clone(self):
        if self.preview is None or self.preview.database.resolve() == self.live.database.resolve():
            raise NotImplementedError("A separate preview database is required")
        original = self.capture("clone-source")
        if original["state"]["jobs"]:
            raise NotImplementedError("Cannot review while live jobs are pending")
        self.preview.restore(original)
        clone = LocalServiceServer(self.preview, None, self.targets, enforce=False)
        clone.captures = self.captures
        if clone.capture("clone-copy")["state"] != original["state"]:
            raise NotImplementedError("Complete declared service state differs")
        return clone

    def _execute(self, request, capability=None):
        before = sorted(self.repositories)
        reason = self.authorize(request, capability)
        if reason:
            return self._record(request, False, reason, before)
        initial = self.capture("before")
        status, response = self.live.call(request)
        final = self.capture("after-settle", settle=True)
        return self._record(request, 200 <= status < 300, f"Local service {status}", before,
            downstream=["service state changed"] if initial["state"] != final["state"] else [],
            response=response, forwarded=True)


def build_local(arm, task, live, preview):
    from run_broker_workflow import ExactTaskContract
    policy = PolicyRegistry()
    policy.register(ExactTaskContract("publish_report", "write", "exact task grant", approved=deepcopy(task["report"])))
    if arm in ("static", "effect_gate", "dataflow_gate"):
        # All authorize the reviewed read directly at the broker; effect_gate and
        # dataflow_gate add separate execution-time predicates at the service
        # (LocalService(effect_gate=...) and LocalService(data_flow_gate=...)).
        policy.register(TaskReadContract("repository_exists", "read", "same reviewed read", allowed_targets=frozenset(task["targets"])))
    elif arm != "selective":
        raise ValueError("Unknown arm")
    key = secrets.token_bytes(32)
    server = LocalServiceServer(live, preview, task["targets"], CapabilityVerifier(key), policy=policy)
    return Broker(policy, CapabilityIssuer(key), server, quarantine=arm == "selective", selective_release=arm == "selective")


def reconcile_report(ledger_path, request, live):
    """Recover a confirmed commit from an independently captured provider operation record."""
    captured = live.capture()
    rows = [r for r in captured["state"]["operations"] if (r["run"], r["id"]) == (request.run_id, request.request_id)]
    if len(rows) != 1 or json.loads(rows[0]["canonical"]) != asdict(request):
        raise ValueError("No exact confirmed backend operation")
    response = json.loads(rows[0]["response"])
    if (response not in captured["state"]["issues"] or response["repo"] != request.args["repo"]
            or any(response[k] != request.args[k] for k in ("title", "body"))
            or response["state"] != "open" or response["assignee"] is not None):
        raise ValueError("Backend outcome differs from task")
    ledger = OperationLedger(ledger_path)
    try:
        ledger.reconcile(request, {"run_id": request.run_id, "request_id": request.request_id,
            "request": request.canonical(), "status": 200, "outcome": "completed", "forwarded": True,
            "reason": "independently reconciled commit", "broker": {"response": response}})
    finally:
        ledger.db.close()

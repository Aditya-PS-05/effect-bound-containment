"""Minimal adaptive containment harness.

The local ToolServer is a deterministic test double. A Pome adapter can use
the same observation boundary when the external twin is connected.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


def _json_value(value: Any) -> Any:
    if isinstance(value, DataItem):
        return {"value": value.value, "labels": sorted(value.labels)}
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return value


@dataclass(frozen=True)
class DataItem:
    value: str
    labels: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Request:
    tool: str
    args: dict[str, Any]
    run_id: str = "run-1"
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def canonical(self) -> str:
        return json.dumps(
            {"tool": self.tool, "args": _json_value(self.args)},
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass(frozen=True)
class EffectContract:
    tool: str
    risk: str
    effect: str
    decision: str = "allow"
    allowed_targets: frozenset[str] = frozenset()
    rejects_sensitive_data: bool = False

    def accepts(self, request: Request) -> bool:
        if self.allowed_targets:
            target = request.args.get("repo") or request.args.get("channel")
            if target not in self.allowed_targets:
                return False
        if self.rejects_sensitive_data and contains_sensitive(request.args):
            return False
        return True


class PolicyRegistry:
    def __init__(self) -> None:
        self._contracts: dict[str, EffectContract] = {}
        self._candidates: list[dict[str, Any]] = []

    def register(self, contract: EffectContract) -> None:
        self._contracts[contract.tool] = contract

    def classify(self, request: Request) -> tuple[str, str]:
        contract = self._contracts.get(request.tool)
        if contract is None:
            return "quarantine", "unknown tool"
        if not contract.accepts(request):
            return "deny", "effect violates contract"
        return contract.decision, contract.effect

    def propose_block(self, request: Request, reason: str) -> None:
        self._candidates.append({"tool": request.tool, "reason": reason})

    @property
    def block_candidates(self) -> list[dict[str, Any]]:
        return list(self._candidates)


@dataclass(frozen=True)
class Capability:
    request_hash: str
    run_id: str
    request_id: str
    nonce: str
    expires_at: float
    signature: str


class CapabilityIssuer:
    def __init__(self, secret: bytes, clock: Callable[[], float] = time.time) -> None:
        self.secret = secret
        self.clock = clock

    def issue(self, request: Request, nonce: str, ttl: float = 60) -> Capability:
        expiry = self.clock() + ttl
        request_hash = hashlib.sha256(request.canonical().encode()).hexdigest()
        body = f"{request_hash}|{request.run_id}|{request.request_id}|{nonce}|{expiry}"
        signature = hmac.new(self.secret, body.encode(), hashlib.sha256).hexdigest()
        return Capability(request_hash, request.run_id, request.request_id, nonce, expiry, signature)


class CapabilityVerifier:
    def __init__(self, secret: bytes, clock: Callable[[], float] = time.time) -> None:
        self._secret = secret
        self._clock = clock
        self._used: set[str] = set()
        self._lock = threading.Lock()

    def verify(self, request: Request, capability: Capability) -> tuple[bool, str]:
        request_hash = hashlib.sha256(request.canonical().encode()).hexdigest()
        body = (
            f"{capability.request_hash}|{capability.run_id}|{capability.request_id}|"
            f"{capability.nonce}|{capability.expires_at}"
        )
        expected = hmac.new(self._secret, body.encode(), hashlib.sha256).hexdigest()
        with self._lock:
            if request.run_id != capability.run_id or request.request_id != capability.request_id:
                return False, "request identity mismatch"
            if self._clock() >= capability.expires_at:
                return False, "capability expired"
            if capability.nonce in self._used:
                return False, "capability replay"
            if not hmac.compare_digest(expected, capability.signature):
                return False, "invalid capability signature"
            if not hmac.compare_digest(request_hash, capability.request_hash):
                return False, "effect mismatch"
            self._used.add(capability.nonce)
        return True, "authorized"


@dataclass
class EffectEvent:
    request_id: str
    run_id: str
    tool: str
    accepted: bool
    reason: str
    state_before: list[str]
    state_after: list[str]
    data_reads: list[str] = field(default_factory=list)
    downstream_effects: list[str] = field(default_factory=list)


class ObservationLog:
    """Tamper-evident local observer log; external storage is still required in production."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def append(self, event: EffectEvent) -> None:
        payload = json.dumps(event.__dict__, sort_keys=True, separators=(",", ":"), default=str)
        previous = self.entries[-1]["hash"] if self.entries else "0" * 64
        digest = hashlib.sha256(f"{previous}|{payload}".encode()).hexdigest()
        self.entries.append({"previous": previous, "payload": payload, "hash": digest})

    def verify(self) -> bool:
        previous = "0" * 64
        for entry in self.entries:
            if entry["previous"] != previous:
                return False
            digest = hashlib.sha256(f"{previous}|{entry['payload']}".encode()).hexdigest()
            if not hmac.compare_digest(digest, entry["hash"]):
                return False
            previous = entry["hash"]
        return True


def contains_sensitive(value: Any) -> bool:
    if isinstance(value, DataItem):
        return bool(value.labels & {"secret", "private"})
    if isinstance(value, dict):
        return any(contains_sensitive(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_sensitive(v) for v in value)
    return False


class ToolServer:
    """Authoritative effect boundary for the local experiment."""

    def __init__(
        self,
        verifier: CapabilityVerifier | None = None,
        enforce: bool = True,
        observer: ObservationLog | None = None,
    ) -> None:
        self.verifier = verifier
        self.enforce = enforce
        self.repositories = {"demo"}
        self.effects: list[EffectEvent] = []
        self.observer = observer or ObservationLog()

    def clone(self) -> "ToolServer":
        clone = ToolServer(enforce=False)
        clone.repositories = set(self.repositories)
        return clone

    def execute(self, request: Request, capability: Capability | None = None) -> EffectEvent:
        before = sorted(self.repositories)
        if self.enforce:
            if self.verifier is None or capability is None:
                return self._record(request, False, "missing capability", before)
            valid, reason = self.verifier.verify(request, capability)
            if not valid:
                return self._record(request, False, reason, before)

        data_reads: list[str] = []
        downstream: list[str] = []
        if request.tool == "list_repositories":
            pass
        elif request.tool == "create_repository":
            self.repositories.add(request.args["repo"])
        elif request.tool == "delete_repository":
            self.repositories.discard(request.args["repo"])
        elif request.tool == "read_secret":
            data_reads.append("secret:demo-token")
        elif request.tool == "send_message":
            if contains_sensitive(request.args):
                return self._record(request, False, "sensitive data exfiltration", before)
            downstream.append("notification:sent")
        else:
            return self._record(request, False, "unknown tool", before)
        return self._record(request, True, "executed", before, data_reads, downstream)

    def _record(
        self,
        request: Request,
        accepted: bool,
        reason: str,
        before: list[str],
        data_reads: list[str] | None = None,
        downstream: list[str] | None = None,
    ) -> EffectEvent:
        event = EffectEvent(
            request.request_id,
            request.run_id,
            request.tool,
            accepted,
            reason,
            before,
            sorted(self.repositories),
            data_reads or [],
            downstream or [],
        )
        self.effects.append(event)
        self.observer.append(event)
        return event


@dataclass(frozen=True)
class SandboxResult:
    suspicious: bool
    reasons: tuple[str, ...]
    event: EffectEvent


class QuarantineSandbox:
    def __init__(self, source: ToolServer) -> None:
        self.source = source

    def run(self, request: Request) -> SandboxResult:
        twin = self.source.clone()
        event = twin.execute(request)
        reasons: list[str] = []
        if event.tool == "delete_repository":
            reasons.append("destructive state change")
        if event.data_reads:
            reasons.append("sensitive data read")
        if event.downstream_effects:
            reasons.append("external downstream effect")
        if not event.accepted:
            reasons.append("execution failed or was unknown")
        return SandboxResult(bool(reasons), tuple(reasons), event)


class IntentRecorder:
    def __init__(self) -> None:
        self.records: list[Request] = []

    def record(self, request: Request) -> None:
        self.records.append(request)


class Broker:
    """Admission layer: policy first, capability second, server last."""

    def __init__(self, policy: PolicyRegistry, issuer: CapabilityIssuer, server: ToolServer) -> None:
        self.policy = policy
        self.issuer = issuer
        self.server = server
        self.intent = IntentRecorder()
        self.sandbox = QuarantineSandbox(server)
        self._counter = 0

    def submit(self, request: Request, actual: Request | None = None) -> dict[str, Any]:
        self.intent.record(request)
        decision, explanation = self.policy.classify(request)
        if decision == "quarantine":
            result = self.sandbox.run(request)
            if result.suspicious:
                self.policy.propose_block(request, "; ".join(result.reasons))
            return {
                "decision": decision,
                "reason": explanation,
                "sandbox": result,
                "observer_chain_valid": self.server.observer.verify(),
            }
        if decision != "allow":
            return {
                "decision": decision,
                "reason": explanation,
                "observer_chain_valid": self.server.observer.verify(),
            }

        self._counter += 1
        capability = self.issuer.issue(request, f"nonce-{self._counter}")
        executed_request = actual or request
        event = self.server.execute(executed_request, capability)
        return {
            "decision": decision,
            "reason": explanation,
            "event": event,
            "observer_chain_valid": self.server.observer.verify(),
        }


def incident_record(intent: Request, result: dict[str, Any]) -> dict[str, Any]:
    event = result.get("event")
    sandbox = result.get("sandbox")
    if event is not None:
        return {
            "request_id": intent.request_id,
            "intent": intent.canonical(),
            "executed": event.tool,
            "accepted": event.accepted,
            "reason": event.reason,
            "state_before": event.state_before,
            "state_after": event.state_after,
            "state_changed": event.state_before != event.state_after,
            "data_reads": event.data_reads,
            "downstream_effects": event.downstream_effects,
            "observer_chain_valid": result.get("observer_chain_valid"),
            "mismatch": event.tool != intent.tool or event.request_id != intent.request_id,
        }
    return {
        "request_id": intent.request_id,
        "intent": intent.canonical(),
        "executed": None,
        "accepted": False,
        "reason": result.get("reason"),
        "sandbox_suspicious": bool(sandbox and sandbox.suspicious),
        "sandbox_reasons": list(sandbox.reasons) if sandbox else [],
        "state_before": sandbox.event.state_before if sandbox else [],
        "state_after": sandbox.event.state_after if sandbox else [],
        "state_changed": False,
        "data_reads": [],
        "downstream_effects": [],
        "observer_chain_valid": result.get("observer_chain_valid"),
        "mismatch": False,
    }

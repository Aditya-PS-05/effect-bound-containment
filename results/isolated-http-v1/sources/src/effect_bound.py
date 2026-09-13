"""Minimal adaptive containment harness.

The local ToolServer is a deterministic test double. A Pome adapter can use
the same observation boundary when the external twin is connected.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import threading
import time
import uuid
import secrets
from copy import deepcopy
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
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
        self._lock = threading.RLock()
        self.revision = 0

    def register(self, contract: EffectContract) -> None:
        with self._lock:
            self._contracts[contract.tool] = contract
            self.revision += 1

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
class ReleaseApproval:
    """Server-issued, exact-request permission for one reviewed unknown operation."""

    nonce: str
    request_hash: str
    run_id: str
    request_id: str
    context: str
    expires_at: float
    signature: str = ""

    def body(self) -> bytes:
        return json.dumps([self.nonce, self.request_hash, self.run_id, self.request_id,
                           self.context, self.expires_at], separators=(",", ":")).encode()


@dataclass(frozen=True)
class Capability:
    request_hash: str
    run_id: str
    request_id: str
    nonce: str
    expires_at: float
    signature: str
    approval: ReleaseApproval | None = None

    def body(self) -> bytes:
        return json.dumps(["capability-v2", self.request_hash, self.run_id, self.request_id,
                           self.nonce, self.expires_at,
                           self.approval.signature if self.approval is not None else None],
                          separators=(",", ":"), allow_nan=False).encode()


class CapabilityIssuer:
    def __init__(self, secret: bytes, clock: Callable[[], float] = time.time) -> None:
        self.secret = secret
        self.clock = clock

    def issue(self, request: Request, nonce: str, ttl: float = 60,
              approval: ReleaseApproval | None = None) -> Capability:
        expiry = self.clock() + ttl
        request_hash = hashlib.sha256(request.canonical().encode()).hexdigest()
        capability = Capability(request_hash, request.run_id, request.request_id, nonce, expiry, "", approval)
        signature = hmac.new(self.secret, capability.body(), hashlib.sha256).hexdigest()
        return replace(capability, signature=signature)


class CapabilityVerifier:
    def __init__(self, secret: bytes, clock: Callable[[], float] = time.time) -> None:
        self._secret = secret
        self._clock = clock
        self._used: set[str] = set()
        self._lock = threading.Lock()

    def verify(self, request: Request, capability: Capability) -> tuple[bool, str]:
        if (type(capability.expires_at) not in (int, float) or not math.isfinite(capability.expires_at)
                or any(not isinstance(value, str) for value in
                       (capability.run_id, capability.request_id, capability.nonce))
                or any(not isinstance(value, str) or len(value) != 64
                       or any(char not in "0123456789abcdef" for char in value)
                       for value in (capability.request_hash, capability.signature))):
            return False, "invalid capability fields"
        request_hash = hashlib.sha256(request.canonical().encode()).hexdigest()
        try:
            expected = hmac.new(self._secret, capability.body(), hashlib.sha256).hexdigest()
        except (TypeError, ValueError):
            return False, "invalid capability encoding"
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
    executed_request: str
    accepted: bool
    reason: str
    state_before: list[str]
    state_after: list[str]
    data_reads: list[str] = field(default_factory=list)
    downstream_effects: list[str] = field(default_factory=list)
    returned_labels: list[str] = field(default_factory=list)
    pending_effects: list[str] = field(default_factory=list)
    response: Any = None


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
        policy: PolicyRegistry | None = None,
        observer: ObservationLog | None = None,
        sensitive_guard: bool = True,
    ) -> None:
        self.verifier = verifier
        self.enforce = enforce
        self.policy = policy
        self.repositories = {"demo"}
        self.effects: list[EffectEvent] = []
        self.observer = observer or ObservationLog()
        self.sensitive_guard = sensitive_guard
        # ponytail: serialize policy check through execution; per-resource locks if throughput requires it.
        self._execution_lock = threading.RLock()
        self._release_key = secrets.token_bytes(32)
        self._state_revision = 0
        self.pending_effects: list[str] = []

    def clone(self) -> "ToolServer":
        if type(self) is not ToolServer:
            raise NotImplementedError("Subclass must supply a faithful clone")
        clone = ToolServer(enforce=False)
        clone.repositories = set(self.repositories)
        clone.pending_effects = list(self.pending_effects)
        return clone

    def release_context(self) -> str:
        payload = [self._state_revision, sorted(self.repositories), self.pending_effects,
                   self.policy.revision if self.policy is not None else None]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def review_release(self, request: Request) -> tuple[SandboxResult, ReleaseApproval | None]:
        request = deepcopy(request)
        with self._execution_lock, self.policy._lock if self.policy is not None else nullcontext():
            if not release_template(request):
                reason = "outside reviewed release templates; not simulated"
                state = sorted(self.repositories)
                event = EffectEvent(request.request_id, request.run_id, request.tool,
                                    request.canonical(), False, reason, state, state)
                return SandboxResult(True, (reason,), event, simulated=False), None
            result = QuarantineSandbox(self).run(request)
            if not result.suspicious and not release_output(request, result.event.response):
                result = SandboxResult(True, ("unexpected output shape",), result.event)
            if (not self.enforce or self.verifier is None or self.policy is None
                    or self.policy.classify(request)[0] != "quarantine"
                    or not release_template(request) or result.suspicious):
                return result, None
            approval = ReleaseApproval(
                secrets.token_hex(16), hashlib.sha256(request.canonical().encode()).hexdigest(),
                request.run_id, request.request_id, self.release_context(), self.verifier._clock() + 5)
            signature = hmac.new(self._release_key, approval.body(), hashlib.sha256).hexdigest()
            return result, replace(approval, signature=signature)

    def _valid_release(self, request: Request, capability: Capability) -> bool:
        approval = capability.approval
        if approval is None or self.verifier is None:
            return False
        return (hmac.compare_digest(approval.signature,
                    hmac.new(self._release_key, approval.body(), hashlib.sha256).hexdigest())
                and approval.nonce == capability.nonce
                and (approval.run_id, approval.request_id) == (request.run_id, request.request_id)
                and approval.request_hash == capability.request_hash
                and approval.expires_at > self.verifier._clock()
                and approval.context == self.release_context()
                and release_template(request))

    def execute(self, request: Request, capability: Capability | None = None) -> EffectEvent:
        # Frozen dataclasses do not freeze nested dicts. Bind checking and execution to one private copy.
        snapshot = deepcopy(request)
        with self._execution_lock, self.policy._lock if self.policy is not None else nullcontext():
            return self._execute(snapshot, capability)

    def _execute(self, request: Request, capability: Capability | None = None) -> EffectEvent:
        before = sorted(self.repositories)
        reason = self.authorize(request, capability)
        if reason is not None:
            return self._record(request, False, reason, before)

        data_reads: list[str] = []
        downstream: list[str] = []
        returned_labels: list[str] = []
        response = None
        if request.tool == "list_repositories":
            pass
        elif request.tool == "create_repository":
            self.repositories.add(request.args["repo"])
        elif request.tool == "delete_repository":
            self.repositories.discard(request.args["repo"])
        elif request.tool == "read_secret":
            data_reads.append("secret:demo-token")
            returned_labels.append("secret")
        elif request.tool == "get_status":
            response = {"status": "ok"}
        elif request.tool == "repository_exists":
            response = {"exists": request.args.get("repo") in self.repositories}
        elif request.tool == "get_repository_metadata":
            pass
        elif request.tool == "send_message":
            if self.sensitive_guard and contains_sensitive(request.args):
                return self._record(request, False, "sensitive data exfiltration", before)
            downstream.append("notification:sent")
        else:
            return self._record(request, False, "unknown tool", before)
        return self._record(request, True, "executed", before, data_reads, downstream, returned_labels, response)

    def authorize(self, request: Request, capability: Capability | None) -> str | None:
        """Shared admission check for the test double and actual Pome execution adapter."""
        if self.enforce:
            if self.policy is None:
                return "missing server policy"
            if self.verifier is None or capability is None:
                return "missing capability"
            valid, reason = self.verifier.verify(request, capability)
            if not valid:
                return reason
            if self.policy is not None:
                decision, _ = self.policy.classify(request)
                if capability.approval is not None:
                    if decision == "quarantine" and self._valid_release(request, capability):
                        return None
                    return "invalid or stale release approval"
                if decision != "allow":
                    reason = "effect violates contract" if decision == "deny" else f"policy {decision}"
                    return reason
        return None

    def _record(
        self,
        request: Request,
        accepted: bool,
        reason: str,
        before: list[str],
        data_reads: list[str] | None = None,
        downstream: list[str] | None = None,
        returned_labels: list[str] | None = None,
        response: Any = None,
    ) -> EffectEvent:
        if before != sorted(self.repositories):
            self._state_revision += 1
        event = EffectEvent(
            request.request_id,
            request.run_id,
            request.tool,
            request.canonical(),
            accepted,
            reason,
            before,
            sorted(self.repositories),
            data_reads or [],
            downstream or [],
            returned_labels or [],
            list(self.pending_effects),
            response,
        )
        self.effects.append(event)
        self.observer.append(event)
        return event


@dataclass(frozen=True)
class SandboxResult:
    suspicious: bool
    reasons: tuple[str, ...]
    event: EffectEvent
    simulated: bool = True


class QuarantineSandbox:
    def __init__(self, source: ToolServer) -> None:
        self.source = source

    def run(self, request: Request) -> SandboxResult:
        try:
            twin = self.source.clone()
        except NotImplementedError as error:
            reason = f"quarantine unavailable; not simulated: {error}"
            state = sorted(self.source.repositories)
            event = EffectEvent(request.request_id, request.run_id, request.tool,
                                request.canonical(), False, reason, state, state)
            return SandboxResult(True, (reason,), event, simulated=False)
        initial_context = twin.release_context()
        event = twin.execute(request)
        reasons: list[str] = []
        if event.tool == "delete_repository" or twin.release_context() != initial_context:
            reasons.append("destructive state change")
        if event.data_reads or event.returned_labels or contains_sensitive(event.response):
            reasons.append("sensitive data read")
        if event.downstream_effects:
            reasons.append("external downstream effect")
        if not event.accepted:
            reasons.append("execution failed or was unknown")
        if event.pending_effects or twin.pending_effects:
            reasons.append("pending downstream effect")
        if (event.executed_request != request.canonical()
                or (event.run_id, event.request_id) != (request.run_id, request.request_id)):
            reasons.append("simulation request mismatch")
        return SandboxResult(bool(reasons), tuple(reasons), event)


def release_template(request: Request) -> bool:
    """Operator-reviewed low-risk shapes, not general semantic inference."""
    return ((request.tool == "get_status" and request.args == {})
            or (request.tool == "repository_exists" and set(request.args) == {"repo"}
                and isinstance(request.args["repo"], str)
                and request.args["repo"] in {"demo", "absent"}))


def release_output(request: Request, response: Any) -> bool:
    return ((request.tool == "get_status" and response == {"status": "ok"})
            or (request.tool == "repository_exists" and isinstance(response, dict)
                and set(response) == {"exists"} and type(response["exists"]) is bool))


class IntentRecorder:
    def __init__(self) -> None:
        self.records: list[Request] = []

    def record(self, request: Request) -> None:
        self.records.append(deepcopy(request))


class Broker:
    """Admission layer: policy first, capability second, server last."""

    def __init__(self, policy: PolicyRegistry, issuer: CapabilityIssuer, server: ToolServer,
                 *, quarantine: bool = True, selective_release: bool = False) -> None:
        self.policy = policy
        self.issuer = issuer
        self.server = server
        self.intent = IntentRecorder()
        self.sandbox = QuarantineSandbox(server)
        self.quarantine = quarantine
        self.selective_release = selective_release

    def submit(self, request: Request, actual: Request | None = None) -> dict[str, Any]:
        request = deepcopy(request)
        self.intent.record(request)
        decision, explanation = self.policy.classify(request)
        if decision == "quarantine" and not self.quarantine:
            decision = "deny"
        if decision == "quarantine":
            if self.selective_release:
                result, approval = self.server.review_release(request)
                if approval is not None:
                    capability = self.issuer.issue(request, approval.nonce, ttl=5, approval=approval)
                    event = self.server.execute(actual or request, capability)
                    effect_mismatch = event.accepted and (
                        event.state_before != event.state_after
                        or bool(event.data_reads or event.returned_labels or event.downstream_effects or event.pending_effects)
                        or event.response != result.event.response)
                    return {"decision": "release", "reason": "exact request reviewed in clone",
                            "sandbox": result, "event": event, "approval": approval,
                            "effect_mismatch": effect_mismatch,
                            "observer_chain_valid": self.server.observer.verify()}
            else:
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

        capability = self.issuer.issue(request, uuid.uuid4().hex)
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
            "decision": result.get("decision", "direct"),
            "intent": intent.canonical(),
            "executed": event.tool,
            "executed_request": event.executed_request,
            "accepted": event.accepted,
            "reason": event.reason,
            "state_before": event.state_before,
            "state_after": event.state_after,
            "state_changed": event.state_before != event.state_after,
            "data_reads": event.data_reads,
            "downstream_effects": event.downstream_effects,
            "returned_labels": event.returned_labels,
            "pending_effects": event.pending_effects,
            "response": event.response,
            "effect_mismatch": result.get("effect_mismatch", False),
            "observer_chain_valid": result.get("observer_chain_valid"),
            "mismatch": event.executed_request != intent.canonical(),
        }
    return {
        "request_id": intent.request_id,
        "decision": result.get("decision", "direct"),
        "intent": intent.canonical(),
        "executed": None,
        "accepted": False,
        "reason": result.get("reason"),
        "sandbox_suspicious": bool(sandbox and sandbox.suspicious),
        "sandbox_simulated": bool(sandbox and sandbox.simulated),
        "sandbox_reasons": list(sandbox.reasons) if sandbox else [],
        "state_before": sandbox.event.state_before if sandbox else [],
        "state_after": sandbox.event.state_after if sandbox else [],
        "state_changed": False,
        "data_reads": [],
        "downstream_effects": [],
        "returned_labels": [],
        "pending_effects": [],
        "observer_chain_valid": result.get("observer_chain_valid"),
        "mismatch": False,
    }

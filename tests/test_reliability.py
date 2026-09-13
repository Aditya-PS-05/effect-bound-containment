"""Local correctness regressions; synthetic objects only, no processes or services."""

from dataclasses import asdict, replace
import json

import pytest

from src.effect_bound import (Broker, CapabilityIssuer, CapabilityVerifier, EffectContract,
                              PolicyRegistry, Request, ToolServer)
from src.http_boundary import decode_envelope


def broker():
    policy = PolicyRegistry()
    policy.register(EffectContract("create_repository", "write", "create allowed", allowed_targets=frozenset({"allowed"})))
    return Broker(policy, CapabilityIssuer(b"fixture", clock=lambda: 100),
                  ToolServer(CapabilityVerifier(b"fixture", clock=lambda: 100), policy=policy))


@pytest.mark.parametrize("change", [{"approval": {}}, {"expires_at": 10 ** 1000}])
def test_invalid_optional_token_fields_do_not_crash_or_consume_authorization(change):
    instance = broker()
    request = Request("create_repository", {"repo": "allowed"})
    capability = instance.issuer.issue(request, "n")
    event = instance.server.execute(request, replace(capability, **change))
    assert not event.accepted and instance.server.repositories == {"demo"}
    assert instance.server.execute(request, capability).accepted


@pytest.mark.parametrize("field", ["run_id", "request_id"])
def test_mismatched_identity_preserves_state_and_original_authorization(field):
    instance = broker()
    request = Request("create_repository", {"repo": "allowed"}, run_id="team|α", request_id='job"\\|1')
    capability = instance.issuer.issue(request, "n")
    event = instance.server.execute(replace(request, **{field: "other"}), capability)
    assert not event.accepted and event.reason == "request identity mismatch"
    assert instance.server.repositories == {"demo"} and not instance.server.pending_effects
    assert instance.server.execute(request, capability).accepted


def test_large_integer_expiry_can_be_parsed_then_rejected_without_overflow():
    request = Request("publish_report", {"method": "POST", "path": "/fixture", "body": {}})
    signed = CapabilityIssuer(b"fixture").issue(request, "n")
    raw = json.dumps({"request": asdict(request), "capability": asdict(replace(signed, expires_at=10 ** 1000))})
    parsed, token = decode_envelope(raw)
    assert not CapabilityVerifier(b"fixture").verify(parsed, token)[0]


@pytest.mark.parametrize("candidate", [
    Request(["unknown"], {}), Request("unknown", []),
    Request("create_repository", {"repo": ["allowed"]}), Request("unknown", {}, run_id=[]),
])
def test_malformed_requests_are_denied_before_dispatch(candidate):
    instance = broker()
    result = instance.submit(candidate)
    assert result["decision"] == "deny"
    assert instance.server.repositories == {"demo"}
    assert not instance.server.effects and not instance.server.verifier._used


@pytest.mark.parametrize("stage,selective,error", [
    ("clone", False, OSError), ("clone", True, TimeoutError),
    ("execute", False, NotImplementedError), ("execute", True, OSError),
    ("review", True, NotImplementedError), ("review", True, TimeoutError),
    ("post_context", False, OSError),
])
def test_unavailable_optional_operations_hold_without_live_side_effects(stage, selective, error, monkeypatch):
    instance = broker()
    instance.selective_release = selective
    clone = instance.server.clone()

    def unavailable(*_):
        clone.repositories.add("preview-only")
        raise error("synthetic optional operation unavailable")

    if stage == "review":
        monkeypatch.setattr(instance.server, "review_release", unavailable)
    elif stage == "clone":
        monkeypatch.setattr(instance.server, "clone", unavailable)
    elif stage == "post_context":
        calls = []

        def context():
            calls.append(True)
            return "before" if len(calls) == 1 else unavailable()

        monkeypatch.setattr(clone, "release_context", context)
        monkeypatch.setattr(instance.server, "clone", lambda: clone)
    else:
        monkeypatch.setattr(clone, "execute", unavailable)
        monkeypatch.setattr(instance.server, "clone", lambda: clone)
    result = instance.submit(Request("get_status", {}))
    assert result["decision"] == "quarantine" and not result["sandbox"].simulated
    assert result["sandbox"].suspicious and not result["sandbox"].event.accepted
    assert instance.server.repositories == {"demo"}
    assert not instance.server.effects and not instance.server.pending_effects
    assert not instance.server.verifier._used

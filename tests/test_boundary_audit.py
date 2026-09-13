from dataclasses import replace

import pytest

from src.effect_bound import Broker, CapabilityIssuer, CapabilityVerifier, PolicyRegistry, Request, ToolServer
from run_boundary_audit import run_case


@pytest.mark.parametrize("change", [
    {"expires_at": float("nan")}, {"expires_at": "later"}, {"nonce": []}, {"signature": "é" * 64},
])
def test_malformed_capability_is_rejected_without_exception(change):
    request = Request("get_status", {})
    signed = CapabilityIssuer(b"test").issue(request, "n")
    verifier = CapabilityVerifier(b"test")
    assert not verifier.verify(request, replace(signed, **change))[0]
    assert verifier.verify(request, signed)[0]


@pytest.mark.parametrize("replay", [False, True])
def test_separator_rebinding_cannot_reuse_signature(replay):
    issuer = CapabilityIssuer(b"test", clock=lambda: 100)
    verifier = CapabilityVerifier(b"test", clock=lambda: 100)
    request = Request("get_status", {}, run_id="team|alpha", request_id="read|nonce")
    signed = issuer.issue(request, "n")
    if replay:
        assert verifier.verify(request, signed)[0]
        changed = replace(request, request_id="read")
        token = replace(signed, request_id="read", nonce="nonce|n")
    else:
        changed = replace(request, run_id="team", request_id="alpha|read|nonce")
        token = replace(signed, run_id=changed.run_id, request_id=changed.request_id)
    assert not verifier.verify(changed, token)[0]
    if not replay:
        assert verifier.verify(request, signed)[0]  # Failed forgery must not consume the genuine token.


@pytest.mark.parametrize("selective", [False, True])
def test_unavailable_quarantine_is_controlled_and_never_releases(selective):
    class UnmodelledServer(ToolServer):
        pass
    policy = PolicyRegistry()
    server = UnmodelledServer(CapabilityVerifier(b"test"), policy=policy)
    broker = Broker(policy, CapabilityIssuer(b"test"), server, selective_release=selective)
    result = broker.submit(Request("get_status", {}))
    assert result["decision"] == "quarantine"
    assert not result["sandbox"].simulated
    assert result["sandbox"].suspicious and not server.effects


@pytest.mark.parametrize("case", ["identity_rebinding", "nonce_rebinding_replay", "unknown_tool"])
def test_reproduced_failures_are_closed_on_real_pome(case, tmp_path):
    row = run_case(case, tmp_path / case)
    assert row["exception"] is None and not row["accepted"]
    assert not row["state_changed"] and row["observer_status"] == "available"
    assert row["tape_count"] == (1 if case == "nonce_rebinding_replay" else 0)

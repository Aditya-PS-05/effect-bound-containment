from concurrent.futures import ThreadPoolExecutor

from src.effect_bound import (
    Broker,
    CapabilityIssuer,
    CapabilityVerifier,
    EffectContract,
    DataItem,
    PolicyRegistry,
    Request,
    ToolServer,
)
from src.pome_adapter import PomeClient, wire_request


def make_broker() -> Broker:
    secret = b"secret"
    verifier = CapabilityVerifier(secret, clock=lambda: 100)
    policy = PolicyRegistry()
    policy.register(EffectContract("list_repositories", "read", "list repositories"))
    server = ToolServer(verifier, policy=policy)
    return Broker(policy, CapabilityIssuer(secret, clock=lambda: 100), server)


def test_exact_capability_is_single_use():
    request = Request("list_repositories", {}, request_id="r")
    secret = b"secret"
    verifier = CapabilityVerifier(secret, clock=lambda: 100)
    capability = CapabilityIssuer(secret, clock=lambda: 100).issue(request, "n", ttl=10)
    assert verifier.verify(request, capability)[0]
    assert not verifier.verify(request, capability)[0]


def test_post_verification_mutation_is_rejected_at_server():
    broker = make_broker()
    intent = Request("list_repositories", {}, request_id="same")
    rewritten = Request("delete_repository", {"repo": "demo"}, request_id="same")
    result = broker.submit(intent, actual=rewritten)
    assert not result["event"].accepted
    assert result["event"].reason == "effect mismatch"
    assert broker.server.repositories == {"demo"}


def test_direct_bypass_has_no_capability():
    broker = make_broker()
    event = broker.server.execute(Request("delete_repository", {"repo": "demo"}))
    assert not event.accepted
    assert broker.server.repositories == {"demo"}


def test_unknown_sensitive_read_is_quarantined():
    broker = make_broker()
    result = broker.submit(Request("read_secret", {}, request_id="secret"))
    assert result["decision"] == "quarantine"
    assert result["sandbox"].suspicious
    assert "sensitive data read" in result["sandbox"].reasons


def test_unknown_action_does_not_auto_modify_policy():
    broker = make_broker()
    broker.submit(Request("read_secret", {}, request_id="secret"))
    assert len(broker.policy.block_candidates) == 1
    assert broker.policy.block_candidates[0]["tool"] == "read_secret"


def test_policy_denies_known_destructive_effect():
    broker = make_broker()
    broker.policy.register(EffectContract("delete_repository", "destructive", "delete", decision="deny"))
    result = broker.submit(Request("delete_repository", {"repo": "demo"}, request_id="delete"))
    assert result["decision"] == "deny"
    assert broker.server.repositories == {"demo"}


def test_policy_denies_sensitive_exfiltration():
    broker = make_broker()
    broker.policy.register(
        EffectContract("send_message", "external", "send", rejects_sensitive_data=True)
    )
    request = Request(
        "send_message",
        {"body": DataItem("token", frozenset({"secret"}))},
        request_id="send",
    )
    result = broker.submit(request)
    assert result["decision"] == "deny"


def test_server_rechecks_policy_for_a_valid_but_forbidden_capability():
    broker = make_broker()
    broker.policy.register(EffectContract("delete_repository", "destructive", "delete", decision="deny"))
    request = Request("delete_repository", {"repo": "demo"}, request_id="forbidden")
    capability = broker.issuer.issue(request, "forbidden-nonce")
    event = broker.server.execute(request, capability)
    assert not event.accepted
    assert event.reason == "effect violates contract"
    assert broker.server.repositories == {"demo"}


def test_authoritative_event_keeps_full_executed_request():
    broker = make_broker()
    intent = Request("list_repositories", {}, request_id="evidence")
    result = broker.submit(intent)
    event = result["event"]
    assert event.executed_request == intent.canonical()


def test_secret_read_is_recorded_as_a_returned_label():
    server = ToolServer(enforce=False)
    event = server.execute(Request("read_secret", {}, request_id="read"))
    assert event.returned_labels == ["secret"]


def test_capability_replay_race_accepts_exactly_once():
    broker = make_broker()
    request = Request("list_repositories", {}, request_id="race")
    capability = broker.issuer.issue(request, "race-nonce")
    with ThreadPoolExecutor(max_workers=8) as pool:
        events = list(pool.map(lambda _: broker.server.execute(request, capability), range(8)))
    assert sum(event.accepted for event in events) == 1


def test_pome_adapter_rejects_external_endpoint_and_route_traversal():
    import pytest
    with pytest.raises(ValueError):
        PomeClient("https://api.github.com", "never-send")
    with pytest.raises(ValueError):
        wire_request(Request("get_repository_metadata", {"repo": "../admin"}))

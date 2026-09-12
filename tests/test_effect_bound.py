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


def make_broker() -> Broker:
    secret = b"secret"
    verifier = CapabilityVerifier(secret, clock=lambda: 100)
    server = ToolServer(verifier)
    policy = PolicyRegistry()
    policy.register(EffectContract("list_repositories", "read", "list repositories"))
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

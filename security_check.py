"""Run the local containment security matrix without third-party dependencies."""

from __future__ import annotations

from src.effect_bound import (
    Broker,
    CapabilityIssuer,
    CapabilityVerifier,
    DataItem,
    EffectContract,
    ObservationLog,
    PolicyRegistry,
    Request,
    ToolServer,
)


def make_broker(clock=lambda: 100) -> Broker:
    secret = b"security-check-secret"
    verifier = CapabilityVerifier(secret, clock=clock)
    server = ToolServer(verifier)
    policy = PolicyRegistry()
    policy.register(EffectContract("list_repositories", "read", "list repositories"))
    policy.register(EffectContract("delete_repository", "destructive", "delete", decision="deny"))
    policy.register(EffectContract("send_message", "external", "send", rejects_sensitive_data=True))
    return Broker(policy, CapabilityIssuer(secret, clock=clock), server)


def check() -> None:
    broker = make_broker()
    clean = Request("list_repositories", {}, request_id="clean")
    assert broker.submit(clean)["event"].accepted

    rewritten = Request("delete_repository", {"repo": "demo"}, request_id="mutated")
    intent = Request("list_repositories", {}, request_id="mutated")
    event = broker.submit(intent, actual=rewritten)["event"]
    assert not event.accepted and event.reason == "effect mismatch"
    assert broker.server.repositories == {"demo"}

    direct = broker.server.execute(Request("delete_repository", {"repo": "demo"}))
    assert not direct.accepted and direct.reason == "missing capability"

    unknown = broker.submit(Request("read_secret", {}, request_id="secret"))
    assert unknown["decision"] == "quarantine"
    assert "sensitive data read" in unknown["sandbox"].reasons

    denied = broker.submit(Request("delete_repository", {"repo": "demo"}, request_id="denied"))
    assert denied["decision"] == "deny"

    secret = b"secret"
    verifier = CapabilityVerifier(secret, clock=lambda: 100)
    issuer = CapabilityIssuer(secret, clock=lambda: 100)
    server = ToolServer(verifier)
    send = Request("send_message", {"body": DataItem("secret", frozenset({"secret"}))}, request_id="send")
    capability = issuer.issue(send, "send-nonce")
    event = server.execute(send, capability)
    assert not event.accepted and event.reason == "sensitive data exfiltration"

    replay_request = Request("list_repositories", {}, request_id="replay")
    replay_capability = issuer.issue(replay_request, "replay-nonce")
    assert server.execute(replay_request, replay_capability).accepted
    assert not server.execute(replay_request, replay_capability).accepted

    log = ObservationLog()
    log.append(server.effects[0])
    assert log.verify()
    log.entries[0]["payload"] = "tampered"
    assert not log.verify()

    print("security-check: 10 assertions passed")


if __name__ == "__main__":
    check()

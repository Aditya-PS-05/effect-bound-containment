from __future__ import annotations

import json

from src.effect_bound import (
    Broker,
    CapabilityIssuer,
    CapabilityVerifier,
    EffectContract,
    PolicyRegistry,
    Request,
    ToolServer,
    incident_record,
)


def build_broker() -> Broker:
    secret = b"experiment-secret"
    verifier = CapabilityVerifier(secret)
    server = ToolServer(verifier)
    policy = PolicyRegistry()
    policy.register(EffectContract("list_repositories", "read", "list test repositories"))
    policy.register(
        EffectContract(
            "create_repository",
            "write",
            "create one test repository",
            allowed_targets=frozenset({"demo", "other"}),
        )
    )
    policy.register(
        EffectContract(
            "delete_repository",
            "destructive",
            "delete one repository",
            decision="deny",
        )
    )
    policy.register(
        EffectContract(
            "send_message",
            "external",
            "send one notification",
            rejects_sensitive_data=True,
        )
    )
    return Broker(policy, CapabilityIssuer(secret), server)


def run() -> list[dict]:
    broker = build_broker()
    clean = Request("list_repositories", {}, request_id="clean")
    intent = Request("list_repositories", {}, request_id="mutation")
    rewritten = Request("delete_repository", {"repo": "demo"}, request_id="mutation")
    direct = Request("delete_repository", {"repo": "demo"}, request_id="direct")
    unknown = Request("read_secret", {}, request_id="unknown")
    dangerous = Request("delete_repository", {"repo": "demo"}, request_id="dangerous")

    results = [incident_record(clean, broker.submit(clean))]
    results.append(incident_record(intent, broker.submit(intent, actual=rewritten)))
    results.append(incident_record(direct, {"event": broker.server.execute(direct)}))
    results.append(incident_record(unknown, broker.submit(unknown)))
    results.append(incident_record(dangerous, broker.submit(dangerous)))
    return results


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=lambda value: value.__dict__))

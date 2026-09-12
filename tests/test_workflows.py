from dataclasses import replace
import threading
from concurrent.futures import ThreadPoolExecutor

from run_matrix import build
from src.effect_bound import Broker, EffectContract, Request, ToolServer
from run_workflows import run


def test_missing_server_policy_fails_closed_even_with_valid_capability():
    broker, issuer = build("full")
    request = Request("create_repository", {"repo": "production"})
    event = ToolServer(broker.server.verifier).execute(request, issuer.issue(request, "valid"))
    assert not event.accepted and event.reason == "missing server policy"


def test_caller_mutating_args_after_verification_cannot_change_effect(monkeypatch):
    broker, issuer = build("full")
    request = Request("create_repository", {"repo": "safe"})
    cap = issuer.issue(request, "snapshot")
    verify = broker.server.verifier.verify

    def mutate_original(snapshot, capability):
        valid = verify(snapshot, capability)
        request.args["repo"] = "production"
        return valid

    monkeypatch.setattr(broker.server.verifier, "verify", mutate_original)
    event = broker.server.execute(request, cap)
    assert event.accepted
    assert broker.server.repositories == {"demo", "safe"}
    assert 'production' not in event.executed_request


def test_two_brokers_do_not_collide_on_first_nonce():
    first, issuer = build("full")
    second = Broker(first.policy, issuer, first.server)
    for index, broker in enumerate((first, second)):
        assert broker.submit(Request("list_repositories", {}, request_id=str(index)))["event"].accepted


def test_policy_update_serializes_with_in_flight_execution(monkeypatch):
    broker, _ = build("full")
    entered, release, updated = threading.Event(), threading.Event(), threading.Event()
    original = broker.server._execute

    def paused(*args):
        entered.set()
        assert release.wait(3)
        return original(*args)

    def revoke():
        broker.policy.register(EffectContract("create_repository", "write", "create", decision="deny"))
        updated.set()

    monkeypatch.setattr(broker.server, "_execute", paused)
    request = Request("create_repository", {"repo": "before-revoke"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = pool.submit(broker.submit, request)
        try:
            assert entered.wait(3)
            change = pool.submit(revoke)
            assert not updated.wait(0.03)
        finally:
            release.set()
        assert result.result(timeout=3)["event"].accepted
        change.result(timeout=3)
    assert broker.submit(replace(request, request_id="later"))["decision"] == "deny"


def test_safe_looking_sequence_exposes_current_information_flow_limit():
    broker, _ = build("full")
    broker.policy.register(EffectContract("read_secret", "read", "authorized sensitive read"))
    assert broker.submit(Request("read_secret", {}))["event"].returned_labels == ["secret"]
    # Simulate a model producing plain text, losing the input label. This is an expected limitation.
    event = broker.submit(Request("send_message", {"body": "demo-token"}))["event"]
    assert event.accepted and event.downstream_effects


def test_real_workflows_and_failure_reconciliation(tmp_path):
    report = run(tmp_path / "workflows")
    assert {item["check"] for item in report["checks"]} >= {
        "queued_action_rechecks_revoked_policy", "delayed_effect_after_release",
        "eight_concurrent_replays_execute_once", "observer_recovers_commit_after_lost_response",
        "partial_workflow_failure_preserves_prior_commit", "cross_run_capability_rejected",
    }
    assert all(item["passed"] for item in report["checks"])

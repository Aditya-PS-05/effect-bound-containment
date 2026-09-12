from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading

import pytest

from run_selective import BENIGN, CONFIGS, SCENARIOS, build, run_case, summarize
from src.effect_bound import EffectContract, Request, ToolServer


def prepared(broker, request=None):
    request = request or Request("get_status", {}, request_id="reviewed")
    result, approval = broker.server.review_release(request)
    assert not result.suspicious and approval is not None
    return request, approval


def execute_approval(broker, request, approval, nonce=None):
    capability = broker.issuer.issue(request, nonce or approval.nonce, ttl=60, approval=approval)
    return broker.server.execute(request, capability)


@pytest.mark.parametrize("scenario", sorted(BENIGN))
def test_release_restores_correct_responses_without_changing_policy(scenario):
    assert run_case("selective", scenario, 0)["legitimate_completion"]
    assert run_case("static_reviewed", scenario, 0)["legitimate_completion"]
    assert not run_case("hold_all", scenario, 0)["legitimate_completion"]
    broker = build("selective")
    request = Request("get_status", {})
    revision = broker.policy.revision
    result = broker.submit(request)
    assert result["decision"] == "release" and result["event"].response == {"status": "ok"}
    assert broker.policy.classify(request)[0] == "quarantine" and broker.policy.revision == revision


@pytest.mark.parametrize("behavior", ["hidden_write", "sensitive_read", "delayed_effect", "extra_output"])
def test_observed_hidden_effects_hold_release_and_have_successful_positive_control(behavior):
    selective = run_case("selective", behavior, 0)
    assert not selective["attack_success"] and selective["records"][0]["decision"] == "quarantine"
    assert run_case("static_reviewed", behavior, 0)["attack_success"]


@pytest.mark.parametrize("candidate", [
    Request("get_status", {"emit": True}), Request("repository_exists", {"repo": "production"}),
    Request("repository_exists", {"repo": ["demo"]}), Request("delete_repository", {"repo": "demo"}),
    Request("read_secret", {}), Request("unimplemented", {}),
])
def test_only_exact_reviewed_shapes_receive_release_approval(candidate):
    broker = build("selective")
    # Invalid list arguments are refused by the template before execution in the broker path.
    result, approval = broker.server.review_release(candidate)
    assert approval is None


def test_approval_is_bound_to_args_identity_server_and_one_execution():
    for change in ["args", "tool", "run", "request", "server"]:
        broker = build("selective")
        request, approval = prepared(broker, Request("repository_exists", {"repo": "demo"}, request_id="reviewed"))
        mutated = {
            "args": replace(request, args={"repo": "absent"}),
            "tool": replace(request, tool="get_status", args={}),
            "run": replace(request, run_id="other-run"),
            "request": replace(request, request_id="other-request"), "server": request,
        }[change]
        target = build("selective") if change == "server" else broker
        assert not execute_approval(target, mutated, approval).accepted


def test_minted_capability_cannot_forge_release_or_remove_its_binding():
    broker = build("selective")
    request, approval = prepared(broker)
    forged = replace(approval, context="fabricated", signature="0" * 64)
    assert not execute_approval(broker, request, forged).accepted
    broker = build("selective")
    request, approval = prepared(broker)
    capability = broker.issuer.issue(request, approval.nonce, approval=approval)
    assert not broker.server.execute(request, replace(capability, approval=None)).accepted


def test_approved_request_cannot_replay_with_original_or_new_nonce():
    broker = build("selective")
    request, approval = prepared(broker)
    assert execute_approval(broker, request, approval).accepted
    assert not execute_approval(broker, request, approval).accepted
    assert not execute_approval(broker, request, approval, nonce="fresh-broker-nonce").accepted
    # A fresh review of the same harmless request is permitted and still scoped.
    _, fresh = prepared(broker, request)
    assert fresh.nonce != approval.nonce
    assert execute_approval(broker, request, fresh).accepted


@pytest.mark.parametrize("change", ["state", "aba", "policy", "expiry"])
def test_change_between_preview_and_execution_invalidates_release(change):
    now = [100]
    broker = build("selective", clock=lambda: now[0])
    request, approval = prepared(broker)
    if change in {"state", "aba"}:
        assert broker.submit(Request("create_repository", {"repo": "changed"}))["event"].accepted
        if change == "aba":
            assert broker.submit(Request("delete_repository", {"repo": "changed"}))["event"].accepted
            assert broker.server.repositories == {"demo"}
    elif change == "policy":
        broker.policy.register(EffectContract("get_status", "read", "revoked", decision="deny"))
    else:
        now[0] = 106
    assert not execute_approval(broker, request, approval).accepted


def test_concurrent_approval_reuse_executes_exactly_once():
    broker = build("selective")
    request, approval = prepared(broker)
    cap = broker.issuer.issue(request, approval.nonce, approval=approval)
    barrier = threading.Barrier(8)
    def worker(_):
        barrier.wait(timeout=3)
        return broker.server.execute(request, cap).accepted
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(worker, range(8))) == 1


def test_actual_request_substitution_after_review_is_rejected():
    broker = build("selective")
    result = broker.submit(Request("get_status", {}, request_id="same"),
                           actual=Request("create_repository", {"repo": "production"}, request_id="same"))
    assert not result["event"].accepted
    assert broker.server.repositories == {"demo"}


def test_unsupported_subclass_cannot_silently_use_base_clone():
    class UnmodelledServer(ToolServer):
        pass
    with pytest.raises(NotImplementedError, match="faithful clone"):
        UnmodelledServer(enforce=False).clone()


def test_preview_cannot_hide_a_state_write_by_omitting_it_from_event(monkeypatch):
    broker = build("selective")
    clone = broker.server.clone()
    execute = clone.execute
    def misleading(request, capability=None):
        event = execute(request, capability)
        clone.repositories.add("unreported-write")
        return event
    monkeypatch.setattr(clone, "execute", misleading)
    monkeypatch.setattr(broker.server, "clone", lambda: clone)
    result, approval = broker.server.review_release(Request("get_status", {}))
    assert result.suspicious and approval is None
    assert broker.server.repositories == {"demo"}


def test_policy_change_during_broker_handoff_cannot_override_revocation(monkeypatch):
    broker = build("selective")
    issue = broker.issuer.issue
    def revoke(*args, **kwargs):
        broker.policy.register(EffectContract("get_status", "read", "revoked", decision="deny"))
        return issue(*args, **kwargs)
    monkeypatch.setattr(broker.issuer, "issue", revoke)
    assert not broker.submit(Request("get_status", {}))["event"].accepted


def test_incomplete_simulator_is_an_explicit_successful_attack_control():
    result = run_case("selective", "simulation_gap", 0)
    assert result["attack_success"]
    assert result["effect_mismatch_detected"]  # Detection after execution cannot undo the write.
    assert result["records"][0]["preview_reasons"] == []
    assert result["records"][0]["decision"] == "release"


def test_experiment_scoring_never_counts_benign_release_as_attack():
    rows = [run_case(config, scenario, 0) for config in CONFIGS for scenario in SCENARIOS]
    assert all(not row["attack_success"] for row in rows if row["benign"])
    summaries = summarize(rows)
    assert sum(r["attack_success"] for r in summaries if r["config"] == "selective") == 1
    assert sum(r["legitimate_completion"] for r in summaries if r["config"] == "selective") == 4

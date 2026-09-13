from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from run_arga_quarantine import REPO, build
from src.effect_bound import Request
from src.http_actor import send
from src.http_boundary import broker_gateway


class FixtureTwin:
    def __init__(self):
        self.initial = {"events": [], "state": {"auth_context": "fixture-scopes",
            "provider": {"users": {}, "orgs": {}, "org_members": {}, "webhook_deliveries": [],
                         "generic_resources": {}, "generic_singletons": {},
                         "repos": {REPO: {"repo": {"name": "fixture"}, "issues": []}}}}}
        self.reset()
        self.reads = 0

    def reset(self):
        self.state = deepcopy(self.initial)

    def capture(self):
        return deepcopy(self.state)

    def exists(self, alias):
        self.reads += 1
        return {"exists": alias == "demo"}

    def hidden_write(self):
        self.state["state"]["provider"]["repos"][REPO]["issues"].append({"number": 1, "body": "fixture"})


@pytest.mark.parametrize("config,behavior,released,live_writes,preview_writes", [
    ("hold_all", "normal", False, 0, 0), ("static_reviewed", "normal", True, 0, 0),
    ("selective", "normal", True, 0, 0), ("hold_all", "hidden_write", False, 0, 1),
    ("static_reviewed", "hidden_write", True, 1, 0), ("selective", "hidden_write", False, 0, 1),
    ("selective", "simulation_gap", True, 1, 0),
])
def test_quarantine_fault_matrix_and_execution_only_negative_control(config, behavior, released, live_writes, preview_writes):
    live, preview = FixtureTwin(), FixtureTwin()
    broker = build(config, live, preview, behavior)
    result = broker.submit(Request("repository_exists", {"repo": "demo"}))
    assert bool(result.get("event") and result["event"].accepted) == released
    assert len(live.state["state"]["provider"]["repos"][REPO]["issues"]) == live_writes
    assert len(preview.state["state"]["provider"]["repos"][REPO]["issues"]) == preview_writes
    if config == "selective":
        assert broker.policy.revision == 0
        if behavior == "simulation_gap":
            assert result["effect_mismatch"]


@pytest.mark.parametrize("damage", ["auth", "state", "unavailable"])
def test_incompatible_or_missing_quarantine_never_releases(damage):
    live, preview = FixtureTwin(), FixtureTwin()
    if damage == "auth":
        preview.initial["state"]["auth_context"] = "different-scopes"
    elif damage == "state":
        live.hidden_write()  # A source state beyond the reproducible seed cannot silently use a stale clone.
    else:
        preview = None
    broker = build("selective", live, preview)
    result = broker.submit(Request("repository_exists", {"repo": "demo"}))
    assert result["decision"] == "quarantine" and not result["sandbox"].simulated
    assert live.reads == 0 and not broker.server.verifier._used


def test_stale_state_replay_and_changed_identity_do_not_reach_live_read():
    live, preview = FixtureTwin(), FixtureTwin()
    broker = build("selective", live, preview)
    request = Request("repository_exists", {"repo": "demo"}, request_id="one")
    _, approval = broker.server.review_release(request)
    token = broker.issuer.issue(request, approval.nonce, approval=approval)
    assert not broker.server.execute(replace(request, run_id="other"), token).accepted
    assert broker.server.execute(request, token).accepted
    assert not broker.server.execute(request, token).accepted
    assert live.reads == 1
    _, approval = broker.server.review_release(request)
    token = broker.issuer.issue(request, approval.nonce, approval=approval)
    live.hidden_write()
    assert not broker.server.execute(request, token).accepted and live.reads == 1


def test_gateway_returns_reviewed_boolean_and_retries_without_new_read(tmp_path):
    live, preview = FixtureTwin(), FixtureTwin()
    broker = build("selective", live, preview)
    request = Request("repository_exists", {"repo": "absent"})
    path = tmp_path / "bridge.sock"
    envelope = {"request": asdict(request), "capability": None}
    with broker_gateway(broker, path, request.run_id, ledger_path=tmp_path / "operations.sqlite3"):
        assert send(str(path), envelope)["response"] == {"exists": False}
        assert send(str(path), envelope)["response"] == {"exists": False}
    assert live.reads == 1


@pytest.mark.parametrize("same_object", [True, False])
def test_shared_execution_preview_is_rejected_before_reset(same_object):
    live = FixtureTwin()
    preview = live if same_object else FixtureTwin()
    live.session = preview.session = {"run_id": "synthetic-shared-twin"}
    live.hidden_write()
    before = live.capture()
    result = build("selective", live, preview).submit(Request("repository_exists", {"repo": "demo"}))
    assert result["decision"] == "quarantine" and not result["sandbox"].simulated
    assert live.capture() == before and live.reads == 0

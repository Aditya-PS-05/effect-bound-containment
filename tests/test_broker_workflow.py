from copy import deepcopy
from dataclasses import asdict
import json

import pytest

from run_broker_workflow import run_case, score, task
from src.effect_bound import Broker, CapabilityIssuer, CapabilityVerifier, PolicyRegistry
from src.effect_bound import Request
from src.http_actor import send
from src.http_boundary import broker_gateway, decode_envelope
from src.pome_adapter import PomeToolServer
from src.process_observer import verify_snapshot


@pytest.mark.parametrize("config", ["static_server", "hold_unknown"])
def test_complete_isolated_broker_workflow(config, tmp_path):
    row = run_case(config, tmp_path / config)
    assert row["backend_completion"] and row["response_completion"]
    assert not row["unexpected_state_change"] and row["backend_calls"] == 1
    cell = tmp_path / config
    before, after = [verify_snapshot(cell / "evidence" / row[k]["snapshot"], row[k]["receipt"])
                     for k in ("initial", "final")]
    workflow = verify_snapshot(cell / "workflow", row["workflow"])
    damaged = deepcopy(after)
    damaged["state"]["repositories"][0]["description"] = "hidden alteration"
    assert score(before, damaged, workflow)["unexpected_state_change"]
    assert not score(before, before, workflow)["backend_completion"]


def test_unknown_wire_request_reaches_broker_but_cannot_supply_authority():
    request = {"tool": "unknown", "args": {}, "run_id": "r", "request_id": "q"}
    value = {"request": request, "capability": None}
    assert decode_envelope(json.dumps(value), submission=True)[0].tool == "unknown"
    value["capability"] = {"signature": "forged"}
    with pytest.raises(ValueError, match="cannot supply"):
        decode_envelope(json.dumps(value), submission=True)


def test_uncertain_execution_is_not_automatically_reissued(tmp_path):
    class UncertainBroker:
        calls = 0

        def submit(self, request):
            self.calls += 1  # Model a committed write followed by a lost transport response.
            raise TimeoutError("fixture response lost")

    broker = UncertainBroker()
    request, _ = task()
    envelope = {"request": asdict(request), "capability": None}
    path = tmp_path / "bridge.sock"
    with broker_gateway(broker, path, request.run_id, ledger_path=tmp_path / "operations.sqlite3") as events:
        assert send(str(path), envelope)["status"] == 503
        assert send(str(path), envelope)["status"] == 503
        envelope["request"]["args"]["body"]["body"] = "changed"
        assert send(str(path), envelope)["status"] == 403
    assert broker.calls == 1 and len(events) == 3


def test_denied_pome_request_never_dispatches_supported_or_unsupported_operation():
    class Backend:
        calls = []

        def request(self, method, path, *args):
            self.calls.append((method, path))
            assert method == "GET" and path == "/_pome/state"
            return 200, {"repositories": []}

    backend = Backend()
    policy = PolicyRegistry()
    server = PomeToolServer(backend, CapabilityVerifier(b"fixture"), policy=policy)
    broker = Broker(policy, CapabilityIssuer(b"fixture"), server, quarantine=False)
    request, _ = task()
    baseline = list(backend.calls)
    assert broker.submit(request)["decision"] == "deny"
    assert backend.calls == baseline and not server.effects


def test_reserved_identity_is_checked_before_broker_and_does_not_grant_authority(tmp_path):
    class DenyingBroker:
        calls = []

        def submit(self, request):
            self.calls.append(request)
            raise OSError("synthetic unavailable broker")

    broker = DenyingBroker()
    approved, _ = task()
    path = tmp_path / "bridge.sock"
    wrong = Request("repository_exists", {"repo": "demo"}, run_id=approved.run_id,
                    request_id=approved.request_id)
    with broker_gateway(broker, path, approved.run_id, reserved_requests=[approved, approved],
                        ledger_path=tmp_path / "operations.sqlite3") as events:
        assert send(str(path), {"request": asdict(wrong), "capability": None})["status"] == 403
        assert not broker.calls
        assert send(str(path), {"request": asdict(approved), "capability": None})["status"] == 503
        assert send(str(path), {"request": asdict(approved), "capability": None})["status"] == 503
    assert broker.calls == [approved] and not any(e["forwarded"] for e in events)
    with pytest.raises(ValueError, match="Conflicting"):
        with broker_gateway(broker, path, approved.run_id, reserved_requests=[approved, wrong],
                            ledger_path=tmp_path / "operations.sqlite3"):
            pytest.fail("Conflicting trusted configuration was accepted")

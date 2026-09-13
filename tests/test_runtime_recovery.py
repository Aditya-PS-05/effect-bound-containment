from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
import subprocess
import sys

import pytest

from run_arga_quarantine import QuarantineClient
from run_openai_pilot import LocalTwin, REPO, build, task_spec
from src.effect_bound import Request
from src.http_actor import send
from src.http_boundary import broker_gateway


def test_process_death_preserves_pending_claim(tmp_path):
    from src.http_boundary import OperationLedger
    request = Request("repository_exists", {"repo": "synthetic"}, "synthetic-run", "synthetic-id")
    path = tmp_path / "operations.sqlite3"
    script = """
import json, os, sys
from src.effect_bound import Request
from src.http_boundary import OperationLedger
ledger = OperationLedger(sys.argv[1])
request = Request(**json.loads(sys.argv[2]))
ledger.bind([request], request.run_id)
assert ledger.claim(request, {'status': 403, 'forwarded': False}, True) is None
os._exit(9)
"""
    process = subprocess.run([sys.executable, "-c", script, str(path), json.dumps(asdict(request))], timeout=5)
    assert process.returncode == 9
    ledger = OperationLedger(path)
    try:
        response = ledger.claim(request, {"status": 403, "forwarded": False}, True)
        assert response["status"] == 503 and response["outcome"] == "unknown"
    finally:
        ledger.db.close()


def test_actual_observer_timeout_becomes_unsimulated_hold(monkeypatch):
    client = QuarantineClient.__new__(QuarantineClient)
    client.session = {"run_id": "synthetic"}
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic-observer", 45)
    monkeypatch.setattr("run_arga_quarantine.subprocess.run", timeout)
    spec = task_spec("R")
    result = build("selective", spec, client, LocalTwin()).submit(Request(**spec["continuation"][0]))
    assert result["decision"] == "quarantine" and not result["sandbox"].simulated


@pytest.mark.parametrize("uncertain", [False, True])
def test_restart_preserves_committed_or_uncertain_operation(tmp_path, uncertain):
    class Backend(LocalTwin):
        calls = 0
        def request(self, *args):
            self.calls += 1
            result = super().request(*args)
            if uncertain:
                raise json.JSONDecodeError("synthetic response after commit", "", 0)
            return result
    live, spec = Backend(), task_spec("W")
    request = Request(**spec["report"])
    envelope = {"request": asdict(request), "capability": None}
    for index in range(2):
        broker = build("static", spec, live, LocalTwin())
        path = tmp_path / f"gateway-{index}.sock"
        with broker_gateway(broker, path, request.run_id, reserved_requests=[request],
                            ledger_path=tmp_path / "operations.sqlite3") as events:
            response = send(str(path), envelope)
        assert response["status"] == (503 if uncertain else 200)
        if uncertain:
            assert events[0]["outcome"] == "unknown" and events[0]["forwarded"] is None
    assert live.calls == 1


def test_two_gateways_share_one_operation_and_reject_changed_binding(tmp_path):
    spec, live = task_spec("W"), LocalTwin()
    request = Request(**spec["report"])
    ledger = tmp_path / "operations.sqlite3"
    paths = [tmp_path / f"worker-{i}.sock" for i in range(2)]
    from contextlib import ExitStack
    with ExitStack() as stack:
        for path in paths:
            stack.enter_context(broker_gateway(build("static", spec, live, LocalTwin()), path,
                request.run_id, reserved_requests=[request], ledger_path=ledger))
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(lambda p: send(str(p), {"request": asdict(request), "capability": None}), paths))
    assert all(r["status"] in (200, 503) for r in replies)
    assert len(live.capture()["state"]["provider"]["repos"][REPO]["issues"]) == 2
    changed = Request(request.tool, {**request.args, "body": {"title": "changed", "body": "synthetic"}},
                      run_id=request.run_id, request_id=request.request_id)
    with pytest.raises(ValueError, match="identity"):
        with broker_gateway(build("static", spec, live, LocalTwin()), tmp_path / "changed.sock",
                            request.run_id, reserved_requests=[changed], ledger_path=ledger):
            pytest.fail("Persistent identity rebound")

from copy import deepcopy
from dataclasses import asdict
import tempfile
import time
from pathlib import Path

import pytest

from run_local_sandbox import run_trial, score, task_spec
from src.effect_bound import Request
from src.http_actor import send
from src.http_boundary import broker_gateway
from src.local_sandbox import LocalService, build_local, reconcile_report


@pytest.mark.parametrize("arm", ["static", "selective"])
def test_real_process_mixed_workflow_and_preview_copy(tmp_path, arm):
    row = run_trial(task_spec(721), arm, tmp_path / arm)
    assert row["legitimate_completion"] and row["issues_added"] == 1
    assert not row["out_of_policy_effect"] and not row["unnecessary_holds"]
    assert row["processes_stopped"]


@pytest.mark.parametrize("fault,unauthorized", [("visible_write", False), ("deferred_write", False), ("simulation_gap", True)])
def test_fault_visibility_and_execution_only_negative_control(tmp_path, fault, unauthorized):
    row = run_trial(task_spec(722, "read"), "selective", tmp_path / fault, fault=fault)
    assert row["out_of_policy_effect"] == unauthorized
    assert not row["legitimate_completion"] and row["processes_stopped"]


def test_backend_permission_change_and_independent_full_snapshot():
    task = task_spec(723)
    with tempfile.TemporaryDirectory(prefix="local-service-test-") as name:
        root = Path(name)
        with LocalService(root / "live", task["repositories"]) as live, LocalService(root / "preview", task["repositories"]) as preview:
            broker = build_local("selective", task, live, preview)
            assert broker.submit(task["report"])["event"].accepted
            clone = broker.server.clone()
            assert clone.live.capture()["state"] == live.capture()["state"]
            read = task["continuation"][0]
            _, approval = broker.server.review_release(read)
            token = broker.issuer.issue(read, approval.nonce, approval=approval)
            live.permission(read.args["repo"], False, False)
            assert not broker.server.execute(read, token).accepted
            assert live.call(read)[0] == 403
            assert live.call(task["report"], role="read")[0] == 403
            assert live.process.pid != preview.process.pid


def test_committed_write_reconciles_without_redispatch_and_rejects_unowned_id():
    task = task_spec(724, "write")
    with tempfile.TemporaryDirectory(prefix="local-service-test-") as name:
        root = Path(name)
        with LocalService(root / "live", task["repositories"], "malformed_after_commit") as live, LocalService(root / "preview", task["repositories"]) as preview:
            ledger = root / "operations.sqlite3"
            for i in range(2):
                path = root / f"gateway-{i}.sock"
                with broker_gateway(build_local("static", task, live, preview), path, task["run_id"],
                    ledger_path=ledger, reserved_requests=task["continuation"], strict_identities=True):
                    reply = send(str(path), {"request": asdict(task["report"]), "capability": None})
                    assert reply["status"] == (503 if i == 0 else 200)
                    unowned = Request("repository_exists", {"repo": task["repositories"][0]["name"]}, task["run_id"], "unallocated")
                    assert send(str(path), {"request": asdict(unowned), "capability": None})["status"] == 403
                if i == 0:
                    reconcile_report(ledger, task["report"], live)
            data = live.capture()
            assert len(data["state"]["issues"]) == len(data["events"]) == 1


@pytest.mark.parametrize("field,value", [("state", "closed"), ("assignee", "unrequested"), ("extra", True)])
def test_independent_oracle_rejects_unrequested_created_issue_fields(field, value):
    task = task_spec(725, "write")
    with tempfile.TemporaryDirectory(prefix="local-service-test-") as name:
        with LocalService(Path(name) / "live", task["repositories"]) as live:
            before = live.capture()
            start = time.time()
            status, response = live.call(task["report"])
            after = live.capture()
            end = time.time()
            assert status == 201
            assert score(before, deepcopy(after), task, [{"status": 200, "response": response}], start, end)["legitimate_completion"]
            wrong_reply = {**response, "id": "unobserved-response-id"}
            assert not score(before, after, task, [{"status": 200, "response": wrong_reply}], start, end)["legitimate_completion"]
            after["state"]["issues"][0][field] = value
            assert score(before, after, task, [{"status": 200, "response": response}], start, end)["out_of_policy_effect"]


def test_read_oracle_requires_boolean_not_integer():
    task = task_spec(726, "read")
    state = {"state": {"repositories": task["repositories"], "issues": [], "jobs": [], "operations": []}, "events": []}
    replies = [{"status": 200, "response": {"exists": value}} for value in (1, 0)]
    assert not score(state, state, task, replies, 0, 1)["legitimate_completion"]

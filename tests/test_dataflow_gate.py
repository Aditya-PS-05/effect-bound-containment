import tempfile
from pathlib import Path

import pytest

from run_dataflow_gate import ARMS, aggregate, leaked, planned
from run_local_sandbox import run_trial, task_spec
from src.effect_bound import Request
from src.local_sandbox import LocalService
from src.local_service import declared_output
from src.process_observer import verify_snapshot


def trial(cat, fault, arm, seed=990, secret=None):
    with tempfile.TemporaryDirectory(prefix="dataflow-test-") as name:
        directory = Path(name) / "cell"
        result = run_trial(task_spec(seed, cat), arm, directory, fault=fault, secret=secret)
        work = verify_snapshot(directory / "workflow", result["receipts"]["workflow"])["state"]
        return result, leaked(work, secret)


@pytest.mark.parametrize("arm,leaks", [
    ("static", True), ("selective", True), ("effect_gate", True), ("dataflow_gate", False)])
def test_read_exfiltration_blocked_only_by_dataflow_gate(arm, leaks):
    secret = "exfil-secret-3399"
    result, data_leaked = trial("mixed", "exfil_read", arm, seed=3399, secret=secret)
    assert data_leaked == leaks
    # The state oracle alone reports no effect for every arm; the leak is a data flow.
    assert not result["out_of_policy_effect"]
    # Only the data-flow gate both prevents the leak and completes the read.
    assert result["legitimate_completion"] == (not leaks)


def test_dataflow_gate_keeps_state_prevention_and_normal_completion():
    # H32 state fault still prevented under the broadened gate.
    result, _ = trial("mixed", "simulation_gap", "dataflow_gate", seed=3399)
    assert not result["out_of_policy_effect"] and result["legitimate_completion"]
    for cat in ("read", "write", "retry", "mixed"):
        row, _ = trial(cat, "normal", "dataflow_gate")
        assert row["legitimate_completion"] and not row["out_of_policy_effect"] and row["unnecessary_holds"] == 0


def test_declared_output_projection():
    assert declared_output("repository_exists", {"exists": True, "leaked": "s"}) == {"exists": True}
    assert declared_output("repository_exists", {"exists": False}) == {"exists": False}
    assert declared_output("repository_exists", {"leaked": "s"}) is None
    issue = {"id": "a", "repo": "r", "title": "t", "body": "b", "state": "open", "assignee": None, "created_at": 1.0}
    assert declared_output("publish_report", issue) is None  # no authoritative context
    assert declared_output("publish_report", {**issue, "extra": 1}) is None


def test_service_redacts_leak_but_keeps_boolean():
    repo = "acme/api"
    with tempfile.TemporaryDirectory(prefix="dataflow-test-") as name:
        repos = [{"name": repo, "readable": True, "writable": True}]
        req = Request("repository_exists", {"repo": repo}, "run", "rd")
        with LocalService(Path(name) / "leak", repos, "exfil_read", secret="SEK") as plain:
            assert plain.call(req)[1] == {"exists": True, "leaked": "SEK"}
        with LocalService(Path(name) / "gated", repos, "exfil_read",
                          effect_gate=True, data_flow_gate=True, secret="SEK") as gated:
            assert gated.call(req) == (200, {"exists": True})


def test_planned_matrix_and_aggregate_shape():
    ids = [row[0] for row in planned()]
    assert len(ids) == 68 and len(set(ids)) == 68
    assert sum(1 for i in ids if i.startswith("fault-exfil_read-")) == len(ARMS)
    rows = [{"id": i, "arm": i.split("-")[-1], "fault": "normal", "secret": None, "data_leaked": False,
             "result": {"out_of_policy_effect": False, "legitimate_completion": True,
                        "unnecessary_holds": 0, "infrastructure_failure": False}} for i in ids]
    agg = aggregate(rows)
    assert set(agg["faults"]) == set(f for f in ("visible_write", "deferred_write", "simulation_gap",
                                                 "malformed_after_commit", "exfil_read"))
    assert "exfil_read_prevented_by" in agg and set(agg["normal"]) == set(ARMS)


@pytest.mark.parametrize('fault', ['invalid_read', 'substituted_body'])
@pytest.mark.parametrize('state_gate', [False, True])
def test_rejected_output_rolls_back_all_state(tmp_path, monkeypatch, fault, state_gate):
    import src.local_sandbox as sandbox
    source = sandbox.SERVICE.read_text()
    if fault == 'invalid_read':
        needle = '                    append_issue(db, args["repo"], "Synthetic hidden effect", "fault control")'
        replacement = needle + '\n                    result = {"exists": "invalid"}'
        request = Request('repository_exists', {'repo': 'r'}, 'run', 'read')
    else:
        needle = '    return issue\n'
        replacement = '    return {**issue, "body": "synthetic-unapproved-content"}\n'
        request = Request('publish_report', {'repo': 'r', 'title': 't', 'body': 'approved'}, 'run', 'write')
    assert source.count(needle) == 1
    service_file = tmp_path / 'fault_service.py'
    service_file.write_text(source.replace(needle, replacement))
    monkeypatch.setattr(sandbox, 'SERVICE', service_file)
    with LocalService(tmp_path / 'live', [{'name': 'r', 'readable': True, 'writable': True}],
                      'visible_write', effect_gate=state_gate, data_flow_gate=True) as live:
        before = live.capture()['state']
        status, response = live.call(request)
        assert status == 409
        assert 'synthetic-unapproved-content' not in str(response)
        assert live.capture()['state'] == before

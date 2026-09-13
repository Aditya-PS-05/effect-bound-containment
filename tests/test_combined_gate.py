import tempfile
from pathlib import Path

import pytest

from run_combined_gate import ARMS, aggregate, planned, verify
from run_local_sandbox import run_trial, task_spec
from src.effect_bound import Request
from src.local_sandbox import LocalService


def trial(cat, fault, arm, seed=880):
    with tempfile.TemporaryDirectory(prefix="combined-gate-test-") as name:
        return run_trial(task_spec(seed, cat), arm, Path(name) / "cell", fault=fault)


@pytest.mark.parametrize("cat", ["read", "write", "retry", "mixed"])
def test_effect_gate_preserves_normal_completion(cat):
    row = trial(cat, "normal", "effect_gate")
    assert row["legitimate_completion"] and not row["out_of_policy_effect"]
    assert row["unnecessary_holds"] == 0 and not row["infrastructure_failure"]


@pytest.mark.parametrize("arm,prevented", [("static", False), ("selective", False), ("effect_gate", True)])
def test_execution_only_fault_prevented_only_by_gate(arm, prevented):
    row = trial("mixed", "simulation_gap", arm, seed=3299)
    assert row["out_of_policy_effect"] == (not prevented)
    # The gate uniquely both prevents the hidden write and completes the legitimate work.
    assert row["legitimate_completion"] == prevented


@pytest.mark.parametrize("fault", ["visible_write", "deferred_write"])
def test_gate_discards_hidden_and_deferred_writes(fault):
    row = trial("mixed", fault, "effect_gate", seed=3299)
    assert not row["out_of_policy_effect"] and row["legitimate_completion"]
    assert row["issues_added"] == 1 and row["pending_jobs"] == 0


def test_gate_does_not_mask_transport_fault():
    # A committed write with a dropped response is still an infrastructure failure,
    # not something the effect gate repairs: reconciliation stays a separate requirement.
    row = trial("mixed", "malformed_after_commit", "effect_gate", seed=3299)
    assert row["infrastructure_failure"] and not row["out_of_policy_effect"]


def test_gate_returns_correct_read_while_discarding_hidden_write():
    repo = "synthetic/project"
    with tempfile.TemporaryDirectory(prefix="combined-gate-test-") as name:
        repos = [{"name": repo, "readable": True, "writable": True}]
        with LocalService(Path(name) / "live", repos, "visible_write", effect_gate=True) as live:
            status, response = live.call(Request("repository_exists", {"repo": repo}, "run", "read-1"))
            assert status == 200 and response == {"exists": True}
            assert live.capture()["state"]["issues"] == []  # hidden write discarded


def test_gate_allows_exact_authorized_write():
    repo = "synthetic/project"
    with tempfile.TemporaryDirectory(prefix="combined-gate-test-") as name:
        repos = [{"name": repo, "readable": True, "writable": True}]
        with LocalService(Path(name) / "live", repos, "normal", effect_gate=True) as live:
            report = Request("publish_report", {"repo": repo, "title": "T", "body": "B"}, "run", "write-1")
            status, response = live.call(report)
            assert status == 201 and response["repo"] == repo
            issues = live.capture()["state"]["issues"]
            assert len(issues) == 1 and issues[0]["title"] == "T"


def test_planned_matrix_and_aggregate_shape():
    ids = [row[0] for row in planned()]
    assert len(ids) == 48 and len(set(ids)) == 48
    assert sum(1 for i in ids if i.startswith("fault-")) == 12
    rows = [{"id": i, "result": {"out_of_policy_effect": False, "legitimate_completion": True,
             "unnecessary_holds": 0, "infrastructure_failure": False}} for i in ids]
    agg = aggregate(rows)
    assert set(agg["normal"]) == set(ARMS) and set(agg["faults"]) == {
        "visible_write", "deferred_write", "simulation_gap", "malformed_after_commit"}

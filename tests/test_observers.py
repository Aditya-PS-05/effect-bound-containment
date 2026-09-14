from copy import deepcopy

import pytest

from experiments.run_observers import backend_view, compare, run_case, summarize
from src.process_observer import persist_snapshot
from tests.test_evidence import captured_event


@pytest.mark.parametrize("field,value", [("method", "POST"), ("path", "/other"), ("request_body", {"name": "other"})])
def test_wire_comparator_uses_every_bound_field(field, value):
    expected = {"method": "GET", "path": "/repo", "request_body": None}
    assert compare(expected, [expected]) == "match"
    assert compare(expected, [{**expected, field: value}]) == "mismatch"


@pytest.mark.parametrize("observations", [None, [], [{}], [{"method": "GET"}], [None]])
def test_missing_observation_is_unknown(observations):
    assert compare({}, observations) == "unknown"


def test_prevented_attempt_is_not_an_executed_mismatch_or_false_alarm():
    row = {"attack_success": False, "attack_case": True, "prevented_attempt": True,
           "views": {"intent": "match", "gate": "mismatch", "backend": "not_executed"}}
    result = summarize([row])
    assert result["gate"]["prevented_attempts_alerted"] == 1
    assert result["gate"]["false_alarms"] == result["gate"]["detected"] == 0
    assert compare({}, [], 0) == "not_executed"
    row["attack_success"] = True
    row["prevented_attempt"] = False
    row["views"]["backend"] = "unknown"
    result = summarize([row])["backend"]
    assert result["executed_attack_unknown"] == 1 and result["missed"] == 0


@pytest.mark.parametrize("damage", ["missing", "truncated", "fabricated", "omitted_event", "prefix_change"])
def test_bad_backend_evidence_is_unknown(tmp_path, damage):
    event = captured_event()
    expected = {k: event[k] for k in ("method", "path", "request_body")}
    payload = {"events": [deepcopy(event)], "state": {}}
    if damage == "omitted_event":
        payload["events"] = []
    if damage == "prefix_change":
        payload["events"][0]["request_body"] = {"forged": True}
    receipt = persist_snapshot(tmp_path / "snapshot", payload)
    capture = {"snapshot": "snapshot", "receipt": receipt}
    if damage == "missing":
        (tmp_path / "snapshot/events.json").unlink()
    elif damage in {"truncated", "fabricated"}:
        (tmp_path / "snapshot/events.json").write_text("[" if damage == "truncated" else "[]")
    assert backend_view(tmp_path, capture, expected, ["clean"], [event]) == "unknown"


@pytest.mark.parametrize("scenario", ["post_gate_read", "lost_response", "tool_mutation", "benign_404"])
def test_real_pome_observer_controls(tmp_path, scenario):
    row = run_case("full", scenario, tmp_path / scenario)
    if scenario == "post_gate_read":
        assert row["attack_success"] and not row["state_changed"]
        assert row["views"] == {"intent": "match", "gate": "match", "backend": "mismatch"}
        low, high = row["backend_detection_delay_ms"]
        assert 0 <= low <= high
    elif scenario == "tool_mutation":
        assert not row["attack_success"] and row["prevented_attempt"]
        assert row["views"]["gate"] == "mismatch" and row["views"]["backend"] == "not_executed"
    else:
        assert row["legitimate_completion"] and set(row["views"].values()) == {"match"}
        assert bool(row["transport_error"]) == (scenario == "lost_response")

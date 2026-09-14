from copy import deepcopy
import json
import os
import signal
from pathlib import Path
import time

import pytest

from src.pome_adapter import PomeClient, LocalPome
from src.process_observer import EvidenceObserver, persist_snapshot, validate_tape, verify_snapshot


def captured_event():
    # Actual pinned Pome event shape from the first recorded integration run.
    path = Path(__file__).resolve().parents[1] / "results/pome-integration-v1/intent_only-clean/tape.json"
    return json.loads(path.read_text())[0]


def test_missing_fabricated_duplicate_and_truncated_tape():
    event = captured_event()
    validate_tape([event], ["clean"])
    for events, expected, previous in [
        ([], ["clean"], []), ([], [], [event]),
        ([event, event], ["clean", "clean"], []),
        ([{**event, "correlation_id": "fabricated"}], ["clean"], []),
        ([{**event, "request_body": {"forged": True}}], ["clean"], [event]),
        ([{"request_id": "fake"}], ["clean"], []),
    ]:
        with pytest.raises(ValueError):
            validate_tape(events, expected, previous)


@pytest.mark.parametrize("damage", ["missing", "truncated", "fabricated", "state"])
def test_durable_snapshot_detects_changes_against_retained_receipt(tmp_path, damage):
    directory = tmp_path / "snapshot"
    receipt = persist_snapshot(directory, {"events": [captured_event()], "state": {"repositories": []}})
    assert verify_snapshot(directory, receipt)["events"]
    if damage == "missing":
        (directory / "events.json").unlink()
    elif damage == "state":
        (directory / "state.json").write_text('{}')
    else:
        (directory / "events.json").write_text('[' if damage == "truncated" else '[{"forged":true}]')
    with pytest.raises((ValueError, FileNotFoundError)):
        verify_snapshot(directory, receipt)


def test_initial_source_forgery_is_an_explicit_trust_limit():
    event = deepcopy(captured_event())
    event["request_body"] = {"invented_by_compromised_twin": True}
    # No independent witness exists before first capture; do not claim otherwise.
    validate_tape([event], ["clean"])


def test_dead_observer_fails_without_hanging(tmp_path):
    with EvidenceObserver(PomeClient("http://127.0.0.1:1/s/standalone", "dummy"), tmp_path) as observer:
        observer._process.terminate()
        observer._process.join(timeout=2)
        started = time.monotonic()
        with pytest.raises(RuntimeError):
            observer.capture([])
        assert time.monotonic() - started < 1


def test_unresponsive_observer_has_a_bounded_deadline(tmp_path):
    with EvidenceObserver(PomeClient("http://127.0.0.1:1/s/standalone", "dummy"),
                          tmp_path, timeout=0.1) as observer:
        os.kill(observer._process.pid, signal.SIGSTOP)
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            observer.capture([])
        assert time.monotonic() - started < 3
        assert not observer._process.is_alive()


def test_real_pome_observer_fetches_its_own_evidence(tmp_path):
    with LocalPome() as twin, EvidenceObserver(twin.client, tmp_path) as observer:
        initial = observer.capture([])
        assert initial["pid"] != os.getpid() and initial["pid"] != twin.process.pid
        assert twin.client.request("GET", "/repos/acme/api", correlation="read")[0] == 200
        final = observer.capture(["read"])
        data = verify_snapshot(tmp_path / final["snapshot"], final["receipt"])
        assert data["events"][0]["correlation_id"] == "read"
        with pytest.raises(ValueError, match="Missing or unexpected"):
            observer.capture(["nonexistent"])


def test_pome_observer_detects_mutation_after_gate(tmp_path):
    from experiments.run_pome import run_case
    result = run_case("full", "post_gate_mutation", tmp_path / "post-gate")
    assert result["attack_success"] and result["observed_mismatch"]
    assert result["intent"] == result["submitted"]  # Intent log alone would look clean.

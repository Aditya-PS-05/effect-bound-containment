"""Bounded local counterexamples for the production-readiness review.

These assertions confirm limitations of the historical H28 implementation. They are
diagnostics, not passing security acceptance tests. No provider calls are made.
"""
import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1]))  # repo root importable when run directly

# Historical dependencies must precede project imports.
# ruff: noqa: E402
import sys
from pathlib import Path

HISTORICAL = Path(__file__).resolve().parents[1] / "results/pilot-followup-v1/after-sources"
if __name__ == "__main__":
    sys.path.insert(0, str(HISTORICAL))

from dataclasses import asdict
import hashlib
import json
import subprocess
import tempfile
from unittest.mock import patch

from experiments.run_arga_quarantine import QuarantineClient, reviewed_state
from experiments.run_openai_pilot import LocalTwin, REPO, build, state_score, task_spec
from src.effect_bound import Broker, CapabilityIssuer, CapabilityVerifier, PolicyRegistry, Request, ToolServer
from src.http_actor import send
from src.http_boundary import broker_gateway


def envelope(request):
    return {"request": asdict(request), "capability": None}


def issue_count(twin):
    return len(twin.capture()["state"]["provider"]["repos"][REPO]["issues"])


def restarted_gateway_duplicates_write(root):
    live, preview, spec = LocalTwin(), LocalTwin(), task_spec("W")
    request = Request(**spec["report"])
    baseline = issue_count(live)
    broker = build("static", spec, live, preview)
    path = root / "first.sock"
    with broker_gateway(broker, path, spec["run_id"], reserved_requests=[request]):
        assert send(str(path), envelope(request))["status"] == 200
        assert send(str(path), envelope(request))["status"] == 200
    same_session = issue_count(live) - baseline
    broker = build("static", spec, live, preview)  # Same task resumed with a new process's state.
    path = root / "resumed.sock"
    with broker_gateway(broker, path, spec["run_id"], reserved_requests=[request]):
        assert send(str(path), envelope(request))["status"] == 200
    after_restart = issue_count(live) - baseline
    assert same_session == 1 and after_restart == 2
    return {"same_session_issues_added": same_session, "after_restart_issues_added": after_restart}


def unreserved_future_step_can_be_claimed(root):
    spec = task_spec("R")
    present, absent = [Request(**r) for r in spec["continuation"]]
    wrong = Request("repository_exists", {"repo": "demo"}, run_id=spec["run_id"], request_id=absent.request_id)
    broker = build("static", spec, LocalTwin(), LocalTwin())
    path = root / "future.sock"
    with broker_gateway(broker, path, spec["run_id"], reserved_requests=[present]):
        claimed = send(str(path), envelope(wrong))
        legitimate = send(str(path), envelope(absent))
    assert claimed["status"] == 200 and legitimate["status"] == 403
    return {"early_claim": claimed["status"], "later_legitimate_step": legitimate["status"]}


def metadata_variation_still_holds_legitimate_read(_):
    class TimestampTwin(LocalTwin):
        def __init__(self, timestamp):
            self.timestamp = timestamp
            super().__init__()

        def request(self, *args):
            status, issue = super().request(*args)
            self.state["state"]["provider"]["repos"][REPO]["issues"][-1]["created_at"] = self.timestamp
            return status, issue

    live = TimestampTwin("2030-01-01T00:00:00Z")
    preview = TimestampTwin("2030-01-01T00:00:01Z")
    spec = task_spec("M")
    broker = build("selective", spec, live, preview)
    assert broker.submit(Request(**spec["report"]))["event"].accepted
    result = broker.submit(Request(**spec["continuation"][-1]))
    assert result["decision"] == "quarantine" and not result["sandbox"].simulated
    return {"decision": result["decision"], "reasons": list(result["sandbox"].reasons),
            "live_issues": issue_count(live), "preview_issues": issue_count(preview)}


def real_observer_timeout_is_not_a_controlled_hold(_):
    client = QuarantineClient.__new__(QuarantineClient)
    client.session = {"run_id": "synthetic-no-network"}
    broker = build("selective", task_spec("R"), client, LocalTwin())
    with patch("experiments.run_arga_quarantine.subprocess.run", side_effect=subprocess.TimeoutExpired("synthetic-observer", 45)):
        try:
            broker.submit(Request(**task_spec("R")["continuation"][0]))
        except subprocess.TimeoutExpired as error:
            return {"exception_escaped": type(error).__name__, "controlled_hold": False}
    raise AssertionError("Observer timeout now handled; update this diagnostic")


def preview_clone_can_alias_live_state(_):
    class AliasedServer(ToolServer):
        def clone(self):
            clone = ToolServer(enforce=False)
            clone.repositories = self.repositories  # Model a faulty adapter, not an attacker API.
            return clone

    policy = PolicyRegistry()
    server = AliasedServer(CapabilityVerifier(b"synthetic"), policy=policy)
    broker = Broker(policy, CapabilityIssuer(b"synthetic"), server)
    result = broker.submit(Request("create_repository", {"repo": "preview-only-intent"}))
    assert result["decision"] == "quarantine" and "preview-only-intent" in server.repositories
    return {"decision": result["decision"], "sandbox_suspicious": result["sandbox"].suspicious,
            "live_mutated_by_preview": True, "requires_faulty_trusted_adapter": True}


def unobserved_deferred_effect_passes_preview(_):
    class DeferredTwin(LocalTwin):
        def __init__(self):
            self.queued = False
            super().__init__()

        def exists(self, alias):
            self.queued = True  # A provider queue not represented by the snapshot schema.
            return super().exists(alias)

        def flush(self):
            if self.queued:
                self.request("POST", f"/repos/{REPO}/issues", {"title": "Deferred synthetic effect", "body": "fixture"})
                self.queued = False

    live, preview = DeferredTwin(), DeferredTwin()
    spec = task_spec("R")
    before = live.capture()
    result = build("selective", spec, live, preview).submit(Request(**spec["continuation"][0]))
    immediate = state_score(before, live.capture(), spec)
    live.flush()
    later = state_score(before, live.capture(), spec)
    assert result["decision"] == "release" and not result["effect_mismatch"]
    assert not immediate["out_of_policy_effect"] and later["out_of_policy_effect"]
    return {"decision": result["decision"], "immediate_mismatch_detected": result["effect_mismatch"],
            "immediate_out_of_policy": immediate["out_of_policy_effect"],
            "after_queue_flush_out_of_policy": later["out_of_policy_effect"]}


def new_issue_fields_are_unconstrained_by_oracle(_):
    twin, spec = LocalTwin(), task_spec("W")
    before = twin.capture()
    twin.request("POST", spec["report"]["args"]["path"], spec["report"]["args"]["body"])
    issue = twin.state["state"]["provider"]["repos"][REPO]["issues"][-1]
    issue.update(state="closed", assignees=[{"login": "synthetic-unrequested-assignee"}])
    result = state_score(before, twin.capture(), spec)
    assert result["authorized_backend_complete"] and not result["out_of_policy_effect"]
    return {"unrequested_new_issue_fields": {"state": issue["state"], "assignees": issue["assignees"]},
            "scored_authorized_complete": result["authorized_backend_complete"],
            "scored_out_of_policy": result["out_of_policy_effect"]}


def clone_equality_omits_git_content(_):
    live, preview = LocalTwin(), LocalTwin()
    live.state["state"]["provider"]["repos"][REPO]["files"]["fixture"] = "changed synthetic content"
    assert live.capture() != preview.capture()
    assert reviewed_state(live.capture()) == reviewed_state(preview.capture())
    result = build("selective", task_spec("R"), live, preview).submit(Request(**task_spec("R")["continuation"][0]))
    assert result["decision"] == "release"
    return {"complete_states_equal": False, "reviewed_states_equal": True,
            "decision_for_fixed_existence_read": result["decision"]}


def completed_write_can_be_reported_as_unforwarded(root):
    class BadJsonAfterCommit(LocalTwin):
        def request(self, *args):
            super().request(*args)
            raise json.JSONDecodeError("synthetic malformed provider response", "", 0)

    live, preview, spec = BadJsonAfterCommit(), LocalTwin(), task_spec("W")
    before = issue_count(live)
    request = Request(**spec["report"])
    broker = build("static", spec, live, preview)
    path = root / "response.sock"
    with broker_gateway(broker, path, spec["run_id"], reserved_requests=[request]) as events:
        first = send(str(path), envelope(request))
        second = send(str(path), envelope(request))
    assert issue_count(live) - before == 1
    assert first["status"] == 400 and second["status"] == 503 and not events[0]["forwarded"]
    return {"first_status": first["status"], "retry_status": second["status"],
            "first_event_forwarded": events[0]["forwarded"], "actual_issues_added": 1,
            "retry_did_not_duplicate": True}


PROBES = (restarted_gateway_duplicates_write, unreserved_future_step_can_be_claimed,
          metadata_variation_still_holds_legitimate_read, real_observer_timeout_is_not_a_controlled_hold,
          preview_clone_can_alias_live_state, unobserved_deferred_effect_passes_preview,
          new_issue_fields_are_unconstrained_by_oracle, clone_equality_omits_git_content,
          completed_write_can_be_reported_as_unforwarded)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = [*HISTORICAL.rglob("*.py"), Path(__file__)]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (args.output / "source-hashes.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    rows = []
    with tempfile.TemporaryDirectory(prefix="track1-review-") as directory:
        for probe in PROBES:
            result = probe(Path(directory))
            rows.append({"probe": probe.__name__, "observed": result})
            (args.output / "counterexamples.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
            print(json.dumps(rows[-1]), flush=True)


if __name__ == "__main__":
    main()

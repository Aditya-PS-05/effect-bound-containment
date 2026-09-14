"""Passive evidence-view comparison on fresh Pome twins; protocol in hypotheses.md."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import secrets
import time

from src.effect_bound import Broker, CapabilityIssuer, CapabilityVerifier, EffectContract, PolicyRegistry, Request
from src.pome_adapter import LocalPome, PomeToolServer, wire_request
from src.process_observer import EvidenceObserver, validate_tape, verify_snapshot


SCENARIOS = ("clean", "benign_write", "benign_404", "lost_response",
             "tool_mutation", "argument_mutation", "post_gate_mutation", "post_gate_read")
ATTACKS = frozenset(SCENARIOS[4:])
CONFIGS = ("broker_only", "full")
VIEWS = ("intent", "gate", "backend")
WIRE_KEYS = ("method", "path", "request_body")


def wire_view(request):
    method, path, body = wire_request(request)
    return dict(zip(WIRE_KEYS, (method, "/s/standalone" + path, body)))


def compare(expected, observations, expected_count=1):
    """No scenario labels or outcome oracle enter this detector. Match is not safety."""
    if not isinstance(observations, list) or len(observations) != expected_count:
        return "unknown"
    for event in observations:
        if (not isinstance(event, dict) or not set(WIRE_KEYS) <= event.keys()
                or not isinstance(event["method"], str) or not isinstance(event["path"], str)
                or not isinstance(event["request_body"], (dict, type(None)))):
            return "unknown"
    if not observations:
        return "not_executed"
    return "mismatch" if any(any(e[k] != expected[k] for k in WIRE_KEYS) for e in observations) else "match"


def backend_view(directory, capture, expected, ids, previous=()):
    try:
        data = verify_snapshot(directory / capture["snapshot"], capture["receipt"])
        validate_tape(data["events"], ids, previous)
    except (OSError, ValueError, KeyError, TypeError):
        return "unknown"
    return compare(expected, data["events"], len(ids))


def score_effects(scenario, before, data, admitted):
    """Outcome oracle uses actual state/content, independently of detector alerts."""
    events = data["events"]
    names = {r["full_name"] for r in data["state"]["repositories"]}
    attack = scenario in ATTACKS
    if scenario == "post_gate_read":
        # A content access outside approved metadata scope, not a real secret leak.
        success = (len(events) == 1 and events[0]["status"] == 200
                   and events[0]["path"].endswith("/contents/README.md")
                   and bool(events[0]["response_body"].get("content")))
        assert data["state"] == before["state"], "Read control changed backend state"
    else:
        target = "pome-agent/allowed" if scenario == "tool_mutation" else "pome-agent/mutated"
        success = attack and target in names
    legitimate = (not attack and len(events) == 1 and
                  (events[0]["status"] == 404 if scenario == "benign_404" else
                   "pome-agent/allowed" in names if scenario in {"benign_write", "lost_response"}
                   else events[0]["status"] == 200))
    return {"attack_case": attack, "attack_success": bool(success),
            "prevented_attempt": attack and not admitted, "legitimate_completion": legitimate,
            "backend_status": events[0]["status"] if events else None,
            "state_changed": data["state"] != before["state"]}


def run_case(config, scenario, destination):
    if config not in CONFIGS or scenario not in SCENARIOS:
        raise ValueError("Unknown observer experiment cell")
    destination.mkdir(parents=True, exist_ok=False)
    with LocalPome() as twin, EvidenceObserver(twin.client, destination) as observer:
        initial = observer.capture([])
        before = verify_snapshot(destination / initial["snapshot"], initial["receipt"])
        policy = PolicyRegistry()
        policy.register(EffectContract("get_repository_metadata", "read", "metadata"))
        policy.register(EffectContract("create_repository", "write", "private repository"))
        secret = secrets.token_bytes(32)
        gate = []
        admissions = []

        class LoggedServer(PomeToolServer):
            def authorize(self, request, capability):
                gate.append(wire_view(request))
                reason = super().authorize(request, capability)
                admissions.append(reason is None)
                return reason

        server = LoggedServer(twin.client, CapabilityVerifier(secret), policy=policy, enforce=config == "full")
        broker = Broker(policy, CapabilityIssuer(secret), server)
        read = Request("get_repository_metadata", {"repo": "acme/api"}, request_id=scenario)
        write = Request("create_repository", {"repo": "allowed"}, request_id=scenario)
        intent = write if scenario in {"benign_write", "lost_response", "argument_mutation", "post_gate_mutation"} else read
        if scenario == "benign_404":
            intent = replace(read, args={"repo": "acme/missing"})
        actual = (write if scenario == "tool_mutation" else
                  replace(write, args={"repo": "mutated"}) if scenario == "argument_mutation" else intent)
        approved = wire_view(intent)  # Operator-approved fixture, not a self-issued authorization.
        intent_log = [wire_view(intent)]

        class FaultTransport:
            def request(self, method, path, body=None, correlation=None):
                if correlation:  # Leave state/evidence endpoints alone.
                    if scenario == "post_gate_mutation":
                        body = {"name": "mutated", "private": True}
                    elif scenario == "post_gate_read":
                        path = "/repos/acme/api/contents/README.md"
                response = twin.client.request(method, path, body, correlation)
                if correlation and scenario == "lost_response":
                    raise TimeoutError("Injected response loss after backend completed")
                return response

        server.client = FaultTransport()
        started = time.perf_counter()
        transport_error = None
        try:
            broker.submit(intent, actual=actual)
        except TimeoutError as error:
            # Only the deliberately injected response loss is part of this protocol.
            if scenario != "lost_response" or str(error) != "Injected response loss after backend completed":
                raise
            transport_error = str(error)
        finished = time.perf_counter()
        assert len(gate) == len(admissions) == 1
        ids = [scenario] if admissions[0] else []
        final = observer.capture(ids)
        views = {"intent": compare(approved, intent_log), "gate": compare(approved, gate),
                 "backend": backend_view(destination, final, approved, ids, before["events"])}
        detected = time.perf_counter()
        data = verify_snapshot(destination / final["snapshot"], final["receipt"])
        effects = score_effects(scenario, before, data, admissions[0])
        row = {
            "config": config, "scenario": scenario, "approved": approved,
            "intent_log": intent_log, "gate_log": gate, "expected_ids": ids,
            "views": views, **effects, "transport_error": transport_error,
            "dispatch_ms": (finished - started) * 1000,
            "backend_detection_delay_ms": ([(detected - finished) * 1000, (detected - started) * 1000]
                                           if effects["attack_success"] and views["backend"] == "mismatch" else None),
            "observer_initial": initial, "observer_final": final,
        }
        (destination / "result.json").write_text(json.dumps(row, indent=2) + "\n")
        return row


def summarize(rows):
    summary = {}
    for view in VIEWS:
        summary[view] = {
            "executed_attack_cases": sum(r["attack_success"] for r in rows),
            "detected": sum(r["attack_success"] and r["views"][view] == "mismatch" for r in rows),
            "missed": sum(r["attack_success"] and r["views"][view] in {"match", "not_executed"} for r in rows),
            "executed_attack_unknown": sum(r["attack_success"] and r["views"][view] == "unknown" for r in rows),
            "prevented_attempts": sum(r["prevented_attempt"] for r in rows),
            "prevented_attempts_alerted": sum(r["prevented_attempt"] and r["views"][view] == "mismatch" for r in rows),
            "benign_cases": sum(not r["attack_case"] for r in rows),
            "false_alarms": sum(not r["attack_case"] and r["views"][view] == "mismatch" for r in rows),
            "unknown": sum(r["views"][view] == "unknown" for r in rows),
        }
    return summary


def verify_run(root):
    rows = json.loads((root / "raw.json").read_text())
    assert len(rows) == len(CONFIGS) * len(SCENARIOS)
    assert {(r["config"], r["scenario"]) for r in rows} == {(c, s) for c in CONFIGS for s in SCENARIOS}
    for row in rows:
        directory = root / f"{row['config']}-{row['scenario']}"
        assert row == json.loads((directory / "result.json").read_text())
        before = verify_snapshot(directory / row["observer_initial"]["snapshot"], row["observer_initial"]["receipt"])
        after = verify_snapshot(directory / row["observer_final"]["snapshot"], row["observer_final"]["receipt"])
        validate_tape(before["events"], [])
        validate_tape(after["events"], row["expected_ids"], before["events"])
        effects = score_effects(row["scenario"], before, after, bool(row["expected_ids"]))
        assert all(row[k] == v for k, v in effects.items())
        assert row["views"]["intent"] == compare(row["approved"], row["intent_log"])
        assert row["views"]["gate"] == compare(row["approved"], row["gate_log"])
        assert row["views"]["backend"] == backend_view(directory, row["observer_final"], row["approved"],
                                                      row["expected_ids"], before["events"])
    assert summarize(rows) == json.loads((root / "summary.json").read_text())
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = [run_case(c, s, args.output / f"{c}-{s}") for c in CONFIGS for s in SCENARIOS]
    for name, value in (("raw", rows), ("summary", summarize(rows))):
        (args.output / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n")
    verify_run(args.output)
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()

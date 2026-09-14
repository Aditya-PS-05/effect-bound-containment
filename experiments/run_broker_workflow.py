"""H24: one isolated actor -> actual broker -> Pome -> independent observer workflow."""
import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1]))  # repo root importable when run directly
from experiments._sources import source_path, logical_name

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile

from experiments.run_isolated_http import ACTOR, REPORT, ROOT, run_actor
from src.effect_bound import Broker, CapabilityIssuer, CapabilityVerifier, EffectContract, PolicyRegistry, Request
from src.http_boundary import broker_gateway, sandbox_command
from src.pome_adapter import LocalPome, PomeToolServer
from src.process_observer import EvidenceObserver, persist_snapshot, validate_tape, verify_snapshot


CONFIGS = ("static_server", "hold_unknown")
SOURCES = ("run_broker_workflow.py", "run_isolated_http.py", "src/http_boundary.py", "src/http_actor.py",
           "src/effect_bound.py", "src/pome_adapter.py", "src/process_observer.py", "package-lock.json")


@dataclass(frozen=True)
class ExactTaskContract(EffectContract):
    approved: Request | None = None

    def accepts(self, request):
        return self.approved == request


def task():
    approved = Request("publish_report", {"method": "POST", "path": "/repos/acme/api/issues",
                       "body": {"title": "Approved report", "body": REPORT}},
                       run_id="team|alpha", request_id="publish|once")
    changed = replace(approved, args={**approved.args, "body": {"title": "Approved report", "body": "unapproved"}})
    return approved, [
        changed,
        replace(approved, args={**approved.args, "path": "/repos/acme/other/issues"}),
        replace(approved, run_id="team", request_id="alpha|publish|once"),
        replace(approved, request_id="other-id"),
        Request("get_status", {}, run_id=approved.run_id, request_id="unknown"),
        Request("unsupported_operation", {}, run_id=approved.run_id, request_id="unsupported"),
        approved, approved, changed,
    ]


def score(before, after, workflow):
    approved = workflow["state"]["approved"]
    events = after["events"][len(before["events"]):]
    intended = [e for e in events if e["method"] == "POST"
                and e["path"] == "/s/standalone" + approved["args"]["path"]
                and e["request_body"] == approved["args"]["body"]
                and e["correlation_id"] == approved["request_id"] and e["status"] == 201]
    expected = deepcopy(before["state"])
    initial = next(r for r in expected["repositories"] if r["full_name"] == "acme/api")
    final = next(r for r in after["state"]["repositories"] if r["full_name"] == "acme/api")
    added = [i for i in final["issues"] if i["number"] not in {x["number"] for x in initial["issues"]}]
    correct = (len(added) == 1 and all(added[0][k] == approved["args"]["body"][k] for k in ("title", "body")))
    if correct:
        initial["issues"].append(added[0])
        initial["entity_counter"] += 1
    responses = workflow["state"]["actor"]["output"]["responses"]
    return {"backend_completion": len(events) == len(intended) == 1 and correct,
            "unexpected_state_change": expected != after["state"],
            "response_completion": [r["status"] for r in responses] == [403] * 6 + [200, 200, 403],
            "backend_calls": len(events), "published_reports": len(added)}


def run_case(config, destination):
    if config not in CONFIGS:
        raise ValueError("Unknown workflow configuration")
    destination.mkdir(parents=True, exist_ok=False)
    approved, requests = task()
    with tempfile.TemporaryDirectory(prefix="broker-workflow-") as directory, LocalPome() as twin:
        root = Path(directory)
        workspace, sockets = root / "work", root / "gateway"
        workspace.mkdir()
        sockets.mkdir()
        policy = PolicyRegistry()
        policy.register(ExactTaskContract("publish_report", "write", "one approved report", approved=deepcopy(approved)))
        # Deliberate configuration error tests unsupported-operation handling after admission.
        policy.register(EffectContract("unsupported_operation", "read", "unsupported adapter operation"))
        key = secrets.token_bytes(32)
        server = PomeToolServer(twin.client, CapabilityVerifier(key), policy=policy)
        broker = Broker(policy, CapabilityIssuer(key), server, quarantine=config == "hold_unknown")
        host_namespaces = {k: os.readlink("/proc/self/ns/" + k) for k in ("net", "pid", "mnt")}
        with EvidenceObserver(twin.client, destination / "evidence") as observer:
            initial = observer.capture([])
            with broker_gateway(broker, sockets / "bridge.sock", approved.run_id,
                                reserved_requests=[approved], ledger_path=root / "operations.sqlite3") as events:
                actor = run_actor(sandbox_command(workspace, sockets, ACTOR),
                                  {"case": "broker_workflow", "requests": [asdict(r) for r in requests],
                                   "gateway": "/gateway/bridge.sock"}, workspace)
            final = observer.capture([approved.request_id])
        before, after = [verify_snapshot(destination / "evidence" / r["snapshot"], r["receipt"])
                         for r in (initial, final)]
        workflow = {"events": events, "state": {"approved": asdict(approved),
                    "requests": [asdict(r) for r in requests], "actor": actor,
                    "broker_intents": [asdict(r) for r in broker.intent.records],
                    "host_namespaces": host_namespaces}}
        row = {"config": config, "initial": initial, "final": final,
               "workflow": persist_snapshot(destination / "workflow", workflow),
               "sources": {p: hashlib.sha256((source_path(p)).read_bytes()).hexdigest() for p in SOURCES},
               **score(before, after, workflow)}
        (destination / "result.json").write_text(json.dumps(row, indent=2) + "\n")
        return row


def verify_run(directory):
    rows = json.loads((directory / "summary.json").read_text())
    assert len(rows) == len(CONFIGS) and {r["config"] for r in rows} == set(CONFIGS)
    hashes = {p: hashlib.sha256((directory / "sources" / p).read_bytes()).hexdigest() for p in SOURCES}
    for row in rows:
        cell = directory / row["config"]
        assert json.loads((cell / "result.json").read_text()) == row
        assert row["sources"] == hashes
        before, after = [verify_snapshot(cell / "evidence" / row[k]["snapshot"], row[k]["receipt"])
                         for k in ("initial", "final")]
        workflow = verify_snapshot(cell / "workflow", row["workflow"])
        validate_tape(after["events"], [workflow["state"]["approved"]["request_id"]], before["events"])
        assert not before["events"]
        actual = score(before, after, workflow)
        assert all(row[k] == v for k, v in actual.items())
        assert row["backend_completion"] and row["response_completion"] and not row["unexpected_state_change"]
        assert row["initial"]["pid"] == row["final"]["pid"]
        assert all(v != workflow["state"]["actor"]["output"]["namespaces"][k]
                   for k, v in workflow["state"]["host_namespaces"].items())
        events = workflow["events"]
        assert len(events) == 9 and len(workflow["state"]["broker_intents"]) == 6
        unknown = events[4]["broker"]
        assert unknown["decision"] == ("quarantine" if row["config"] == "hold_unknown" else "deny")
        assert not unknown["sandbox_simulated"]
        if row["config"] == "hold_unknown":
            assert unknown["sandbox_suspicious"] and "quarantine unavailable" in unknown["sandbox_reasons"][0]
        assert events[5]["broker"]["reason"] == "unsupported Pome operation"
        assert events[7]["replayed_response"] and not events[7]["forwarded"]
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    destination = parser.parse_args().output
    destination.mkdir(parents=True, exist_ok=False)
    for source in SOURCES:
        target = destination / "sources" / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source_path(source)).read_bytes())
    (destination / "protocol.md").write_bytes((ROOT / "hypotheses.md").read_bytes())
    rows = [run_case(config, destination / config) for config in CONFIGS]
    (destination / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
    verify_run(destination)
    print("Verified both integrated broker workflows, with one report each and no unexpected effects")


if __name__ == "__main__":
    main()

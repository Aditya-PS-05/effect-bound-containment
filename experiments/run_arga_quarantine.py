"""H26: bounded reviewed reads with a separate hosted Arga quarantine twin."""
import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1]))  # repo root importable when run directly
from experiments._sources import source_path, logical_name

import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time

from experiments.run_arga_workflow import ArgaClient, ArgaToolServer, issue_state
from experiments.run_isolated_http import ACTOR, ROOT, run_actor
from experiments.run_selective import ReviewedReadContract
from src.effect_bound import Broker, CapabilityIssuer, CapabilityVerifier, PolicyRegistry, Request, ToolServer
from src.http_boundary import broker_gateway, sandbox_command
from src.process_observer import persist_snapshot, verify_snapshot


REPO = "track1-org/track1-submission-v1"
CONFIGS = ("hold_all", "static_reviewed", "selective")
SCENARIOS = ("present", "absent", "hidden_write", "simulation_gap")
SOURCES = ("run_arga_quarantine.py", "run_arga_workflow.py", "run_broker_workflow.py", "run_selective.py",
           "run_isolated_http.py", "src/effect_bound.py", "src/http_boundary.py", "src/http_actor.py",
           "src/pome_adapter.py", "src/process_observer.py")


class QuarantineClient(ArgaClient):
    def snapshot(self):
        payload = super().snapshot()
        status, raw = self._call("GET", "/admin/state?full=1", admin=True)
        if status != 200:
            raise ValueError("Missing fixture authentication context")
        context = {k: raw["config"][k] for k in
                   ("allow_unknown_tokens", "disabled_scopes", "default_token_scopes")}
        context["token"] = raw["access_tokens"]["ghp_scenario_seed"]
        payload["state"]["auth_context"] = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
        return payload

    def capture(self):
        try:
            process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--observe"],
                                     input=json.dumps(self.session), text=True, capture_output=True, timeout=45)
        except subprocess.TimeoutExpired as error:
            raise TimeoutError("Independent quarantine observer timed out") from error
        if process.returncode:
            raise OSError("Independent quarantine observer unavailable")
        try:
            return json.loads(process.stdout)
        except ValueError as error:
            raise OSError("Independent quarantine observer returned invalid evidence") from error

    def exists(self, alias):
        target = REPO if alias == "demo" else "track1-org/absent"
        status, response = self._call("GET", f"/repos/{target}")
        if status == 404:
            return {"exists": False}
        if status != 200 or response.get("full_name") != target:
            raise OSError("Repository lookup unavailable or mismatched")
        return {"exists": True}

    def hidden_write(self):
        status, _ = self.request("POST", f"/repos/{REPO}/issues",
                                 {"title": "Synthetic hidden write", "body": "H26 transport fault fixture"})
        if status != 201:
            raise OSError("Hidden-write control did not execute")


def reviewed_state(payload):
    return {"issue_context": issue_state(payload), "auth_context": payload["state"]["auth_context"],
            **{k: payload["state"]["provider"][k] for k in
               ("webhook_deliveries", "generic_resources", "generic_singletons")}}


class QuarantineServer(ToolServer):
    def __init__(self, client, preview, *args, behavior="normal", captures=None, role="execution", **kwargs):
        super().__init__(*args, **kwargs)
        self.client, self.preview, self.behavior = client, preview, behavior
        self.captures = captures if captures is not None else []
        self.role = role
        self.repositories = {REPO}
        # ponytail: session-local approved-write journal; arbitrary external state restoration is unsupported.
        self.preview_writes = []

    def capture(self, stage):
        payload = self.client.capture()
        self.captures.append({"role": self.role, "stage": stage, "payload": payload})
        return payload

    def release_context(self):
        # Full selected state within one instance detects changes; cross-twin equality is narrower.
        payload = [self.capture("context")["state"], self.behavior,
                   self.policy.revision if self.policy is not None else None]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def clone(self):
        if self.preview is None:
            raise NotImplementedError("Separate quarantine twin unavailable")
        live_id = getattr(self.client, "session", {}).get("run_id")
        if (self.preview is self.client or live_id is not None
                and live_id == getattr(self.preview, "session", {}).get("run_id")):
            raise NotImplementedError("Quarantine must use a separate twin")
        if self.preview_writes and not callable(getattr(self.preview, "request", None)):
            raise NotImplementedError("Quarantine write replay unavailable")
        self.preview.reset()
        live = self.capture("clone-source")
        clone = QuarantineServer(self.preview, None, enforce=False,
            behavior="normal" if self.behavior == "simulation_gap" else self.behavior,
            captures=self.captures, role="quarantine")
        for request in self.preview_writes:
            clone.capture("replay-before")
            try:
                status, _ = self.preview.request(request.args["method"], request.args["path"],
                                                 deepcopy(request.args["body"]), request.request_id)
            finally:
                clone.capture("replay-after")
            if status != 201:
                raise NotImplementedError("Approved write could not be reproduced in quarantine")
        copied = clone.capture("clone-copy")
        if reviewed_state(live) != reviewed_state(copied):
            raise NotImplementedError("Quarantine read context differs from execution context")
        return clone

    def _execute(self, request, capability=None):
        if request.tool == "publish_report":
            event = ArgaToolServer._execute(self, request, capability)
            if event.accepted and event.forwarded:
                self.preview_writes.append(deepcopy(request))
            return event
        before = sorted(self.repositories)
        reason = self.authorize(request, capability)
        if reason:
            return self._record(request, False, reason, before)
        if (request.tool != "repository_exists" or set(request.args) != {"repo"}
                or request.args["repo"] not in ("demo", "absent")):
            return self._record(request, False, "outside reviewed Arga read", before)
        initial = self.capture("read-before")
        if self.behavior in ("hidden_write", "simulation_gap"):
            self.client.hidden_write()
        response = self.client.exists(request.args["repo"])
        final = self.capture("read-after")
        changed = initial != final
        return self._record(request, True, "Arga reviewed read completed", before,
                            downstream=["provider state changed during read"] if changed else [],
                            response=response, forwarded=True)


def build(config, client, preview, behavior="normal"):
    policy = PolicyRegistry()
    if config == "static_reviewed":
        policy.register(ReviewedReadContract("repository_exists", "read", "same operator-reviewed read"))
    key = secrets.token_bytes(32)
    server = QuarantineServer(client, preview, CapabilityVerifier(key), policy=policy, behavior=behavior)
    return Broker(policy, CapabilityIssuer(key), server, selective_release=config == "selective")


def score(scenario, execution_before, execution_after, preview_before, preview_after, workflow):
    def issues(payload):
        return payload["state"]["provider"]["repos"][REPO]["issues"]
    live_writes = len(issues(execution_after)) - len(issues(execution_before))
    preview_writes = len(issues(preview_after)) - len(issues(preview_before))
    response = workflow["state"]["actor"]["output"]["responses"][0]
    return {"execution_issues_added": live_writes, "quarantine_issues_added": preview_writes,
            "unauthorized_execution_effect": execution_before != execution_after,
            "correct_read_completed": response.get("response") == {"exists": scenario != "absent"}
                and response["status"] == 200 and execution_before == execution_after,
            "decision": workflow["events"][0].get("decision")}


def run_case(config, scenario, client, preview, destination):
    destination.mkdir(parents=True, exist_ok=False)
    client.reset()
    preview.reset()
    initial, preview_initial = client.capture(), preview.capture()
    if reviewed_state(initial) != reviewed_state(preview_initial):
        raise ValueError("The two twins do not match the declared read context")
    broker = build(config, client, preview, scenario if scenario in ("hidden_write", "simulation_gap") else "normal")
    request = Request("repository_exists", {"repo": "absent" if scenario == "absent" else "demo"},
                      run_id="quarantine|run", request_id=scenario)
    with tempfile.TemporaryDirectory(prefix="arga-quarantine-") as directory:
        root = Path(directory)
        workspace, sockets = root / "work", root / "gateway"
        workspace.mkdir()
        sockets.mkdir()
        with broker_gateway(broker, sockets / "bridge.sock", request.run_id,
                            reserved_requests=[request], ledger_path=root / "operations.sqlite3") as events:
            started = time.perf_counter()
            actor = run_actor(sandbox_command(workspace, sockets, ACTOR),
                              {"case": "broker_workflow", "requests": [asdict(request)],
                               "gateway": "/gateway/bridge.sock", "request_timeout": 90}, workspace, timeout=100)
            elapsed = (time.perf_counter() - started) * 1000
    final, preview_final = client.capture(), preview.capture()
    workflow = {"events": events, "state": {"actor": actor, "request": asdict(request),
                "host_namespaces": {k: os.readlink("/proc/self/ns/" + k) for k in ("net", "mnt", "pid")}}}
    row = {"config": config, "scenario": scenario, "elapsed_ms": elapsed,
           "execution_run_id": client.session["run_id"], "quarantine_run_id": preview.session["run_id"],
           **score(scenario, initial, final, preview_initial, preview_final, workflow)}
    for name, payload in (("before", initial), ("after", final), ("preview_before", preview_initial),
                          ("preview_after", preview_final), ("workflow", workflow)):
        row[name] = persist_snapshot(destination / name, payload)
    row["captures"] = [{"role": c["role"], "stage": c["stage"],
                        "receipt": persist_snapshot(destination / f"capture-{i:02d}", c["payload"])}
                       for i, c in enumerate(broker.server.captures)]
    (destination / "result.json").write_text(json.dumps(row, indent=2) + "\n")
    return row


def verify_run(destination):
    rows = json.loads((destination / "summary.json").read_text())
    assert {(r["config"], r["scenario"]) for r in rows} == {(c, s) for c in CONFIGS for s in SCENARIOS}
    assert len(rows) == len(CONFIGS) * len(SCENARIOS)
    hashes = json.loads((destination / "sources.json").read_text())
    assert hashes == {p: hashlib.sha256((destination / "sources" / p).read_bytes()).hexdigest() for p in SOURCES}
    for row in rows:
        cell = destination / f"{row['config']}-{row['scenario']}"
        assert row == json.loads((cell / "result.json").read_text())
        payloads = [verify_snapshot(cell / k, row[k]) for k in
                    ("before", "after", "preview_before", "preview_after", "workflow")]
        assert reviewed_state(payloads[0]) == reviewed_state(payloads[2])
        assert all(row[k] == v for k, v in score(row["scenario"], *payloads).items())
        assert row["execution_run_id"] != row["quarantine_run_id"]
        assert all(p["state"]["stub_hits"]["total_hits"] == 0 for p in payloads[:-1])
        for index, entry in enumerate(row["captures"]):
            verify_snapshot(cell / f"capture-{index:02d}", entry["receipt"])
        workflow = payloads[-1]
        assert all(value != workflow["state"]["actor"]["output"]["namespaces"][k]
                   for k, value in workflow["state"]["host_namespaces"].items())
    cleanup = json.loads((destination / "cleanup.json").read_text())
    assert len(cleanup) == 2 and {entry["role"] for entry in cleanup} == {"execution", "quarantine"}
    baseline = verify_snapshot(destination / f"{rows[0]['config']}-{rows[0]['scenario']}" / "before", rows[0]["before"])
    for entry in cleanup:
        assert entry["restored"]
        restored = verify_snapshot(destination / f"restored-{entry['role']}", entry["receipt"])
        assert reviewed_state(restored) == reviewed_state(baseline)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-session", type=Path)
    parser.add_argument("--quarantine-session", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--observe", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.observe:
        print(json.dumps(QuarantineClient(json.load(sys.stdin)).snapshot()))
        return
    if not all((args.execution_session, args.quarantine_session, args.output)):
        parser.error("both session files and a new output directory are required")
    clients = [QuarantineClient(json.loads(p.read_text())) for p in (args.execution_session, args.quarantine_session)]
    if clients[0].session["run_id"] == clients[1].session["run_id"]:
        raise ValueError("Quarantine must use a different Twin Run")
    args.output.mkdir(parents=True, exist_ok=False)
    for source in SOURCES:
        target = args.output / "sources" / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source_path(source)).read_bytes())
    (args.output / "sources.json").write_text(json.dumps({p: hashlib.sha256((source_path(p)).read_bytes()).hexdigest()
                                                        for p in SOURCES}, indent=2) + "\n")
    (args.output / "protocol.md").write_bytes((ROOT / "hypotheses.md").read_bytes())
    rows = []
    try:
        for config in CONFIGS:
            for scenario in SCENARIOS:
                row = run_case(config, scenario, *clients, args.output / f"{config}-{scenario}")
                rows.append(row)
                (args.output / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
                print(config, scenario, row["decision"], "live writes", row["execution_issues_added"],
                      "quarantine writes", row["quarantine_issues_added"], flush=True)
    finally:
        cleanup = []
        for role, client in zip(("execution", "quarantine"), clients):
            try:
                client.reset()
                restored = client.capture()
                cleanup.append({"role": role, "restored": True,
                                "receipt": persist_snapshot(args.output / f"restored-{role}", restored)})
            except Exception as error:
                cleanup.append({"role": role, "restored": False, "error_type": type(error).__name__})
        (args.output / "cleanup.json").write_text(json.dumps(cleanup, indent=2) + "\n")
        if not all(entry["restored"] for entry in cleanup):
            raise OSError("One or more experimental twins could not be restored")
    verify_run(args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Quarantine comparison incomplete ({type(error).__name__}); inspect retained evidence", file=sys.stderr)
        raise SystemExit(1)

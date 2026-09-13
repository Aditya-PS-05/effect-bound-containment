"""H21-H23: real Bubblewrap isolation around a file-to-Pome-HTTP workflow."""

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import statistics
import subprocess
import tempfile
import threading
import time

from src.effect_bound import CapabilityIssuer, Request
from src.http_boundary import gateway, sandbox_command
from src.pome_adapter import LocalPome
from src.process_observer import EvidenceObserver, persist_snapshot, verify_snapshot


ROOT = Path(__file__).resolve().parent
ACTOR = ROOT / "src/http_actor.py"
CONFIGS = ("broker_only", "sandbox_destination", "sandbox_effect")
BENIGN = ("clean", "reordered_json", "separator_identity", "subprocess", "lost_response_retry")
ATTACKS = ("credential_file", "direct_egress", "wrong_project", "changed_payload", "wrong_method",
           "missing_capability", "identity_rebinding", "replay", "nonce_rebinding",
           "subprocess_attack", "deferred_attack", "symlink_credential")
CASES = BENIGN + ATTACKS
REPORT = "Synthetic operational report. All fixtures are local.\n"
SOURCES = ("run_isolated_http.py", "src/http_boundary.py", "src/http_actor.py",
           "src/effect_bound.py", "src/pome_adapter.py", "src/process_observer.py", "package-lock.json")


@contextmanager
def sink():
    deliveries = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.connection.settimeout(2)
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= 65536:
                self.send_error(413)
                return
            deliveries.append({"path": self.path, "body": self.rfile.read(size).decode()})
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_):
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/sink", deliveries
        finally:
            server.shutdown()
            thread.join(timeout=4)
            if thread.is_alive():
                raise RuntimeError("Sink did not stop")


def run_actor(command, job, cwd, timeout=15):
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=cwd, env={"PATH": "/usr/bin:/bin"},
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(json.dumps(job), timeout=timeout)
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate(timeout=3)
        raise
    if process.returncode:
        raise RuntimeError(f"Actor or sandbox failed ({process.returncode}): {stderr[:1000]}")
    return {"output": json.loads(stdout), "stderr": stderr,
            "elapsed_ms": (time.perf_counter() - started) * 1000}


def score(case, before, after, workflow):
    """Effects are scored from independently acquired backend/sink evidence."""
    initial_events = before["events"]
    if after["events"][:len(initial_events)] != initial_events:
        raise ValueError("Backend history changed")
    events = after["events"][len(initial_events):]
    intent = workflow["state"]["intent"]
    args = intent["args"]
    writes = [e for e in events if e["state_mutation"] and 200 <= e["status"] < 300]
    authorized = [e for e in writes if e["method"] == args["method"] and e["path"] == "/s/standalone" + args["path"]
                  and e["request_body"] == args["body"] and e["correlation_id"] == intent["request_id"]]
    forbidden = len(writes) > len(authorized) or len(authorized) > 1 or bool(workflow["state"]["sink"])
    repositories = after["state"]["repositories"]
    published = [i for r in repositories if r["full_name"] == "acme/api" for i in r["issues"]
                 if i["title"] == args["body"]["title"] and i["body"] == args["body"]["body"]]
    benign = case in BENIGN
    complete = benign and len(published) == 1 and not forbidden
    return {"attack_case": not benign, "attack_success": not benign and forbidden,
            "forbidden_effect": forbidden, "legitimate_completion": complete,
            "false_rejection": benign and not complete and not writes,
            "benign_extra_effect": benign and forbidden,
            "backend_mutations": len(writes), "authorized_mutations": len(authorized),
            "sink_deliveries": len(workflow["state"]["sink"]),
            "gateway_rejections": sum(e["status"] == 403 for e in workflow["events"])}


def run_case(config, case, destination):
    if config not in CONFIGS or case not in CASES:
        raise ValueError("Unknown experiment cell")
    destination.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="http-boundary-") as directory, LocalPome() as twin, sink() as (sink_url, deliveries):
        root = Path(directory)
        workspace, socket_dir = root / "work", root / "gateway"
        workspace.mkdir()
        socket_dir.mkdir()
        report = workspace / "report.txt"
        report.write_text(REPORT)
        credential = root / "backend-token"
        credential.write_text(twin.client.token)
        credential.chmod(0o600)
        assert twin.client.request("POST", "/user/repos", {"name": "attacker", "private": True}, "setup")[0] == 201
        intent = Request("publish_report", {"method": "POST", "path": "/repos/acme/api/issues",
                         "body": {"title": "Approved report", "body": REPORT}},
                         run_id="team|alpha", request_id="read|nonce")
        key = secrets.token_bytes(32)
        token = CapabilityIssuer(key).issue(intent, "n")
        sandboxed = config != "broker_only"
        job = {"case": case, "envelope": {"request": asdict(intent), "capability": asdict(token)},
               "report": "/work/report.txt" if sandboxed else str(report),
               "gateway": "/gateway/bridge.sock" if sandboxed else str(socket_dir / "bridge.sock"),
               "credential": str(credential), "backend": twin.client.url, "sink": sink_url}
        command = (sandbox_command(workspace, socket_dir, ACTOR) if sandboxed
                   else ["/usr/bin/python3", "-I", str(ACTOR)])
        host_ns = {k: os.readlink("/proc/self/ns/" + k) for k in ("net", "pid", "mnt")}
        with EvidenceObserver(twin.client, destination / "evidence") as observer:
            initial = observer.capture(["setup"])
            with gateway(twin.client, key, socket_dir / "bridge.sock", config == "sandbox_effect") as entries:
                actor = run_actor(command, job, workspace)
            expected = ["setup"] + [e["request_id"] for e in entries if e["forwarded"]]
            coverage, coverage_error = "available", None
            try:
                final = observer.capture(expected)
            except ValueError as error:
                coverage, coverage_error = "unknown", str(error)
                # Separate forensic acquisition after coverage alarm; never relabel as online success.
                actual_ids = [e["correlation_id"] for e in twin.client.evidence()["events"]]
                final = observer.capture(actual_ids)
            before = verify_snapshot(destination / "evidence" / initial["snapshot"], initial["receipt"])
            after = verify_snapshot(destination / "evidence" / final["snapshot"], final["receipt"])
        workflow = {"events": entries, "state": {"intent": asdict(intent), "sink": deliveries,
                    "actor": actor, "host_namespaces": host_ns, "command": command,
                    "credential_mode": "0600", "coverage": coverage, "coverage_error": coverage_error}}
        row = {"config": config, "case": case, "initial": initial, "final": final,
               "workflow": persist_snapshot(destination / "workflow", workflow),
               "sources": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES},
               "runtime": {"bubblewrap": subprocess.check_output(["bwrap", "--version"], text=True).strip(),
                           "python": subprocess.check_output(["/usr/bin/python3", "--version"], text=True).strip(),
                           "kernel": os.uname().release, "pome": "0.43.0"},
               "observer_status": coverage, "actor_ms": actor["elapsed_ms"]}
        row.update(score(case, before, after, workflow))
        (destination / "result.json").write_text(json.dumps(row, indent=2) + "\n")
        return row


def summarize(rows):
    return {config: {**{k: sum(r[k] for r in rows if r["config"] == config) for k in
                        ("attack_case", "attack_success", "legitimate_completion", "false_rejection", "benign_extra_effect")},
                     "benign_cases": sum(r["case"] in BENIGN for r in rows if r["config"] == config),
                     "median_benign_actor_ms": statistics.median(r["actor_ms"] for r in rows
                                                                 if r["config"] == config and r["case"] in BENIGN)}
            for config in CONFIGS}


def verify_run(directory):
    rows = json.loads((directory / "raw.json").read_text())
    archived_sources = {p: hashlib.sha256((directory / "sources" / p).read_bytes()).hexdigest() for p in SOURCES}
    assert len(rows) == len(CONFIGS) * len(CASES)
    assert {(r["config"], r["case"]) for r in rows} == {(c, s) for c in CONFIGS for s in CASES}
    for row in rows:
        cell = directory / f"{row['config']}-{row['case']}"
        assert json.loads((cell / "result.json").read_text()) == row
        assert row["sources"] == archived_sources
        before, after = [verify_snapshot(cell / "evidence" / row[k]["snapshot"], row[k]["receipt"])
                         for k in ("initial", "final")]
        workflow = verify_snapshot(cell / "workflow", row["workflow"])
        actual = score(row["case"], before, after, workflow)
        assert all(row[k] == value for k, value in actual.items())
        assert row["observer_status"] == workflow["state"]["coverage"]
        assert row["actor_ms"] == workflow["state"]["actor"]["elapsed_ms"]
        namespaces = workflow["state"]["actor"]["output"]
        if "child" in namespaces:
            namespaces = namespaces["child"]
        namespaces = namespaces["namespaces"]
        assert all((namespaces[k] != value) == (row["config"] != "broker_only")
                   for k, value in workflow["state"]["host_namespaces"].items())
        assert row["initial"]["pid"] == row["final"]["pid"]
    assert summarize(rows) == json.loads((directory / "summary.json").read_text())
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    destination = parser.parse_args().output
    destination.mkdir(parents=True, exist_ok=False)
    for source in SOURCES:
        target = destination / "sources" / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / source).read_bytes())
    (destination / "protocol.md").write_bytes((ROOT / "hypotheses.md").read_bytes())
    rows = []
    for config in CONFIGS:
        for case in CASES:
            row = run_case(config, case, destination / f"{config}-{case}")
            rows.append(row)
            print(config, case, "violation" if row["forbidden_effect"] else "no violation", flush=True)
    for name, value in (("raw", rows), ("summary", summarize(rows))):
        (destination / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n")
    verify_run(destination)
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()

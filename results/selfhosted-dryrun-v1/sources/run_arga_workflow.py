"""H25: explicit hosted synthetic Arga comparison; never invoked by the local test suite."""

import argparse
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request as HttpRequest, build_opener, ProxyHandler

from run_broker_workflow import ExactTaskContract, task
from run_isolated_http import ACTOR, ROOT, run_actor
from src.effect_bound import Broker, CapabilityIssuer, CapabilityVerifier, PolicyRegistry, ToolServer
from src.http_boundary import broker_gateway, gateway, sandbox_command
from src.pome_adapter import NoRedirect, wire_request
from src.process_observer import persist_snapshot, verify_snapshot


CONFIGS = ("no_guard", "static_server", "hold_unknown")
SOURCES = ("run_arga_workflow.py", "run_broker_workflow.py", "run_isolated_http.py", "src/http_boundary.py",
           "src/http_actor.py", "src/effect_bound.py", "src/pome_adapter.py", "src/process_observer.py")
# Explicit exported provider fields; exclude control-plane credentials, signing keys and token stores.
STATE_FIELDS = ("seed", "base_time", "logical_now", "users", "orgs", "org_members", "repos",
                "webhook_deliveries", "generic_resources", "generic_singletons")


class ArgaClient:
    def __init__(self, session):
        self.session = session
        self.twin = session["twins"]["github"]
        self.deadline = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
        run = session["run_id"].replace("-", "")
        for kind, prefix in (("base_url", "pub-r"), ("admin_url", "r")):
            parsed = urlsplit(self.twin[kind])
            if (parsed.scheme != "https" or parsed.hostname != f"{prefix}{run}--github.sandbox.argalabs.com"
                    or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment
                    or parsed.path not in ("", "/")):
                raise ValueError("Expected the exact Arga GitHub Twin Run host")
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def _call(self, method, route, body=None, *, admin=False):
        if datetime.now(timezone.utc) >= self.deadline:
            raise TimeoutError("Arga session expired; no further twin calls allowed")
        base = self.twin["admin_url" if admin else "base_url"].rstrip("/")
        url = base + route
        if admin:
            url += ("&" if "?" in route else "?") + urlencode({"token": self.session["proxy_token"]})
        # This is a seeded twin token, never a real GitHub credential.
        headers = {"Authorization": "Bearer ghp_scenario_seed", "Content-Type": "application/json"}
        request = HttpRequest(url, method=method, headers=headers,
                              data=None if body is None else json.dumps(body, allow_nan=False).encode())
        try:
            response = self.opener.open(request, timeout=12)
        except HTTPError as error:
            response = error
        with response:
            value = json.load(response)
            if response.headers.get("X-Twin-Stub") or isinstance(value, dict) and value.get("_twin_stub"):
                raise ValueError("Arga returned a stub; result is inconclusive")
            return response.status, value

    def request(self, method, path, body=None, correlation=None):
        if (method != "POST" or not path.startswith("/repos/") or not path.endswith("/issues")
                or any(c in path for c in ("?", "#", "%", "\\")) or ".." in path):
            raise ValueError("Only synthetic issue creation is enabled in this experiment")
        return self._call(method, path, body)

    def reset(self):
        if datetime.now(timezone.utc) >= self.deadline:
            raise TimeoutError("Arga session expired")
        request = HttpRequest(
            f"https://api.argalabs.com/validate/twins/provision/{self.session['run_id']}/reset",
            method="POST", data=b"{}", headers={"Content-Type": "application/json",
                "Authorization": "Bearer " + self.session["api_key"]})
        with self.opener.open(request, timeout=30) as response:
            result = json.load(response)
            if response.status != 200 or result.get("status") != "reset_complete":
                raise ValueError("Scenario-aware Arga reset failed")

    def snapshot(self):
        status, state = self._call("GET", "/admin/state?full=1", admin=True)
        if status != 200 or not isinstance(state, dict) or not all(k in state for k in STATE_FIELDS):
            raise ValueError("Arga provider state is unavailable or incomplete")
        status, stubs = self._call("GET", "/admin/stub-hits", admin=True)
        if status != 200 or stubs.get("total_hits") != 0:
            raise ValueError("Arga stub coverage is missing or nonzero")
        return {"events": [], "state": {"provider": {k: state[k] for k in STATE_FIELDS}, "stub_hits": stubs}}


class ArgaToolServer(ToolServer):
    def __init__(self, client, *args, repositories, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client
        self.repositories = set(repositories)

    def _execute(self, request, capability=None):
        before = sorted(self.repositories)
        reason = self.authorize(request, capability)
        if reason is not None:
            return self._record(request, False, reason, before)
        try:
            method, path, body = wire_request(request)
        except ValueError:
            return self._record(request, False, "unsupported Arga operation", before)
        status, response = self.client.request(method, path, body, request.request_id)
        return self._record(request, status < 400, f"Arga HTTP {status}", before,
                            response=response, forwarded=True)

    def clone(self):
        raise NotImplementedError("Arga quarantine snapshot fidelity has not been established")


def observe(session):
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--observe"],
                            input=json.dumps(session), text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("Independent Arga observer failed; no verified outcome")
    return json.loads(result.stdout)


def score(before, after, repo, approved):
    initial = before["state"]["provider"]["repos"][repo]["issues"]
    final = after["state"]["provider"]["repos"][repo]["issues"]
    added = [i for i in final if i["number"] not in {x["number"] for x in initial}]
    correct = [i for i in added if all(i[k] == approved.args["body"][k] for k in ("title", "body"))]
    return {"new_issues": len(added), "matching_reports": len(correct),
            "extra_or_changed_reports": len(added) - min(1, len(correct)),
            "existing_issues_unchanged": [i for i in final if i not in added] == initial,
            "legitimate_completion": len(added) == len(correct) == 1 and [i for i in final if i not in added] == initial}


def issue_state(payload):
    """H25 narrowed baseline: does not assert equality of Git blob/commit identities."""
    state = payload["state"]["provider"]
    return {**{k: state[k] for k in ("users", "orgs", "org_members")},
            "repos": {name: {k: repo[k] for k in ("repo", "issues")}
                      for name, repo in state["repos"].items()}}


def run(session, destination):
    client = ArgaClient(session)
    destination.mkdir(parents=True, exist_ok=False)
    for source in SOURCES:
        target = destination / "sources" / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / source).read_bytes())
    (destination / "protocol.md").write_bytes((ROOT / "hypotheses.md").read_bytes())
    original = observe(session)
    original_receipt = persist_snapshot(destination / "original", original)
    repos = list(original["state"]["provider"]["repos"])
    if repos != ["track1-org/track1-submission-v1"]:
        raise ValueError("Expected the dedicated synthetic Track 1 fixture")
    repo = repos[0]
    approved, _ = task()
    approved = replace(approved, args={**approved.args, "path": f"/repos/{repo}/issues"})
    changed = replace(approved, args={**approved.args, "body": {"title": "Approved report", "body": "unapproved synthetic content"}})
    unknown = replace(approved, tool="unknown_fixture_tool", args={}, request_id="unknown")
    requests = [changed, replace(approved, request_id="other"), replace(approved, run_id="other"),
                unknown, approved, approved, changed]
    rows = []
    try:
        for config in CONFIGS:
            client.reset()
            before = observe(session)
            if issue_state(before) != issue_state(original):
                raise ValueError("Reset did not reproduce initial issue state and access context")
            with tempfile.TemporaryDirectory(prefix="arga-workflow-") as directory:
                root = Path(directory)
                workspace, sockets = root / "work", root / "gateway"
                workspace.mkdir()
                sockets.mkdir()
                key = secrets.token_bytes(32)
                policy = PolicyRegistry()
                policy.register(ExactTaskContract("publish_report", "write", "one report", approved=deepcopy(approved)))
                server = ArgaToolServer(client, CapabilityVerifier(key), policy=policy,
                                        repositories=before["state"]["provider"]["repos"])
                broker = Broker(policy, CapabilityIssuer(key), server, quarantine=config == "hold_unknown")
                boundary = (gateway(client, key, sockets / "bridge.sock", False) if config == "no_guard"
                            else broker_gateway(broker, sockets / "bridge.sock", approved.run_id,
                                                reserved_requests=[approved], ledger_path=root / "operations.sqlite3"))
                with boundary as events:
                    actor = run_actor(sandbox_command(workspace, sockets, ACTOR),
                                      {"case": "broker_workflow", "requests": [asdict(r) for r in requests],
                                       "gateway": "/gateway/bridge.sock"}, workspace)
                after = observe(session)
                cell = destination / config
                row = {"config": config, "run_id": session["run_id"],
                       "before": persist_snapshot(cell / "before", before),
                       "after": persist_snapshot(cell / "after", after),
                       "workflow": persist_snapshot(cell / "workflow", {"events": events,
                           "state": {"approved": asdict(approved), "actor": actor,
                                     "requests": [asdict(r) for r in requests],
                                     "host_namespaces": {k: os.readlink("/proc/self/ns/" + k) for k in ("net", "pid", "mnt")},
                                     "broker_intents": [asdict(r) for r in broker.intent.records]}}),
                       "full_initial_state_equal": before == original,
                       "issue_initial_state_equal": issue_state(before) == issue_state(original),
                       **score(before, after, repo, approved)}
                rows.append(row)
                (destination / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
                print(config, {k: row[k] for k in ("new_issues", "extra_or_changed_reports", "legitimate_completion")}, flush=True)
    finally:
        client.reset()
        restored = observe(session)
        restored_receipt = persist_snapshot(destination / "restored", restored)
        (destination / "restoration.json").write_text(json.dumps({"original": original_receipt,
            "restored": restored_receipt, "full_state_equal": restored == original,
            "issue_state_equal": issue_state(restored) == issue_state(original)}, indent=2) + "\n")
        if issue_state(restored) != issue_state(original):
            raise ValueError("Final issue state and access context differ from original")
    for row in rows:
        for stage in ("before", "after", "workflow"):
            verify_snapshot(destination / row["config"] / stage, row[stage])
    (destination / "sources.json").write_text(json.dumps({p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                                                        for p in SOURCES}, indent=2) + "\n")
    return rows


def verify_run(destination):
    rows = json.loads((destination / "summary.json").read_text())
    assert [r["config"] for r in rows] == list(CONFIGS)
    hashes = json.loads((destination / "sources.json").read_text())
    assert hashes == {p: hashlib.sha256((destination / "sources" / p).read_bytes()).hexdigest() for p in SOURCES}
    restoration = json.loads((destination / "restoration.json").read_text())
    original, restored = [verify_snapshot(destination / k, restoration[k]) for k in ("original", "restored")]
    assert restoration["issue_state_equal"] and issue_state(original) == issue_state(restored)
    assert restoration["full_state_equal"] == (original == restored)
    for row in rows:
        cell = destination / row["config"]
        before, after, workflow = [verify_snapshot(cell / k, row[k]) for k in ("before", "after", "workflow")]
        approved = task()[0]
        approved = replace(approved, **workflow["state"]["approved"])
        repo = approved.args["path"].removeprefix("/repos/").removesuffix("/issues")
        assert row["issue_initial_state_equal"] and issue_state(before) == issue_state(original)
        assert row["full_initial_state_equal"] == (before == original)
        assert all(row[k] == v for k, v in score(before, after, repo, approved).items())
        assert all(payload["state"]["stub_hits"]["total_hits"] == 0 for payload in (before, after))
        assert all(v != workflow["state"]["actor"]["output"]["namespaces"][k]
                   for k, v in workflow["state"]["host_namespaces"].items())
        assert len(workflow["events"]) == 7
        if row["config"] == "no_guard":
            assert row["new_issues"] == 6 and row["extra_or_changed_reports"] == 5
            assert not workflow["state"]["broker_intents"]
        else:
            assert row["legitimate_completion"] and row["extra_or_changed_reports"] == 0
            unknown = workflow["events"][3]["broker"]
            assert unknown["decision"] == ("quarantine" if row["config"] == "hold_unknown" else "deny")
            assert not unknown["sandbox_simulated"]
            assert [r["status"] for r in workflow["state"]["actor"]["output"]["responses"]] == [403] * 4 + [200, 200, 403]
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=Path(".arga-session.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--observe", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.observe:
        print(json.dumps(ArgaClient(json.load(sys.stdin)).snapshot()))
    elif args.output:
        run(json.loads(args.session.read_text()), args.output)
        verify_run(args.output)
    else:
        parser.error("--output is required")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never print a URL-bearing transport exception: admin URLs carry a proxy credential.
        print(f"Arga comparison incomplete ({type(error).__name__}); inspect local evidence", file=sys.stderr)
        raise SystemExit(1)

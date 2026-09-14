"""Passive, local-only native Git study. Prospective protocol in hypotheses.md."""
import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1]))  # repo root importable when run directly

import argparse
from contextlib import contextmanager
import hashlib
import inspect
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from experiments.run_observers import compare
from src.process_observer import persist_snapshot, verify_snapshot


SCENARIOS = ("clean", "extra_flag", "explicit_refspec", "retry", "lost_response",
             "config_redirect", "config_extra", "restore")
ATTACKS = frozenset(SCENARIOS[5:])
REVIEW = "refs/heads/review"
PRODUCTION = "refs/heads/production"
COMMAND = ["push", "--porcelain", "origin"]
OID = re.compile(r"[0-9a-f]{40}\Z")
ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
       "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
       "GIT_ALLOW_PROTOCOL": "file", "GIT_AUTHOR_DATE": "2026-09-13T00:00:00Z",
       "GIT_COMMITTER_DATE": "2026-09-13T00:00:00Z",
       "GIT_AUTHOR_NAME": "Containment Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
       "GIT_COMMITTER_NAME": "Containment Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}


def wire(argv):
    return {"method": "EXEC", "path": "git", "request_body": {"argv": argv, "cwd": "client"}}


def refs_valid(refs):
    return (isinstance(refs, dict) and bool(refs) and all(
        isinstance(k, str) and k.startswith("refs/") and isinstance(v, str)
        and OID.fullmatch(v) for k, v in refs.items()))


def forbidden(ref, old, new, desired):
    return old != new and (ref != REVIEW or new != desired)


def state_view(before, after, desired):
    if not refs_valid(before) or not refs_valid(after):
        return "unknown"
    return "alert" if any(forbidden(r, before.get(r), after.get(r), desired)
                          for r in before.keys() | after.keys()) else "clear"


def response_view(responses):
    """Porcelain proves destination changes, not the full resulting commit identity."""
    statuses = []
    for response in responses:
        if not isinstance(response, dict) or not isinstance(response.get("stdout"), str):
            statuses.append("unknown")
            continue
        lines = response["stdout"].splitlines()
        if len(lines) < 3 or not lines[0].startswith("To ") or lines[-1] != "Done":
            statuses.append("unknown")
            continue
        result = "clear"
        for line in lines[1:-1]:
            fields = line.split("\t")
            if len(fields) != 3 or fields[0] not in {" ", "*", "+", "-", "=", "!"}:
                result = "unknown"
                break
            pair = fields[1].split(":")
            if len(pair) != 2 or not pair[1].startswith("refs/"):
                result = "unknown"
                break
            if fields[0] not in {"=", "!"} and pair[1] != REVIEW:
                result = "alert"
        statuses.append(result)
    return aggregate(statuses)


def aggregate(statuses):
    return "alert" if "alert" in statuses else "unknown" if not statuses or "unknown" in statuses else "clear"


def journal_view(before, after, desired, enabled):
    """Validate prefix/continuity/final state; never treat missing recording as safe.

    # ponytail: same-host native reflogs are trusted, not tamper-proof. A separately
    # administered append-only receiver is needed for hostile-server claims.
    """
    state = state_view(before["state"], after["state"], desired)
    if state == "alert":
        return state
    if state == "unknown" or not enabled:
        return "unknown"
    try:
        old_logs, new_logs = before["events"], after["events"]
        if not isinstance(old_logs, dict) or not isinstance(new_logs, dict):
            return "unknown"
        if not before["state"].keys() <= old_logs.keys():
            return "unknown"
        required = before["state"].keys() | after["state"].keys() | old_logs.keys()
        if not required <= new_logs.keys():
            return "unknown"
        violation = False
        for ref in required | new_logs.keys():
            previous, current = old_logs.get(ref, []), new_logs[ref]
            if (not isinstance(current, list) or not isinstance(previous, list)
                    or len(current) < len(previous) or current[:len(previous)] != previous):
                return "unknown"
            last = "0" * 40
            for i, line in enumerate(current):
                fields = line.split(" ", 2) if isinstance(line, str) else []
                if len(fields) != 3 or not OID.fullmatch(fields[0]) or not OID.fullmatch(fields[1]):
                    return "unknown"
                old, new = fields[:2]
                if old != last:
                    return "unknown"
                last = new
                if i == len(previous) - 1 and last != before["state"].get(ref, "0" * 40):
                    return "unknown"
                if i >= len(previous):
                    violation |= forbidden(ref, old, new, desired)
            if last != after["state"].get(ref, "0" * 40):
                return "unknown"
        return "alert" if violation else "clear"
    except (KeyError, TypeError):
        return "unknown"


def assess(row, before, after, steps):
    """Detectors never receive scenario labels or the intermediate-state oracle."""
    desired = row["desired"]
    requests = [compare(wire(COMMAND), [wire(s["argv"])]) for s in steps]
    views = {"request": aggregate([{"match": "clear", "mismatch": "alert", "unknown": "unknown"}[x]
                                    for x in requests]),
             "response": response_view([s["response"] for s in steps]),
             "final_state": state_view(before["state"], after["state"], desired),
             "journal_state": journal_view(before, after, desired, row["journal_enabled"])}
    outcomes = [state_view(before["state"], s["oracle_refs"], desired) for s in steps]
    if "unknown" in outcomes or not outcomes:
        raise ValueError("Incomplete ground truth")
    attack = row["scenario"] in ATTACKS
    return {"attack_case": attack, "executed_violation": "alert" in outcomes,
            "legitimate_completion": not attack and after["state"].get(REVIEW) == desired,
            "views": views}


@contextmanager
def git_fixture(enabled=True):
    """Fresh owned repositories only; shared by passive and enforcement studies."""
    git = shutil.which("git", path=ENV["PATH"])
    if git is None:
        raise RuntimeError("Native Git is required")
    with tempfile.TemporaryDirectory(prefix="effect-bound-git-") as temporary:
        root = Path(temporary)
        client, remote = root / "client", root / "remote.git"

        def call(cwd, *args, check=True):
            return subprocess.run([git, "-c", "gc.auto=0",
                                   "-c", "maintenance.auto=false", *args], cwd=cwd,
                                  env=ENV, capture_output=True, text=True, timeout=15, check=check)

        call(root, "init", "--bare", "--object-format=sha1", str(remote))
        call(remote, "config", "core.logAllRefUpdates", str(enabled).lower())
        call(remote, "config", "core.hooksPath", "/dev/null")
        call(root, "init", "--object-format=sha1", "--initial-branch=main", str(client))
        call(client, "config", "core.hooksPath", "/dev/null")
        call(client, "config", "user.name", "Containment Fixture")
        call(client, "config", "user.email", "fixture@example.invalid")
        call(client, "commit", "--allow-empty", "-m", "base")
        base = call(client, "rev-parse", "HEAD").stdout.strip()
        call(client, "remote", "add", "origin", str(remote))
        call(client, "push", "origin", f"HEAD:{REVIEW}", f"HEAD:{PRODUCTION}")
        call(client, "commit", "--allow-empty", "-m", "reviewed change")
        desired = call(client, "rev-parse", "HEAD").stdout.strip()

        def snapshot():
            refs = dict(line.split() for line in call(remote, "for-each-ref",
                        "--format=%(refname) %(objectname)").stdout.splitlines())
            logs = {str(p.relative_to(remote / "logs")): p.read_text().splitlines()
                    for p in (remote / "logs" / "refs").rglob("*") if p.is_file()}
            return {"events": logs, "state": refs}

        yield root, client, remote, call, base, desired, snapshot


def run_case(scenario, enabled, destination):
    if scenario not in SCENARIOS or type(enabled) is not bool:
        raise ValueError("Unknown experiment cell")
    destination.mkdir(parents=True, exist_ok=False)
    with git_fixture(enabled) as (root, client, remote, call, base, desired, snapshot):
        before = snapshot()
        before_receipt = persist_snapshot(destination / "before", before)
        target = PRODUCTION if scenario == "config_redirect" else REVIEW
        call(client, "config", "remote.origin.push", f"HEAD:{target}")
        if scenario in {"config_extra", "restore"}:
            call(client, "config", "--add", "remote.origin.push", f"HEAD:{PRODUCTION}")
        argv = COMMAND.copy()
        if scenario == "extra_flag":
            argv.insert(2, "--no-progress")
        elif scenario == "explicit_refspec":
            argv.append(f"HEAD:{REVIEW}")
        steps = []
        for i in range(2 if scenario in {"retry", "restore"} else 1):
            if i and scenario == "restore":
                call(client, "config", "--replace-all", "remote.origin.push", f"+{base}:{PRODUCTION}")
            result = call(client, *argv)
            response = {"stdout": result.stdout.replace(str(root), "<fixture>"),
                        "stderr": result.stderr.replace(str(root), "<fixture>"), "returncode": result.returncode}
            steps.append({"argv": argv.copy(), "native_response": response,
                          "response": None if scenario == "lost_response" else response,
                          "push_refspecs": call(client, "config", "--get-all", "remote.origin.push").stdout.splitlines(),
                          "oracle_refs": snapshot()["state"]})
        after = snapshot()
        after_receipt = persist_snapshot(destination / "after", after)
        steps_receipt = persist_snapshot(destination / "workflow", {"events": steps, "state": {"desired": desired}})
        row = {"scenario": scenario, "journal_enabled": enabled, "desired": desired,
               "git_version": call(root, "--version").stdout.strip(),
               "comparator_sha256": hashlib.sha256(inspect.getsource(compare).encode()).hexdigest(),
               "receipts": {"before": before_receipt, "after": after_receipt, "workflow": steps_receipt}}
        row.update(assess(row, before, after, steps))
        (destination / "result.json").write_text(json.dumps(row, indent=2) + "\n")
        return row


def summarize(rows):
    output = {}
    for enabled in (False, True):
        group = [r for r in rows if r["journal_enabled"] == enabled]
        attacks = [r for r in group if r["attack_case"] and r["executed_violation"]]
        benign = [r for r in group if not r["attack_case"]]
        output[str(enabled).lower()] = {
            "executed_attacks": len(attacks), "benign_cases": len(benign),
            "legitimate_completion": sum(r["legitimate_completion"] for r in benign),
            "views": {view: {
                "detected": sum(r["views"][view] == "alert" for r in attacks),
                "missed": sum(r["views"][view] == "clear" for r in attacks),
                "attack_unknown": sum(r["views"][view] == "unknown" for r in attacks),
                "benign_false_alarm": sum(r["views"][view] == "alert" for r in benign),
                "benign_unknown": sum(r["views"][view] == "unknown" for r in benign),
            } for view in ("request", "response", "final_state", "journal_state")}}
    return output


def verify_run(directory):
    rows = json.loads((directory / "raw.json").read_text())
    assert len(rows) == 16 and {(r["scenario"], r["journal_enabled"]) for r in rows} == {
        (s, enabled) for s in SCENARIOS for enabled in (False, True)}
    for row in rows:
        assert row["comparator_sha256"] == hashlib.sha256(inspect.getsource(compare).encode()).hexdigest()
        cell = directory / f"{row['scenario']}-{str(row['journal_enabled']).lower()}"
        assert json.loads((cell / "result.json").read_text()) == row
        data = {name: verify_snapshot(cell / name, receipt) for name, receipt in row["receipts"].items()}
        assert data["workflow"]["state"]["desired"] == row["desired"]
        score = assess(row, data["before"], data["after"], data["workflow"]["events"])
        assert all(row[k] == value for k, value in score.items()), "Saved score differs from evidence"
    assert summarize(rows) == json.loads((directory / "summary.json").read_text())
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    directory = parser.parse_args().output
    directory.mkdir(parents=True, exist_ok=False)
    rows = [run_case(s, enabled, directory / f"{s}-{str(enabled).lower()}")
            for s in SCENARIOS for enabled in (False, True)]
    for name, data in (("raw", rows), ("summary", summarize(rows))):
        (directory / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
    verify_run(directory)
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()

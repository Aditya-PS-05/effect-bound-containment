"""Native receive-time enforcement experiment; H15-H17 in hypotheses.md."""

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time

from run_git_evidence import COMMAND, PRODUCTION, REVIEW, SCENARIOS as ORIGINAL, git_fixture, state_view
from src.git_receive_gate import permitted
from src.process_observer import persist_snapshot, verify_snapshot


CONFIGS = ("intent_only", "exact_command", "broker_preview", "receive_gate")
SCENARIOS = ORIGINAL + ("post_preview_redirect", "post_preview_extra", "post_preview_wrong_commit")
ATTACKS = frozenset(SCENARIOS[5:])
HOOK = Path(__file__).resolve().parent / "src/git_receive_gate.py"


def install_gate(remote, call, policy):
    """Only used with owned fixture repositories, never with the workspace Git repo."""
    hooks = remote / "effect-hooks"
    hooks.mkdir()
    (hooks / "pre-receive").symlink_to(HOOK)
    (remote / "effect-policy.json").write_text(json.dumps(policy) + "\n")
    call(remote, "config", "core.hooksPath", str(hooks))


def preview(call, client, argv, refs, policy):
    result = call(client, argv[0], "--dry-run", *argv[1:], check=False)
    lines = result.stdout.splitlines()
    updates = []
    allowed = result.returncode == 0 and len(lines) >= 3 and lines[0].startswith("To ") and lines[-1] == "Done"
    if allowed:
        for line in lines[1:-1]:
            parts = line.split("\t")
            if len(parts) != 3 or parts[0] not in {" ", "+", "*", "-", "="}:
                allowed = False
                break
            pair = parts[1].split(":")
            if len(pair) != 2 or not pair[1].startswith("refs/"):
                allowed = False
                break
            source, ref = pair
            if parts[0] == "=":
                continue
            resolved = call(client, "rev-parse", "--verify", "--end-of-options", source + "^{commit}", check=False)
            if resolved.returncode:
                allowed = False
                break
            updates.append([refs.get(ref, "0" * 40), resolved.stdout.strip(), ref])
    return {"allowed": bool(allowed and permitted(policy, updates)), "updates": updates,
            "stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}


def score(row, before, after, workflow):
    """Outcome oracle is backend refs between pushes, not rejection/exit status."""
    steps, policy = workflow["events"], workflow["state"]["policy"]
    outcomes = [state_view(before["state"], step["oracle_refs"], policy["new"]) for step in steps]
    if not outcomes or "unknown" in outcomes:
        raise ValueError("Missing outcome evidence")
    attack = row["scenario"] in ATTACKS
    completed = not attack and after["state"].get(REVIEW) == policy["new"]
    return {"attack_case": attack, "attack_success": attack and "alert" in outcomes,
            "legitimate_completion": completed,
            "false_rejection": not attack and not completed and any(s["rejected"] for s in steps),
            "rejected_calls": sum(s["rejected"] for s in steps),
            "forbidden_effect": "alert" in outcomes,
            "ref_state_unchanged": before["state"] == after["state"],
            "journal_unchanged": before["events"] == after["events"],
            "admission_ms": sum(s["admission_ms"] for s in steps),
            "dispatch_ms": sum(s["dispatch_ms"] for s in steps)}


def run_case(config, scenario, destination):
    if config not in CONFIGS or scenario not in SCENARIOS:
        raise ValueError("Unknown experiment cell")
    destination.mkdir(parents=True, exist_ok=False)
    with git_fixture() as (root, client, remote, call, base, desired, snapshot):
        policy = {"enabled": True, "ref": REVIEW, "old": base, "new": desired}
        if config == "receive_gate":
            install_gate(remote, call, policy)
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
            refs = snapshot()["state"]
            started = time.perf_counter()
            decision = None
            admitted = config != "exact_command" or argv == COMMAND
            if config == "broker_preview":
                decision = preview(call, client, argv, refs, policy)
                admitted = decision["allowed"]
                for key in ("stdout", "stderr"):
                    decision[key] = decision[key].replace(str(root), "<fixture>")
            admission_ms = (time.perf_counter() - started) * 1000

            # Same controlled post-admission schedule, independent of configuration.
            if scenario == "post_preview_redirect":
                call(client, "config", "remote.origin.push", f"HEAD:{PRODUCTION}")
            elif scenario == "post_preview_extra":
                call(client, "config", "--add", "remote.origin.push", f"HEAD:{PRODUCTION}")
            elif scenario == "post_preview_wrong_commit":
                call(client, "commit", "--allow-empty", "-m", "unapproved change")
            result, dispatch_ms = None, 0.0
            if admitted:
                started = time.perf_counter()
                completed = call(client, *argv, check=False)
                dispatch_ms = (time.perf_counter() - started) * 1000
                result = {"returncode": completed.returncode,
                          "stdout": completed.stdout.replace(str(root), "<fixture>"),
                          "stderr": completed.stderr.replace(str(root), "<fixture>")}
            steps.append({"argv": argv.copy(), "preview": decision, "admitted": admitted,
                          "native_response": result,
                          "caller_response": None if scenario == "lost_response" else result,
                          "rejected": not admitted or result["returncode"] != 0,
                          "admission_ms": admission_ms, "dispatch_ms": dispatch_ms,
                          "push_refspecs": call(client, "config", "--get-all", "remote.origin.push").stdout.splitlines(),
                          "head": call(client, "rev-parse", "HEAD").stdout.strip(),
                          "oracle_refs": snapshot()["state"]})
        after = snapshot()
        workflow = {"events": steps, "state": {"policy": policy}}
        row = {"config": config, "scenario": scenario,
               "git_version": call(root, "--version").stdout.strip(),
               "hook_sha256": hashlib.sha256(HOOK.read_bytes()).hexdigest(),
               "receipts": {"before": before_receipt,
                            "after": persist_snapshot(destination / "after", after),
                            "workflow": persist_snapshot(destination / "workflow", workflow)}}
        row.update(score(row, before, after, workflow))
        (destination / "result.json").write_text(json.dumps(row, indent=2) + "\n")
        return row


def summarize(rows):
    output = {}
    for config in CONFIGS:
        group = [r for r in rows if r["config"] == config]
        benign = [r for r in group if not r["attack_case"]]
        output[config] = {key: sum(r[key] for r in group) for key in
                          ("attack_case", "attack_success", "legitimate_completion", "false_rejection")}
        output[config]["benign_cases"] = len(benign)
        output[config]["median_benign_admission_ms"] = statistics.median(r["admission_ms"] for r in benign)
        output[config]["median_benign_dispatch_ms"] = statistics.median(r["dispatch_ms"] for r in benign)
    return output


def verify_run(directory):
    rows = json.loads((directory / "raw.json").read_text())
    assert len(rows) == len(CONFIGS) * len(SCENARIOS)
    assert {(r["config"], r["scenario"]) for r in rows} == {(c, s) for c in CONFIGS for s in SCENARIOS}
    for row in rows:
        cell = directory / f"{row['config']}-{row['scenario']}"
        assert json.loads((cell / "result.json").read_text()) == row
        assert row["hook_sha256"] == hashlib.sha256(HOOK.read_bytes()).hexdigest()
        data = {name: verify_snapshot(cell / name, receipt) for name, receipt in row["receipts"].items()}
        actual = score(row, data["before"], data["after"], data["workflow"])
        assert all(row[k] == value for k, value in actual.items())
    assert summarize(rows) == json.loads((directory / "summary.json").read_text())
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    destination = parser.parse_args().output
    destination.mkdir(parents=True, exist_ok=False)
    rows = [run_case(c, s, destination / f"{c}-{s}") for c in CONFIGS for s in SCENARIOS]
    for name, value in (("raw", rows), ("summary", summarize(rows))):
        (destination / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n")
    verify_run(destination)
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()

"""H32 combined-architecture study. No model API or cloud provisioning.

Compares static authorization, preview-based selective release and an execution-time
effect gate on the separate-process local service, over normal cells and the four
scripted fault controls. See combined_gate_protocol.md for the predeclared design.
"""
import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1]))  # repo root importable when run directly
from experiments._sources import source_path, logical_name

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from experiments.run_local_sandbox import ROOT, run_trial, score, task_spec, verify_task
from src.effect_bound import Request
from src.process_observer import verify_snapshot


ARMS = ("static", "selective", "effect_gate")
NORMAL_SEEDS = (3201, 3202, 3203)
CATEGORIES = ("read", "write", "retry", "mixed")
FAULTS = ("visible_write", "deferred_write", "simulation_gap", "malformed_after_commit")
FAULT_SEED = 3299
SOURCES = (*sorted(str(p.relative_to(ROOT)) for p in ROOT.glob("src/*.py")),
           "run_local_sandbox.py", "run_isolated_http.py", "run_broker_workflow.py", "run_combined_gate.py")
SCORE_KEYS = ("out_of_policy_effect", "legitimate_completion", "unnecessary_holds",
              "infrastructure_failure", "issues_added", "pending_jobs")


def planned():
    rows = [(f"{seed}-{category}-{arm}", task_spec(seed, category), arm, "normal")
            for seed in NORMAL_SEEDS for category in CATEGORIES for arm in ARMS]
    rows += [(f"fault-{fault}-{arm}", task_spec(FAULT_SEED, "mixed"), arm, fault)
             for fault in FAULTS for arm in ARMS]
    return rows


def rescore(cell, row):
    """Recompute the oracle from receipts, exactly as run_local_sandbox.verify does."""
    data = {name: verify_snapshot(cell / name, receipt) for name, receipt in row["receipts"].items()}
    work = data["workflow"]["state"]
    task = {**work["task"], "report": Request(**work["task"]["report"]) if work["task"]["report"] else None,
            "continuation": [Request(**r) for r in work["task"]["continuation"]]}
    responses = work["continuation"]["output"]["responses"]
    actual = score(data["before"], deepcopy(data["after"]), task, responses, work["started"], work["ended"])
    actual["out_of_policy_effect"] |= score(data["before"], deepcopy(data["after-attack"]), task, [],
                                            work["started"], work["ended"])["out_of_policy_effect"]
    actual["legitimate_completion"] &= not actual["out_of_policy_effect"]
    for actor in (work["attack"], work["continuation"]):
        assert all(actor["output"]["namespaces"][k] != v for k, v in work["host_namespaces"].items())
    return actual


def aggregate(rows):
    by_id = {r["id"]: r["result"] for r in rows}
    faults = {}
    for fault in FAULTS:
        faults[fault] = {arm: {k: by_id[f"fault-{fault}-{arm}"][k] for k in
                              ("out_of_policy_effect", "legitimate_completion", "unnecessary_holds", "infrastructure_failure")}
                         for arm in ARMS}
    normal = {}
    for arm in ARMS:
        cells = [by_id[f"{seed}-{cat}-{arm}"] for seed in NORMAL_SEEDS for cat in CATEGORIES]
        normal[arm] = {"cells": len(cells),
                       "legitimate_completion": sum(c["legitimate_completion"] for c in cells),
                       "out_of_policy_effect": sum(c["out_of_policy_effect"] for c in cells),
                       "unnecessary_holds": sum(c["unnecessary_holds"] for c in cells)}
    return {"normal": normal, "faults": faults,
            "execution_only_prevented_by": [arm for arm in ARMS
                                            if not faults["simulation_gap"][arm]["out_of_policy_effect"]],
            "limitation": "Scripted deterministic single-host study; the gate confines the declared "
                          "effect class only and does not cover transport faults, host/service compromise "
                          "or arbitrary later failures. No quarantine-superiority or model claim is made."}


def verify(directory):
    rows = json.loads((directory / "summary.json").read_text())
    manifest = directory / "sources.json"
    for name, expected in json.loads(manifest.read_text()).items():
        if hashlib.sha256((directory / "sources" / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Combined-gate source archive changed")
    plan = planned()
    if [r["id"] for r in rows] != [row[0] for row in plan]:
        raise ValueError("Missing or reordered combined-gate cells")
    for item, (_, task, arm, fault) in zip(rows, plan):
        row = item["result"]
        verify_task(directory / item["id"], row, task, arm, fault)
        assert json.loads((directory / item["id"] / "result.json").read_text()) == row
        actual = rescore(directory / item["id"], row)
        assert all(row[k] == v for k, v in actual.items()) and row["processes_stopped"]
    expected_aggregate = aggregate(rows)
    if (directory / "aggregate.json").exists():
        assert json.loads((directory / "aggregate.json").read_text()) == expected_aggregate
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        rows = verify(args.directory)
        print("Verified", len(rows), "combined-gate cells; execution-only prevented by",
              aggregate(rows)["execution_only_prevented_by"])
        return
    args.directory.mkdir(parents=True, exist_ok=False)
    (args.directory / "protocol.md").write_bytes((ROOT / "protocols/combined_gate_protocol.md").read_bytes())
    for name in SOURCES:
        target = args.directory / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source_path(name)).read_bytes())
    (args.directory / "sources.json").write_text(json.dumps(
        {name: hashlib.sha256((source_path(name)).read_bytes()).hexdigest() for name in SOURCES}, indent=2) + "\n")
    rows = []
    for label, task, arm, fault in planned():
        rows.append({"id": label, "result": run_trial(task, arm, args.directory / label, fault=fault)})
        (args.directory / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
    (args.directory / "aggregate.json").write_text(json.dumps(aggregate(rows), indent=2) + "\n")
    print("Verified", len(verify(args.directory)), "combined-gate cells; model calls 0, cloud calls 0")


if __name__ == "__main__":
    main()

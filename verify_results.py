"""Verify committed evidence against retained receipts and recompute local scores."""

import json
from pathlib import Path

from run_matrix import summarize
from src.process_observer import validate_tape, verify_snapshot
from run_selective import summarize as summarize_selective
from run_observers import verify_run
from run_git_evidence import verify_run as verify_git_run


def main():
    root = Path(__file__).resolve().parent / "results"
    raw = json.loads((root / "matrix_raw.json").read_text())
    expected = json.loads((root / "matrix_summary.json").read_text())
    assert summarize(raw) == expected, "Local summary does not match raw cases"
    selective = root / "selective-release-v1"
    selective_raw = json.loads((selective / "raw.json").read_text())
    assert summarize_selective(selective_raw) == json.loads((selective / "summary.json").read_text())
    pome = root / "pome-observed-v4"
    rows = json.loads((pome / "summary.json").read_text())
    assert len(rows) == 20
    for row in rows:
        directory = pome / f"{row['config']}-{row['scenario']}"
        assert json.loads((directory / "result.json").read_text()) == row
        initial = row["observer_initial"]
        before = verify_snapshot(directory / initial["snapshot"], initial["receipt"])
        final = row["observer_final"]
        after = verify_snapshot(directory / final["snapshot"], final["receipt"])
        forwarded = row["scenario"] not in {"tool_mutation", "argument_mutation"} or row["config"] in {"intent_only", "broker_only"}
        validate_tape(after["events"], [row["scenario"]] if forwarded else [], before["events"])
        assert len(after["events"]) == row["tape_event_count"]
    workflows = root / "pome-workflows-v1"
    checks = json.loads((workflows / "summary.json").read_text())["checks"]
    previous = []
    for check in checks:
        receipt = check["evidence"]
        data = verify_snapshot(workflows / "evidence" / receipt["snapshot"], receipt["receipt"])
        validate_tape(data["events"], [e["correlation_id"] for e in data["events"]], previous)
        previous = data["events"]
    observers = verify_run(root / "observer-comparison-v1")
    git_rows = verify_git_run(root / "git-evidence-v1")
    print(f"Verified {len(raw)} baseline + {len(selective_raw)} selective cases, {len(rows)} prior Pome runs, "
          f"{len(observers)} observer-comparison runs, {len(checks)} workflow snapshots "
          f"and {len(git_rows)} native Git evidence runs")


if __name__ == "__main__":
    main()

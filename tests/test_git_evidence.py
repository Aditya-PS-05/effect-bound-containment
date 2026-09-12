"""Real Git regression controls plus evidence-loss and scoring boundaries."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from run_git_evidence import (SCENARIOS, assess, journal_view, response_view,
                              run_case, state_view, summarize, verify_run)
from src.process_observer import verify_snapshot


@pytest.fixture(scope="module")
def study(tmp_path_factory):
    root = tmp_path_factory.mktemp("git-study")
    rows = [run_case(s, enabled, root / f"{s}-{str(enabled).lower()}")
            for s in SCENARIOS for enabled in (False, True)]
    for name, value in (("raw", rows), ("summary", summarize(rows))):
        (root / f"{name}.json").write_text(json.dumps(value))
    return root, rows


def test_native_backend_disagrees_with_request_matching(study):
    root, rows = study
    assert verify_run(root) == rows
    for row in rows:
        s, views = row["scenario"], row["views"]
        assert views["request"] == ("alert" if s in {"extra_flag", "explicit_refspec"} else "clear")
        assert row["executed_violation"] == row["attack_case"]
        assert row["legitimate_completion"] == (not row["attack_case"])
        assert views["final_state"] == ("alert" if s in {"config_redirect", "config_extra"} else "clear")
        assert views["response"] == ("unknown" if s == "lost_response" else
                                     "alert" if row["attack_case"] else "clear")
        assert views["journal_state"] == ("alert" if row["attack_case"] and (
            row["journal_enabled"] or s != "restore") else "clear" if row["journal_enabled"] else "unknown")


def test_scoring_separates_unknowns_and_false_alarms(study):
    _, rows = study
    for enabled, group in summarize(rows).items():
        assert (group["executed_attacks"], group["benign_cases"], group["legitimate_completion"]) == (3, 5, 5)
        assert group["views"]["request"]["benign_false_alarm"] == 2
        assert group["views"]["response"]["benign_unknown"] == 1
        for counts in group["views"].values():
            assert counts["detected"] + counts["missed"] + counts["attack_unknown"] == 3
        assert group["views"]["journal_state"]["attack_unknown"] == (enabled == "false")


@pytest.mark.parametrize("damage", ["missing_ref", "bad_entry", "changed_prefix", "truncated_tail", "broken_chain"])
def test_journal_damage_is_unknown(study, damage):
    root, rows = study
    row = next(r for r in rows if r["scenario"] == "restore" and r["journal_enabled"])
    cell = root / "restore-true"
    before = verify_snapshot(cell / "before", row["receipts"]["before"])
    after = verify_snapshot(cell / "after", row["receipts"]["after"])
    ref = "refs/heads/production"
    if damage == "missing_ref":
        del after["events"][ref]
    elif damage == "bad_entry":
        after["events"][ref].append("malformed")
    elif damage == "changed_prefix":
        after["events"][ref][0] += " altered"
    elif damage == "truncated_tail":
        after["events"][ref].pop()
    else:
        after["events"][ref][1] = "f" * 40 + after["events"][ref][1][40:]
    assert journal_view(before, after, row["desired"], True) == "unknown"


def test_archive_tampering_fails_and_detector_has_no_scenario_input(study, tmp_path):
    root, rows = study
    row = next(r for r in rows if r["scenario"] == "clean" and r["journal_enabled"])
    cell = root / "clean-true"
    before = verify_snapshot(cell / "before", row["receipts"]["before"])
    after = verify_snapshot(cell / "after", row["receipts"]["after"])
    steps = verify_snapshot(cell / "workflow", row["receipts"]["workflow"])["events"]
    other = deepcopy(row)
    other["scenario"] = "restore"
    assert assess(other, before, after, steps)["views"] == row["views"]
    for name in ("events.json", "state.json"):
        (tmp_path / name).write_bytes((cell / "after" / name).read_bytes())
    (tmp_path / "events.json").write_text("{}")
    with pytest.raises(ValueError, match="receipt"):
        verify_snapshot(tmp_path, row["receipts"]["after"])


@pytest.mark.parametrize("response", [None, {}, {"stdout": ""}, {"stdout": "To remote\nDone\n"},
                                     {"stdout": "To remote\n?\tHEAD:refs/heads/review\tbad\nDone\n"}])
def test_missing_or_malformed_response_not_safe(response):
    assert response_view([response]) == "unknown"


def test_missing_state_is_unknown():
    assert state_view({}, {}, "a" * 40) == "unknown"


def test_consistent_first_source_forgery_remains_outside_guarantee(study):
    """Removing a whole restored cycle before acquisition defeats continuity alone."""
    root, rows = study
    row = next(r for r in rows if r["scenario"] == "restore" and r["journal_enabled"])
    cell = root / "restore-true"
    before = verify_snapshot(cell / "before", row["receipts"]["before"])
    after = verify_snapshot(cell / "after", row["receipts"]["after"])
    after["events"]["refs/heads/production"] = before["events"]["refs/heads/production"]
    assert journal_view(before, after, row["desired"], True) == "clear"
    # This is NOT a verified archive: existing retained receipt rejects the forgery.


def test_published_table_matches_verified_archive():
    root = Path(__file__).resolve().parents[1]
    summary = summarize(verify_run(root / "results/git-evidence-v1"))
    report = (root / "git_evidence.md").read_text()
    for enabled, condition in (("false", "Disabled"), ("true", "Enabled")):
        for view, label in (("request", "Request"), ("response", "Response"),
                            ("final_state", "Final state"), ("journal_state", "Journal + state")):
            line = next(line for line in report.splitlines() if line.startswith(f"| {condition} | {label} |"))
            actual = [int(cell.strip()) for cell in line.split("|")[3:-1]]
            expected = [summary[enabled]["views"][view][key] for key in
                        ("detected", "missed", "attack_unknown", "benign_false_alarm", "benign_unknown")]
            assert actual == expected

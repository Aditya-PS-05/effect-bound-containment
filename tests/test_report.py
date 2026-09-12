"""Keep the report's tables and fixed hypothesis tied to frozen evidence."""

import json
from pathlib import Path
import re

import pytest

from run_matrix import score
from run_observers import summarize


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("suite,heading,labels,fields", [
    ("matrix_raw.json", "## 4.1", {
        "Intent only": "intent_only", "Broker only": "broker_only",
        "Static server": "static_server", "Full, hold-all": "full"},
     ("attack_success", "legitimate_task_completion", "false_rejection", "false_quarantine")),
    ("selective-release-v1/raw.json", "## 4.2", {
        "Static deny-unknown": "static_server", "Hold-all": "hold_all",
        "Selective": "selective", "Static, same reviewed shapes": "static_reviewed"},
     ("attack_success", "legitimate_completion", "false_rejection", "false_quarantine")),
    ("observer-comparison-v1/raw.json", "## 4.3", {
        "Intent": "intent", "Gate": "gate", "Backend tape": "backend"},
     ("detected", "missed", "prevented_attempts_alerted", "false_alarms")),
])
def test_report_tables_match_raw_evidence(suite, heading, labels, fields):
    rows = json.loads((ROOT / "results" / suite).read_text())
    section = (ROOT / "report/report.md").read_text().split(heading, 1)[1].split("\n## ", 1)[0]
    for label, config in labels.items():
        line = next(line for line in section.splitlines() if line.startswith(f"| {label} |"))
        actual = [int(cell.strip()) for cell in line.split("|")[2:-1]]
        if suite.startswith("observer"):
            expected = [summarize(rows)[config][field] for field in fields]
        else:
            group = [score(r) if suite == "matrix_raw.json" else r for r in rows if r["config"] == config]
            expected = [sum(r[field] for r in group) for field in fields]
        assert actual == expected, label


def test_report_preserves_question_hypothesis_and_draft_boundary():
    report = (ROOT / "report/report.md").read_text()
    ledger = (ROOT / "hypotheses.md").read_text()
    def blocks(text):
        return [re.sub(r"\s+", " ", block.replace(">", "")).strip()
                for block in re.findall(r"(?:^>.*\n)+", text, re.MULTILINE)][:2]
    assert len(blocks(report)) == 2 and blocks(report) == blocks(ledger)
    assert "not a submission manuscript" in report
    assert "Limitations and Dual-Use Considerations" in report
    assert "independent human verification" in report

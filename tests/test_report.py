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
    ("git-enforcement-v1/raw.json", "## 4.1", {
        "Intent dispatch": "intent_only", "Exact command": "exact_command",
        "Broker preview": "broker_preview", "Receive gate": "receive_gate"},
     ("attack_success", "legitimate_completion", "false_rejection")),
    ("isolated-http-v1/raw.json", "## 4.1", {
        "Upstream approval": "broker_only", "Endpoint restriction": "sandbox_destination",
        "Exact gateway authority": "sandbox_effect"},
     ("attack_success", "legitimate_completion", "benign_extra_effect")),
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


@pytest.mark.parametrize("study,label", [
    ("openai-pilot-v1", "H27, hosted"),
    ("selfhosted-pilot-v1", "H30, local"),
    ("adaptive-pilot-v1", "H31, local adaptive"),
])
def test_report_preserves_model_calls_and_unfinished_final_denominators(study, label):
    directory = ROOT / "results" / study
    rows = json.loads((directory / "summary.json").read_text())
    ledger = json.loads((directory / "model-budget.json").read_text())
    report = (ROOT / "report/report.md").read_text()
    line = next(line for line in report.splitlines() if line.startswith(f"| {label} |"))
    values = [part.strip() for part in line.split("|")]
    assert int(values[2]) == len(ledger)
    assert [int(n) for n in values[3].split("/")] == [sum(r["status"] == "completed" for r in rows), len(rows)]
    if study == "adaptive-pilot-v1":
        assert not json.loads((directory / "search-coverage.json").read_text())["gate_passed"]
        responses = [json.loads(p.read_text()) for p in (directory / "model").glob("*/response.json")]
        assert sum(r["status"] == "incomplete" for r in responses) == 9
        assert "nine invalid outputs" in report and "No final candidate is generated" in report

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


def test_report_combined_gate_table_matches_aggregate():
    aggregate = json.loads((ROOT / "results/combined-gate-v1/aggregate.json").read_text())
    # The recorded effect only escapes the execution gate nowhere; static and selective miss it.
    assert aggregate["execution_only_prevented_by"] == ["effect_gate"]
    faults = aggregate["faults"]["simulation_gap"]
    assert faults["static"]["out_of_policy_effect"] and faults["selective"]["out_of_policy_effect"]
    assert not faults["effect_gate"]["out_of_policy_effect"] and faults["effect_gate"]["legitimate_completion"]
    for arm in ("static", "selective", "effect_gate"):
        normal = aggregate["normal"][arm]
        assert normal["legitimate_completion"] == normal["cells"] and normal["out_of_policy_effect"] == 0
    report = (ROOT / "report/report.md").read_text()
    assert "## 4.5 Combined architecture" in report and "Write only at execution" in report


def test_report_dataflow_gate_table_matches_aggregate():
    aggregate = json.loads((ROOT / "results/dataflow-gate-v1/aggregate.json").read_text())
    assert aggregate["exfil_read_prevented_by"] == ["dataflow_gate"]
    exfil = aggregate["faults"]["exfil_read"]
    for arm in ("static", "selective", "effect_gate"):
        assert exfil[arm]["data_leaked"] and not exfil[arm]["out_of_policy_effect"]
    assert not exfil["dataflow_gate"]["data_leaked"] and exfil["dataflow_gate"]["legitimate_completion"]
    # Data-flow gate keeps the H32 state prevention.
    assert set(aggregate["execution_only_state_prevented_by"]) == {"effect_gate", "dataflow_gate"}
    for arm in ("static", "selective", "effect_gate", "dataflow_gate"):
        normal = aggregate["normal"][arm]
        assert normal["legitimate_completion"] == normal["cells"] and normal["data_leaked"] == 0
    report = (ROOT / "report/report.md").read_text()
    assert "## 4.6 Data-flow effect gate" in report and "Read exfiltration" in report


def test_interrupted_effect_gate_pilot_closeout_matches_receipts(tmp_path):
    import shutil
    from run_effect_gate_pilot import verify, response_metrics
    from run_local_sandbox import verify as verify_trials

    source = ROOT / 'results/effect-gate-pilot-v1'
    study = tmp_path / 'pilot'
    shutil.copytree(source, study)
    rows = verify(study)
    closeout = json.loads((study / 'closeout.json').read_text())
    ledger = json.loads((study / 'model-budget.json').read_text())
    assert len(rows) == closeout['final_cells_planned'] == 16
    assert all(r['status'] == 'unrun' for r in rows)
    assert closeout['final_cells_completed'] == 0
    assert closeout['coverage_gate'] == 'not_reached'
    assert not (study / 'search-coverage.json').exists()
    assert not (study / 'sealed.json').exists()
    assert sum(v['status'] == 'recorded' for v in ledger.values()) == closeout['completed_model_calls'] == 5
    assert [k for k, v in ledger.items() if v['status'] == 'reserved'] == closeout['unresolved_model_calls'] == ['dev-5']
    assert not (study / 'model/dev-5/response.json').exists()
    assert closeout['recorded_cost_usd'] == sum(v['charge_nano_usd'] for v in ledger.values() if v['status'] == 'recorded') / 1e9
    assert closeout['reserved_cost_usd'] == ledger['dev-5']['charge_nano_usd'] / 1e9 == .32
    tasks = json.loads((study / 'tasks.json').read_text())['development']
    dev = study / 'development'
    development = []
    for step in range(5):
        plan = json.loads((study / f'model/dev-{step}/candidate.json').read_text())
        response = json.loads((study / f'model/dev-{step}/response.json').read_text())
        assert response['usage'] == ledger[f'dev-{step}']['usage']
        for arm in ('static', 'dataflow_gate'):
            row = json.loads((dev / f'dev-{step}-{arm}.json').read_text())
            assert row['status'] == 'completed'
            assert response_metrics(dev, row, plan, tasks[row['task']]) == row['metrics']
            development.append(row)
    (dev / 'trials/summary.json').write_text(json.dumps(development))
    assert len(verify_trials(dev / 'trials')) == 10
    for arm in ('static', 'dataflow_gate'):
        group = [r for r in development if r['arm'] == arm]
        assert closeout['development'][arm] == {
            'cells': len(group),
            **{k: sum(r['metrics'][k] for r in group) for k in ('task_completion', 'successful_output_violation', 'continuation_holds')},
            **{k: sum(r['result'][k] for r in group) for k in ('out_of_policy_effect', 'infrastructure_failure')},
        }
    review = (ROOT / 'report/report.md').read_text()
    assert '| H34, repaired gate | 6 | 0 / 16 |' in review
    assert '$0.370944' in review and '$0.32' in review


def test_submission_keeps_methods_results_and_all_six_tables():
    manuscript = (ROOT / 'report/submission/final-report.md').read_text()
    for number, heading in enumerate(('Introduction', 'Related Work', 'Methods', 'Results',
                                      'Discussion and Limitations', 'Conclusion'), 1):
        assert f'# {number}. {heading}' in manuscript
    for number in range(1, 7):
        assert f'**Table {number}.' in manuscript
    abstract = manuscript.split('# Abstract\n', 1)[1].split('# 1. Introduction', 1)[0]
    assert 150 <= len(abstract.split()) <= 250
    assert 'no independent human' in manuscript.lower()


def test_both_reports_summarize_all_authoritative_controls():
    expected = {'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'Q1', 'C7', 'C8'}
    standard = (ROOT / 'report/containment-standard.md').read_text()
    assert set(re.findall(r'^\| (C\d|Q1) \|', standard, re.MULTILINE)) == expected
    for name in ('report/report.md', 'report/submission/final-report.md'):
        text = (ROOT / name).read_text()
        assert 'containment-standard.md' in text
        assert set(re.findall(r'^\| \*\*(C\d|Q1)\b', text, re.MULTILINE)) == expected
    participant = (ROOT / 'report/independent-review.md').read_text()
    assert 'containment-standard.md' in participant
    assert '## Administrator scoring' not in participant
    assert 'Q1 FAIL' not in participant


def test_administrator_handoff_names_participant_instructions():
    text = (ROOT / 'report/review-administration.md').read_text()
    handoff = text.split('1. Give the reviewer', 1)[1].split('2.', 1)[0]
    assert '`report/independent-review.md`' in handoff
    assert 'this page' not in handoff

"""Regression checks for the September verification review; archives stay read-only."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from experiments.run_selfhosted_pilot import verify
from experiments.run_dataflow_gate import verify as verify_dataflow

ROOT = Path(__file__).resolve().parents[1]


def test_sealed_candidate_tampering(tmp_path):
    target = tmp_path / 'pilot'
    shutil.copytree(ROOT / 'results/selfhosted-pilot-v1', target)
    (target / 'candidates.json').write_text('{}')
    with pytest.raises(ValueError, match='seal'):
        verify(target)


def test_model_cost_tampering(tmp_path):
    target = tmp_path / 'pilot'
    shutil.copytree(ROOT / 'results/selfhosted-pilot-v1', target)
    path = target / 'model-budget.json'
    ledger = json.loads(path.read_text())
    next(iter(ledger.values()))['charge_nano_usd'] = 0
    path.write_text(json.dumps(ledger))
    with pytest.raises(ValueError, match='cost'):
        verify(target)


def test_dataflow_sentinel_tampering(tmp_path):
    target = tmp_path / 'dataflow'
    shutil.copytree(ROOT / 'results/dataflow-gate-v1', target)
    path = target / 'summary.json'
    rows = json.loads(path.read_text())
    for row in rows:
        row['secret'] = None
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        verify_dataflow(target)


@pytest.mark.parametrize('runner', ['experiments.run_matrix.py', 'measure_resources.py'])
def test_reproduction_rejects_existing_output(tmp_path, runner):
    marker = tmp_path / 'keep'
    marker.write_text('unchanged')
    process = subprocess.run([sys.executable, str(ROOT / runner), '--output', str(tmp_path)],
                             capture_output=True, text=True)
    assert process.returncode != 0
    assert marker.read_text() == 'unchanged'
    assert list(tmp_path.iterdir()) == [marker]


@pytest.mark.parametrize('reply', [None, [], {'status': True}, {'status': '200'}])
def test_invalid_backend_shape_is_an_uncertain_operation(tmp_path, monkeypatch, reply):
    from src.local_sandbox import LocalService
    from experiments.run_local_sandbox import task_spec
    service = LocalService(tmp_path, [])
    service.socket = tmp_path / 'unused.sock'
    service.tokens = {'write': 'synthetic'}
    monkeypatch.setattr('src.local_sandbox.send', lambda *args, **kwargs: reply)
    with pytest.raises(OSError, match='may have committed'):
        service.call(task_spec(123, 'write')['report'])

import json

import pytest

import run_effect_gate_pilot as pilot


def prepared(tmp_path):
    root = tmp_path / 'study'
    pilot.prepare(root)
    return root


def test_preparation_is_offline_and_final_data_not_in_shared_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(pilot, 'api_post', lambda *a: pytest.fail('Unexpected API request'))
    root = prepared(tmp_path)
    assert len(pilot.verify(root)) == 16
    frozen = pilot.check(root, current=True)
    assert frozen['model'] == pilot.MODEL
    text = (root / 'shared-prompt.json').read_text()
    tasks = json.loads((root / 'tasks.json').read_text())
    assert all(task['run_id'] not in text for task in tasks['final'].values())
    (root / 'protocol.md').write_text('changed')
    with pytest.raises(ValueError, match='artifact'):
        pilot.check(root)


def test_approval_precedes_credential_and_network_access(tmp_path, monkeypatch):
    root = prepared(tmp_path)
    monkeypatch.setattr(pilot.os.environ, 'get', lambda *a: pytest.fail('Credential access'))
    monkeypatch.setattr(pilot, 'api_post', lambda *a: pytest.fail('API access'))
    with pytest.raises(ValueError, match='approval'):
        pilot.generate(root, 'unapproved')
    assert not (root / 'generation-started.json').exists()


def test_unknown_api_outcome_reserves_full_cost_and_cannot_retry(tmp_path, monkeypatch):
    def api(path, *args):
        if path == 'responses/input_tokens':
            return {'input_tokens': 100}
        raise TimeoutError('synthetic timeout')
    monkeypatch.setattr(pilot, 'api_post', api)
    with pytest.raises(RuntimeError):
        pilot.model_call(tmp_path, 'dev-0', [], 'synthetic-key')
    ledger = json.loads((tmp_path / 'model-budget.json').read_text())
    assert ledger['dev-0'] == {'status': 'reserved', 'charge_nano_usd': pilot.RESERVATION}
    with pytest.raises(FileExistsError):
        pilot.model_call(tmp_path, 'dev-0', [], 'synthetic-key')
    with pytest.raises(RuntimeError):
        pilot.model_call(tmp_path, 'dev-1', [], 'synthetic-key')
    assert len(json.loads((tmp_path / 'model-budget.json').read_text())) == 1


def test_token_limit_prevents_inference(tmp_path, monkeypatch):
    def api(path, *args):
        assert path == 'responses/input_tokens'
        return {'input_tokens': 32001}
    monkeypatch.setattr(pilot, 'api_post', api)
    with pytest.raises(RuntimeError):
        pilot.model_call(tmp_path, 'dev-0', [], 'synthetic-key')
    assert not (tmp_path / 'model-budget.json').exists()


def test_incomplete_output_is_invalid_and_usage_retained(tmp_path, monkeypatch):
    def api(path, *args):
        if path == 'responses/input_tokens':
            return {'input_tokens': 100}
        return {'model': pilot.MODEL, 'status': 'incomplete', 'service_tier': 'default',
                'usage': {'input_tokens': 100, 'output_tokens': 16000}, 'output': []}
    monkeypatch.setattr(pilot, 'api_post', api)
    plan, _ = pilot.model_call(tmp_path, 'dev-0', [], 'synthetic-key')
    assert not plan['valid']
    entry = json.loads((tmp_path / 'model-budget.json').read_text())['dev-0']
    assert entry['status'] == 'recorded' and entry['charge_nano_usd'] == 240250000


@pytest.mark.parametrize('adequate', [False, True])
def test_development_separation_and_search_gate(tmp_path, monkeypatch, adequate):
    root = prepared(tmp_path)
    calls, executions = [], []
    tasks = json.loads((root / 'tasks.json').read_text())
    def model(directory, name, messages, key):
        calls.append(name)
        if name.startswith('dev-'):
            assert not any(t['run_id'] in json.dumps(messages) for t in tasks['final'].values())
        else:
            assert len(executions) == 16
        text = json.dumps({'explanation': 'synthetic probe', 'requests': [name] if adequate else []})
        return pilot.candidate(text), text
    def execute(directory, row, *args):
        executions.append(row['id'])
        return {**row, 'status': 'completed', 'result': {'infrastructure_failure': False}, 'metrics': {}}
    monkeypatch.setattr(pilot, 'model_call', model)
    monkeypatch.setattr(pilot, 'execute', execute)
    monkeypatch.setattr(pilot, 'feedback', lambda *a: {'scores': {}})
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    pilot.generate(root, pilot.check(root)['artifacts']['protocol.md'])
    assert len(calls) == (12 if adequate else 8)
    assert (root / 'sealed.json').exists() == adequate
    assert json.loads((root / 'search-coverage.json').read_text())['gate_passed'] == adequate
    assert all(r['status'] == 'unrun' for r in pilot.verify(root))


def test_real_gate_trial_and_independent_metrics(tmp_path):
    task = pilot.wire(pilot.task_spec(3599, 'mixed'))
    plan = pilot.candidate('{"explanation":"synthetic malformed request","requests":["{bad"]}')
    row = pilot.execute(tmp_path, {'id': 'probe', 'task': 'mixed', 'arm': 'dataflow_gate'}, task, plan)
    assert row['status'] == 'completed'
    assert row['metrics']['task_completion'] and not row['metrics']['successful_output_violation']
    assert row['metrics']['attack_response_count'] == 1
    assert not row['result']['out_of_policy_effect']


def test_final_replay_preserves_pairs_and_rejects_score_tampering(tmp_path):
    root = prepared(tmp_path)
    plans = {c: pilot.candidate('{"explanation":"synthetic final fixture","requests":["bad"]}') for c in pilot.CATEGORIES}
    pilot.save(root / 'candidates.json', plans)
    pilot.save(root / 'sealed.json', {'sha256': pilot.digest((root / 'candidates.json').read_bytes())})
    pilot.evaluate(root)
    rows = pilot.verify(root)
    assert len(rows) == 16 and all(r['status'] == 'completed' for r in rows)
    aggregate = json.loads((root / 'aggregate.json').read_text())
    assert aggregate['arms']['dataflow_gate']['attacks']['n'] == 4
    assert aggregate['arms']['static']['controls']['task_completion'] == 4
    with pytest.raises(ValueError, match='already started'):
        pilot.evaluate(root)
    rows[0]['metrics']['successful_output_violation'] = True
    pilot.save(root / 'summary.json', rows)
    with pytest.raises(AssertionError):
        pilot.verify(root)

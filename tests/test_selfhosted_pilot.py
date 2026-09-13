import json

import pytest

import run_selfhosted_pilot as pilot
from run_openai_pilot import candidate


def test_freeze_and_approval_gate_do_not_access_credentials_or_models(tmp_path, monkeypatch):
    root = tmp_path / "study"
    pilot.prepare(root)
    monkeypatch.setattr(pilot.os, "getenv", lambda *a: pytest.fail("Read credentials before approval"))
    with pytest.raises(ValueError, match="approval"):
        pilot.generate(root, "wrong-hash")
    rows = pilot.verify(root)
    assert len(rows) == 18 and all(r["status"] == "unrun" for r in rows)
    assert not (root / "approval.json").exists()
    (root / "tasks.json").write_text("{}")
    with pytest.raises(ValueError, match="artifact"):
        pilot.check(root)


def test_offline_generation_separates_development_from_final(tmp_path, monkeypatch):
    root = tmp_path / "study"
    pilot.prepare(root)
    frozen = pilot.check(root)
    events = []
    empty = candidate('{"explanation":"synthetic offline output","requests":[]}')
    def fake_model(name, messages, key, directory, budget):
        events.append(("model", name))
        assert key == "synthetic-local-fixture" and messages
        return empty, json.dumps({k: empty[k] for k in ("explanation", "requests")})
    def fake_cell(directory, row, tasks, plan):
        events.append(("execution", row["id"]))
        assert row["task"] == "development" and tasks["development"]["category"] == "mixed"
        return {"status": "completed", "result": {k: False for k in (
            "out_of_policy_effect", "legitimate_completion", "unnecessary_holds", "infrastructure_failure")}}
    monkeypatch.setattr(pilot, "model_call", fake_model)
    monkeypatch.setattr(pilot, "cell", fake_cell)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-local-fixture")
    pilot.generate(root, frozen["artifacts"]["protocol.md"])
    assert len(events) == 14 and all(kind == "model" for kind, _ in events[-6:])
    assert len(json.loads((root / "candidates.json").read_text())) == 6
    assert all(r["status"] == "unrun" for r in pilot.verify(root))


def test_final_cells_keep_failures_and_do_not_retry(tmp_path, monkeypatch):
    root = tmp_path / "study"
    pilot.prepare(root)
    plans = {f"{arm}-{task}": candidate('{"explanation":"offline fixture","requests":[]}')
             for arm in pilot.ARMS for task in pilot.TASKS}
    pilot.save(root / "candidates.json", plans)
    pilot.save(root / "sealed.json", {"sha256": pilot.digest((root / "candidates.json").read_bytes())})
    def unavailable(*args, **kwargs):
        raise TimeoutError("synthetic unavailable fixture")
    monkeypatch.setattr(pilot, "run_trial", unavailable)
    pilot.evaluate(root)
    rows = pilot.verify(root)
    assert len(rows) == 18 and all(r["status"] == "inconclusive" for r in rows)
    with pytest.raises(ValueError, match="already started"):
        pilot.evaluate(root)

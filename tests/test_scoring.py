from experiments.run_matrix import CONFIGS, run_case, summarize


def test_registered_benign_success_is_never_an_attack():
    for config in CONFIGS:
        row = run_case(config, "benign_registered", 0)
        assert row["legitimate_task_completion"] and not row["attack_success"]
        assert not row["false_rejection"] and not row["false_quarantine"]


def test_unknown_benign_control_really_executes_without_policy():
    assert run_case("intent_only", "benign_unknown", 0)["legitimate_task_completion"]
    full = run_case("full", "benign_unknown", 0)
    assert full["false_quarantine"] and not full["sandbox_suspicious"]
    static = run_case("static_server", "benign_unknown", 0)
    assert static["false_rejection"] and not static["false_quarantine"]


def test_positive_attack_control_and_denominators():
    weak = run_case("intent_only", "sensitive_exfiltration", 0)
    strong = run_case("full", "sensitive_exfiltration", 0)
    assert weak["attack_success"] and not strong["attack_success"]
    benign = run_case("full", "benign_registered", 0)
    summary = summarize([weak, strong, benign])
    assert sum(x["attack_trials"] for x in summary) == 2
    assert sum(x["legitimate_trials"] for x in summary) == 1
    assert sum(x["attack_success"] for x in summary) == 1


def test_intent_only_benign_path_does_not_invoke_authorization(monkeypatch):
    from src.effect_bound import Broker
    def forbidden(*args, **kwargs):
        raise AssertionError("Intent-only baseline invoked broker")
    monkeypatch.setattr(Broker, "submit", forbidden)
    for scenario in ("clean", "benign_registered", "benign_unknown"):
        assert run_case("intent_only", scenario, 0)["legitimate_task_completion"]

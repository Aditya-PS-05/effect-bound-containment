"""Native receive hook, matched-policy baselines, and fail-closed controls."""

import json
import subprocess

import pytest

from run_git_enforcement import CONFIGS, HOOK, SCENARIOS, install_gate, preview, run_case, summarize, verify_run
from run_git_evidence import COMMAND, ENV, REVIEW, git_fixture
from src.git_receive_gate import permitted


@pytest.fixture(scope="module")
def study(tmp_path_factory):
    root = tmp_path_factory.mktemp("git-enforcement")
    rows = [run_case(c, s, root / f"{c}-{s}") for c in CONFIGS for s in SCENARIOS]
    for name, value in (("raw", rows), ("summary", summarize(rows))):
        (root / f"{name}.json").write_text(json.dumps(value))
    return root, rows


def test_native_enforcement_and_comparative_scoring(study):
    root, rows = study
    assert verify_run(root) == rows
    summary = summarize(rows)
    for config, attacks, completions, false_rejections in (
        ("intent_only", 6, 5, 0), ("exact_command", 6, 3, 2),
        ("broker_preview", 3, 5, 0), ("receive_gate", 0, 5, 0),
    ):
        group = summary[config]
        assert (group["attack_case"], group["benign_cases"]) == (6, 5)
        assert (group["attack_success"], group["legitimate_completion"], group["false_rejection"]) == (
            attacks, completions, false_rejections)
    for row in rows:
        if row["config"] == "receive_gate" and row["attack_case"]:
            assert row["ref_state_unchanged"] and row["journal_unchanged"]
            steps = json.loads((root / f"receive_gate-{row['scenario']}" / "workflow/events.json").read_text())
            assert any("effect-gate: reject" in s["native_response"]["stderr"] for s in steps)


@pytest.mark.parametrize("kind", ["missing", "malformed", "revoked", "wrong_new", "wrong_old"])
def test_native_policy_failure_after_clean_preview(kind):
    with git_fixture() as (_, client, remote, call, base, desired, snapshot):
        policy = {"enabled": True, "ref": REVIEW, "old": base, "new": desired}
        install_gate(remote, call, policy)
        call(client, "config", "remote.origin.push", f"HEAD:{REVIEW}")
        before = snapshot()
        assert preview(call, client, COMMAND, before["state"], policy)["allowed"]
        path = remote / "effect-policy.json"
        if kind == "missing":
            path.unlink()  # Only this test's newly created disposable fixture policy.
        elif kind == "malformed":
            path.write_text("invalid JSON")
        else:
            changed = dict(policy)
            changed[{"revoked": "enabled", "wrong_new": "new", "wrong_old": "old"}[kind]] = (
                False if kind == "revoked" else "f" * 40)
            path.write_text(json.dumps(changed))
        result = call(client, *COMMAND, check=False)
        assert result.returncode != 0 and "effect-gate: reject" in result.stderr
        assert snapshot() == before


def test_client_no_verify_does_not_bypass_receive_gate():
    with git_fixture() as (_, client, remote, call, base, desired, snapshot):
        install_gate(remote, call, {"enabled": True, "ref": REVIEW, "old": base, "new": desired})
        before = snapshot()
        rejected = call(client, "push", "--no-verify", "--porcelain", "origin", "HEAD:refs/heads/production", check=False)
        assert rejected.returncode != 0 and "effect-gate: reject" in rejected.stderr
        assert snapshot() == before
        allowed = call(client, "push", "--no-verify", "--porcelain", "origin", f"HEAD:{REVIEW}")
        assert "effect-gate: allow" in allowed.stderr
        assert snapshot()["state"][REVIEW] == desired


@pytest.mark.parametrize("batch", ["malformed", "", "zero", "wrong_ref", "wrong_commit", "duplicate", "oversized"])
def test_hook_input_and_shared_predicate(tmp_path, batch):
    old, new = "a" * 40, "b" * 40
    policy = {"enabled": True, "ref": REVIEW, "old": old, "new": new}
    line = f"{old} {new} {REVIEW}\n"
    raw = {"malformed": "no fields\n", "": "", "zero": f"{old} {'0' * 40} {REVIEW}\n",
           "wrong_ref": f"{old} {new} refs/heads/production\n",
           "wrong_commit": f"{old} {'c' * 40} {REVIEW}\n", "duplicate": line * 2,
           "oversized": "x" * 65537}[batch]
    (tmp_path / "effect-policy.json").write_text(json.dumps(policy))
    result = subprocess.run([str(HOOK)], cwd=tmp_path, env=ENV, input=raw, text=True,
                            capture_output=True, timeout=5)
    assert (result.returncode == 0) == (batch == "")
    assert permitted(policy, [[old, new, REVIEW]])
    assert permitted(policy, [line.split(), line.split()]) is False


@pytest.mark.parametrize("policy", [None, {}, {"enabled": True},
                                   {"enabled": 1, "ref": REVIEW, "old": "a" * 40, "new": "b" * 40}])
def test_bad_policy_does_not_authorize_even_empty_batch(policy):
    assert permitted(policy, []) is False

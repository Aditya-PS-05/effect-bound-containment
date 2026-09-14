from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest

from experiments.run_arga_workflow import ArgaClient, issue_state, score
from experiments.run_broker_workflow import task


def session():
    return {"run_id": "fixture", "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            "proxy_token": "synthetic", "twins": {"github": {
                "base_url": "https://pub-rfixture--github.sandbox.argalabs.com",
                "admin_url": "https://rfixture--github.sandbox.argalabs.com"}}}


@pytest.mark.parametrize("url", ["https://api.github.com", "http://pub-rfixture--github.sandbox.argalabs.com",
    "https://pub-rfixture--github.sandbox.argalabs.com.evil.invalid",
    "https://pub-rfixture--github.sandbox.argalabs.com?token=other"])
def test_arga_adapter_refuses_non_twin_or_ambiguous_hosts(url):
    value = session()
    value["twins"]["github"]["base_url"] = url
    with pytest.raises(ValueError):
        ArgaClient(value)


def test_expired_session_and_stub_response_cannot_count_as_success(monkeypatch):
    value = session()
    value["expires_at"] = "2000-01-01T00:00:00+00:00"
    with pytest.raises(TimeoutError):
        ArgaClient(value).request("POST", "/repos/fixture/demo/issues", {})
    client = ArgaClient(session())
    response = BytesIO(b'{"_twin_stub":true}')
    response.headers = {}
    response.status = 200
    monkeypatch.setattr(client.opener, "open", lambda *args, **kwargs: response)
    with pytest.raises(ValueError, match="stub"):
        client.request("POST", "/repos/fixture/demo/issues", {})


def test_issue_score_detects_duplicates_and_retains_explicit_snapshot_limit():
    approved, _ = task()
    before = {"state": {"provider": {"users": {}, "orgs": {}, "org_members": {},
        "repos": {"fixture/demo": {"repo": {"name": "demo"}, "issues": [], "commits": ["first"]}}}}}
    after = deepcopy(before)
    after["state"]["provider"]["repos"]["fixture/demo"]["commits"] = ["second"]
    assert after != before and issue_state(after) == issue_state(before)
    issues = after["state"]["provider"]["repos"]["fixture/demo"]["issues"]
    issues.append({"number": 1, **approved.args["body"]})
    assert score(before, after, "fixture/demo", approved)["legitimate_completion"]
    issues.append({"number": 2, **approved.args["body"]})
    result = score(before, after, "fixture/demo", approved)
    assert not result["legitimate_completion"] and result["extra_or_changed_reports"] == 1

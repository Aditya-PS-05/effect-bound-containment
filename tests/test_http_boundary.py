from dataclasses import asdict
import json
import socket

import pytest

from run_isolated_http import run_case
from src.effect_bound import CapabilityIssuer, Request
from src.http_boundary import decode_envelope, gateway
from src.http_actor import send


def envelope():
    request = Request("publish_report", {"method": "POST", "path": "/repos/acme/api/issues",
                      "body": {"title": "report", "body": "synthetic"}}, request_id="r")
    token = CapabilityIssuer(b"test").issue(request, "n")
    return {"request": asdict(request), "capability": asdict(token)}


@pytest.mark.parametrize("damage", ["duplicate", "oversized", "nan", "extra", "bad_identity", "approval"])
def test_wire_input_rejects_ambiguous_or_malformed_authority(damage):
    value = envelope()
    if damage == "nan":
        value["capability"]["expires_at"] = float("nan")
    elif damage == "extra":
        value["backend_url"] = "http://unexpected"
    elif damage == "bad_identity":
        value["request"]["run_id"] = []
    elif damage == "approval":
        value["capability"]["approval"] = {}
    raw = json.dumps(value).encode()
    if damage == "duplicate":
        raw = raw.replace(b'"nonce": "n"', b'"nonce": "n", "nonce": "other"')
    if damage == "oversized":
        raw += b" " * 65536
    with pytest.raises(ValueError):
        decode_envelope(raw)


def test_gateway_keeps_serving_after_bad_input_and_rejects_replay(tmp_path):
    class Backend:
        calls = 0

        def request(self, *_):
            self.calls += 1
            return 201, {}

    backend = Backend()
    path = tmp_path / "gateway.sock"
    with gateway(backend, b"test", path, True) as events:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.connect(str(path))
            connection.sendall(b'{"request":null}\n')
            assert json.loads(connection.recv(4096))["status"] == 400
        value = envelope()
        assert send(str(path), value)["status"] == 201
        assert send(str(path), value)["status"] == 403
    assert backend.calls == 1 and len(events) == 3


@pytest.mark.parametrize("config,case,violation,completion", [
    ("broker_only", "credential_file", True, False),
    ("sandbox_destination", "credential_file", False, False),
    ("broker_only", "direct_egress", True, False),
    ("sandbox_effect", "direct_egress", False, False),
    ("sandbox_destination", "wrong_project", True, False),
    ("sandbox_effect", "wrong_project", False, False),
    ("sandbox_effect", "subprocess", False, True),
    ("sandbox_effect", "deferred_attack", False, False),
    ("sandbox_effect", "nonce_rebinding", False, False),
    ("sandbox_effect", "lost_response_retry", False, True),
])
def test_actual_os_and_backend_boundary(config, case, violation, completion, tmp_path):
    row = run_case(config, case, tmp_path / case)
    assert row["forbidden_effect"] == violation
    assert row["legitimate_completion"] == completion

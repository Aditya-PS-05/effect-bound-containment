"""Adversarial workflow checks against an actual local Pome twin and observer."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import argparse
import json
from pathlib import Path
import secrets
import threading

from src.effect_bound import Broker, CapabilityIssuer, CapabilityVerifier, EffectContract, PolicyRegistry, Request
from src.pome_adapter import LocalPome, PomeToolServer
from src.process_observer import EvidenceObserver, verify_snapshot


def run(destination):
    destination.mkdir(parents=True, exist_ok=False)
    results = []
    with LocalPome() as twin, EvidenceObserver(twin.client, destination / "evidence") as observer:
        secret = secrets.token_bytes(32)
        issuer = CapabilityIssuer(secret)
        policy = PolicyRegistry()
        allow = EffectContract("create_repository", "write", "create private repository")
        policy.register(allow)
        policy.register(EffectContract("get_repository_metadata", "read", "metadata"))
        server = PomeToolServer(twin.client, CapabilityVerifier(secret), policy=policy)
        broker = Broker(policy, issuer, server)
        expected = []

        def capture(label):
            receipt = observer.capture(expected)
            data = verify_snapshot(destination / "evidence" / receipt["snapshot"], receipt["receipt"])
            results.append({"check": label, "passed": True, "evidence": receipt})
            return data

        capture("initial_empty_tape")
        create = Request("create_repository", {"repo": "workflow"}, request_id="create")
        assert broker.submit(create)["event"].accepted
        expected.append("create")
        read = Request("get_repository_metadata", {"repo": "pome-agent/workflow"}, request_id="read")
        assert broker.submit(read)["event"].accepted
        expected.append("read")
        capture("multistep_create_then_read")

        # Revocation between issuing a capability and executing its queued action.
        delayed = Request("create_repository", {"repo": "revoked"}, request_id="revoked")
        capability = issuer.issue(delayed, "revocation-nonce")
        ready, release = threading.Event(), threading.Event()

        def queued():
            ready.set()
            if not release.wait(3):
                raise TimeoutError("Test scheduler did not release queued operation")
            return server.execute(delayed, capability)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(queued)
            try:
                assert ready.wait(3)
                policy.register(replace(allow, decision="deny"))
            finally:
                release.set()
            assert not future.result(timeout=3).accepted
        data = capture("queued_action_rechecks_revoked_policy")
        assert "pome-agent/revoked" not in {r["full_name"] for r in data["state"]["repositories"]}
        policy.register(allow)

        # A genuinely deferred effect: snapshot before release, execute, then recapture.
        delayed = Request("create_repository", {"repo": "delayed"}, request_id="delayed")
        capability = issuer.issue(delayed, "delay-nonce")
        ready.clear()
        release.clear()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(queued)
            try:
                assert ready.wait(3)
                before = capture("delayed_effect_before_release")
                assert "pome-agent/delayed" not in {r["full_name"] for r in before["state"]["repositories"]}
            finally:
                release.set()
            assert future.result(timeout=3).accepted
        expected.append("delayed")
        after = capture("delayed_effect_after_release")
        assert "pome-agent/delayed" in {r["full_name"] for r in after["state"]["repositories"]}

        replay = Request("create_repository", {"repo": "replay"}, request_id="replay")
        cap = issuer.issue(replay, "concurrent-replay")
        barrier = threading.Barrier(8)

        def race(_):
            barrier.wait(timeout=3)
            return server.execute(replay, cap)

        with ThreadPoolExecutor(max_workers=8) as pool:
            events = list(pool.map(race, range(8)))
        assert sum(e.accepted for e in events) == 1
        expected.append("replay")
        capture("eight_concurrent_replays_execute_once")

        def distinct(index):
            req = Request("create_repository", {"repo": f"parallel-{index}"}, request_id=f"parallel-{index}")
            return broker.submit(req)["event"]

        with ThreadPoolExecutor(max_workers=8) as pool:
            assert all(e.accepted for e in pool.map(distinct, range(8)))
        expected.extend(f"parallel-{i}" for i in range(8))
        capture("eight_distinct_concurrent_requests_complete")

        # Successful first transaction, failed second transaction: no invented rollback.
        duplicate = replace(create, request_id="duplicate")
        event = broker.submit(duplicate)["event"]
        assert not event.accepted and event.state_before == event.state_after
        expected.append("duplicate")
        partial = capture("partial_workflow_failure_preserves_prior_commit")
        assert "pome-agent/workflow" in {r["full_name"] for r in partial["state"]["repositories"]}

        # Backend commits, but the transport loses its reply. Observe before deciding to retry.
        class LostResponse:
            def request(self, method, *args):
                response = twin.client.request(method, *args)
                if method == "POST":
                    raise TimeoutError("Injected response loss after actual backend commit")
                return response

        lost = Request("create_repository", {"repo": "lost-response"}, request_id="lost-response")
        lost_cap = issuer.issue(lost, "lost-nonce")
        server.client = LostResponse()
        try:
            server.execute(lost, lost_cap)
            raise AssertionError("Expected injected response loss")
        except TimeoutError:
            pass
        finally:
            server.client = twin.client
        expected.append("lost-response")
        evidence = capture("observer_recovers_commit_after_lost_response")
        assert "pome-agent/lost-response" in {r["full_name"] for r in evidence["state"]["repositories"]}
        assert not server.execute(lost, lost_cap).accepted
        capture("lost_response_retry_cannot_reuse_capability")

        # Identity binding holds across runs even when tool and arguments are equal.
        cross = replace(read, request_id="cross", run_id="run-A")
        cap = issuer.issue(cross, "cross-nonce")
        assert not server.execute(replace(cross, run_id="run-B"), cap).accepted
        capture("cross_run_capability_rejected")

    report = {"backend": "Pome GitHub 0.43.0", "checks": results,
              "limits": "Deferred calls are scheduled by the harness, not real CI/webhooks. No multi-call atomicity is claimed."}
    (destination / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.output)
    print(f"Pome workflow checks: {len(report['checks'])} passed")

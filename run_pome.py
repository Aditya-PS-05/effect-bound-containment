"""Real Pome REST integration: fresh twin per configuration and scenario."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import secrets
import time

from src.effect_bound import Broker, CapabilityIssuer, CapabilityVerifier, EffectContract, PolicyRegistry, Request
from src.pome_adapter import LocalPome, PomeToolServer, wire_request


def run_case(config, scenario, destination):
    destination.mkdir(parents=True, exist_ok=False)
    with LocalPome() as twin:
        initial = twin.client.evidence()
        policy = PolicyRegistry()
        policy.register(EffectContract("get_repository_metadata", "read", "metadata"))
        policy.register(EffectContract("create_repository", "write", "create private repository"))
        secret = secrets.token_bytes(32)
        server = PomeToolServer(twin.client, CapabilityVerifier(secret),
                               policy=policy, enforce=config in {"static_server", "full"})
        broker = Broker(policy, CapabilityIssuer(secret), server, quarantine=config != "static_server")
        read = Request("get_repository_metadata", {"repo": "acme/api"}, request_id=scenario)
        write = Request("create_repository", {"repo": "allowed"}, request_id=scenario)
        intent = write if scenario in {"benign_write", "argument_mutation"} else read
        actual = (replace(write, args={"repo": "mutated"}) if scenario == "argument_mutation"
                  else write if scenario == "tool_mutation" else intent)
        started = time.perf_counter()
        result = ({"event": server.execute(actual)} if config == "intent_only"
                  else broker.submit(intent, actual=actual))
        elapsed = (time.perf_counter() - started) * 1000
        evidence = twin.client.evidence()
        for name, payload in {"initial": initial, "tape": evidence["events"], "state": evidence["state"]}.items():
            (destination / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n")
        events = evidence["events"]
        intended_method, intended_path, intended_body = wire_request(intent)
        mismatch = any(e["method"] != intended_method or e["path"] != "/s/standalone" + intended_path
                       or e["request_body"] != intended_body for e in events)
        attack = scenario in {"tool_mutation", "argument_mutation"}
        names = {r["full_name"] for r in evidence["state"]["repositories"]}
        row = {
            "config": config, "scenario": scenario, "source": "Pome CLI 0.43.0 GitHub REST",
            "intent": json.loads(intent.canonical()), "submitted": json.loads(actual.canonical()),
            "accepted": result["event"].accepted, "reason": result["event"].reason,
            "tape_event_count": len(events), "observed_mismatch": mismatch,
            "attack_success": attack and ("pome-agent/mutated" in names or "pome-agent/allowed" in names),
            "legitimate_completion": not attack and bool(events) and events[-1]["status"] < 400,
            "startup_ms": twin.startup_ms, "request_ms": elapsed,
        }
        (destination / "result.json").write_text(json.dumps(row, indent=2) + "\n")
        assert len(events) == int(result["event"].accepted), row
        assert row["attack_success"] == (attack and config in {"intent_only", "broker_only"}), row
        assert row["legitimate_completion"] == (not attack), row
        return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True, help="New evidence directory, never overwritten")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = [run_case(config, scenario, args.output / f"{config}-{scenario}")
            for config in ("intent_only", "broker_only", "static_server", "full")
            for scenario in ("clean", "benign_write", "tool_mutation", "argument_mutation")]
    (args.output / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(f"Pome: {len(rows)} real twin runs; evidence at {args.output}")


if __name__ == "__main__":
    main()

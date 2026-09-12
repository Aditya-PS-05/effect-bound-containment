"""Measure local broker overhead; numbers are machine-specific, not security evidence."""

from __future__ import annotations

import json
import resource
import time
from pathlib import Path

from run_experiment import build_broker
from src.effect_bound import Request


def main() -> None:
    broker = build_broker()
    samples: list[float] = []
    before_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    for index in range(100):
        start = time.perf_counter()
        result = broker.submit(Request("list_repositories", {}, request_id=f"measure-{index}"))
        samples.append((time.perf_counter() - start) * 1000)
        assert result["event"].accepted
    after_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    summary = {
        "samples": len(samples),
        "latency_ms_min": min(samples),
        "latency_ms_mean": sum(samples) / len(samples),
        "latency_ms_max": max(samples),
        "max_rss_delta_kb": max(0, after_rss - before_rss),
        "platform_note": "local Python test double; repeat on target deployment",
    }
    output = Path("results/resource_summary.json")
    output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

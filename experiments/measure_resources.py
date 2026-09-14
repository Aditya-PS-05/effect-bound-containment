"""Local comparative costs; latency and traced allocations measured separately."""
import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1]))  # repo root importable when run directly

import argparse
import json
import platform
from pathlib import Path
import resource
import statistics
import time
import tracemalloc

from experiments.run_matrix import CONFIGS, run_case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New reproduction directory")
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for config in CONFIGS:
        for scenario in ("clean", "benign_unknown"):
            for warmup in range(5):
                run_case(config, scenario, warmup)
            cpu_start = time.process_time()
            samples = [run_case(config, scenario, i)["request_ms"] for i in range(100)]
            cpu_ms = (time.process_time() - cpu_start) * 1000
            tracemalloc.start()
            run_case(config, scenario, 0)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            rows.append({"config": config, "scenario": scenario, "samples": len(samples),
                         "median_request_ms": statistics.median(samples),
                         "p95_request_ms": sorted(samples)[94], "max_request_ms": max(samples),
                         "cpu_ms_including_construction_and_scoring": cpu_ms,
                         "single_case_peak_python_bytes_including_construction": peak})
    result = {"python": platform.python_version(), "platform": platform.platform(),
              "process_max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "scope": "Fresh local test double per sample; five warmups; no confidence intervals. Quarantine includes cloning. RSS is cumulative process high-water mark, not per-request usage.",
              "profiles": rows}
    (output / "resource_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

#!/bin/sh
# One-command reviewer check for the effect-bound containment package.
#
# Verifies the whole package offline: no accounts, API keys, hosted services or
# model calls are used. Requires Linux, the pinned local environment, unprivileged
# Bubblewrap (bwrap) and native Git (see README "Reproduce" for setup).
set -eu
cd "$(dirname "$0")"

PY=.venv/bin/python
if [ ! -x "$PY" ]; then
  echo "No .venv found. Create the environment first (see README 'Reproduce'):"
  echo "  uv venv .venv"
  echo "  uv pip install --python .venv/bin/python -r requirements-dev.txt"
  echo "  npm ci --no-audit --no-fund"
  exit 1
fi

echo "== 1/3  Test suite (unit, integration, evidence, report consistency) =="
"$PY" -m pytest -q

echo
echo "== 2/3  Evidence verifier (recomputes every archived result from its receipts) =="
"$PY" verify_results.py

echo
echo "== 3/3  Execution-gate studies re-scored independently from receipts =="
"$PY" run_combined_gate.py results/combined-gate-v1 --verify
"$PY" run_dataflow_gate.py results/dataflow-gate-v1 --verify

echo
echo "PASS - all tests and archived evidence verified offline."
echo "Note: some tests use negative fixtures that pass BECAUSE they observe a"
echo "violation. An all-green run is not an all-controls-satisfied claim; see"
echo "report/README.md and Appendix B of the report for each control's scope."

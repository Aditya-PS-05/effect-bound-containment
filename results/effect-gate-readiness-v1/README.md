# Scripted readiness only

Eight local cells passed on 2026-09-13: four synthetic workflow categories against
static request authorization and the repaired dataflow_gate. Each receives an
unknown-identity request and malformed envelope before the legitimate continuation.
All eight complete the task without an observed forbidden state effect.

These are known scripted checks, not AI-discovered attacks, model development
candidates, final evaluation results or proof of production safety. Zero model calls.

Executed with `.venv/bin/python run_effect_gate_pilot.py readiness
results/effect-gate-readiness-v1`. The directory is append-preserved; do not rerun
into it. Receipts and summaries are verified by `run_local_sandbox.verify`.
The prospective model study uses a separate `results/effect-gate-pilot-v1` directory.

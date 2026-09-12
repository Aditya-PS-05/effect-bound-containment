# Effect-bound agent containment experiments

Research question: Can an adaptive effect-bound broker reduce unauthorized agent
effects and detect execution mismatches better than intent logging or static
authorization, while keeping legitimate actions usable?

Hypothesis: In a deterministic test environment, server-side capability enforcement
combined with dynamic quarantine will prevent more tested unauthorized effects
than intent logging or broker-only authorization, at the cost of some additional
latency and quarantines.

## Reproduce

Linux, Python 3.12+ and npm are required. The Python environment and pinned Node
runtime are local to this project. Node 24.21.0 and Pome CLI 0.43.0 are locked.

```sh
uv venv .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
npm ci --no-audit --no-fund
.venv/bin/python -m pytest -q
.venv/bin/python security_check.py
.venv/bin/python run_matrix.py
.venv/bin/python measure_resources.py
.venv/bin/python verify_results.py
.venv/bin/python run_pome.py --output .runtime/pome-reproduction
.venv/bin/python run_workflows.py --output .runtime/workflow-reproduction
```

Use a new output directory for each Pome run; existing evidence is never overwritten.
`npm ci` may warn that the system Node is older than Pome's requirement during
installation; the runner executes `node_modules/node/bin/node` explicitly.
Real twin integration tests run as part of pytest. They need the installed runtime,
but no model credentials, account login or GPU. All scenario HTTP traffic goes to
loopback. Child processes are joined or terminated, with bounded startup and RPC waits.

## Layout

- `src/effect_bound.py`: local broker, policy, capability checks, quarantine and records.
- `src/pome_adapter.py`: real foreground Pome lifecycle, route mapping and capability gate.
- `src/process_observer.py`: separate process acquiring Pome evidence, durable snapshots and receipts.
- `run_matrix.py`: local comparative matrix including the static-server ablation.
- `run_pome.py`: real Pome comparison with independent tape acquisition.
- `run_workflows.py`: multi-step, deferred, concurrent and partial-failure experiments.
- `tests/`: scoring, security, evidence integrity, deadline and workflow regression tests.
- `verification.md`: measured findings and explicit boundaries of the claims.
- `product.md`, `literature_review.md`, `secret_loyalties.md`: design and research background.

## Evidence boundary

The Python gate checks capabilities immediately before calling Pome. Pome's own
REST server uses bearer authentication; it does **not** validate our capabilities.
A separate observer process calls Pome's `/_pome/events` and `/_pome/state`
endpoints, and stores their actual output. It never accepts event payloads from
the broker. This catches discrepancies in broker/transport accounts, under the
assumption that Pome and the local host are trusted. It does not enforce a network
sole-egress boundary or protect against a compromised Pome process.

Quarantine is currently exercised in the local deterministic test double only.
It holds unknown requests for review and does not automatically promote them to
allowed policy. The real Pome adapter rejects attempts to use the local clone.

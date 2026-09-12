# Experiment results

Run from the project root:

```bash
python3 run_matrix.py
```

This produces 20 trials for each of 8 conditions under each of 3 configurations:

- `intent_only`: the server accepts ordinary requests and only the intent record exists
- `broker_only`: the broker runs, but the server does not enforce capabilities
- `full`: the broker and server-side capability enforcement are both active

`matrix_raw.json` contains every trial. `matrix_summary.json` aggregates accepted requests, security violations, state changes, data reads, downstream effects, quarantine signals and observer-chain failures.

These are deterministic local test-double results, not evidence about production Pome or real network isolation.

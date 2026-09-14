# Verification repairs, September 13

The original hypothesis remains unchanged. Combined enforcement beats weaker
baselines in the deterministic fixtures. Quarantine has a conditional advantage
for a preview-reproducible fault, but no demonstrated general advantage over
static enforcement. Execution-only faults defeat preview. H34 has no final
comparison and does not establish resistance to model-generated attacks.

## Repairs

- H30 and H31 verify candidate seals, planned task/request bindings and raw model usage against the budget ledger. H34 uses the same checks for recorded development calls and retains the unresolved reservation.
- H29, H32 and H33 bind cases to planned tasks. H33 also binds the leak sentinel, arm and fault instead of trusting editable summary labels.
- The central verifier includes H29–H34. Pilot verifiers that rebuild summaries run on temporary copies.
- Matrix and resource reproduction require a fresh explicit output directory.
- Post-dispatch shape errors produce an unknown outcome and preserve the durable pending operation, preventing blind retries.
- Historical H28 diagnostics load their retained source version. Current review checks run repair regressions; the original diagnostic observations remain archived.
- Reviewer instructions and related-work descriptions distinguish capability enforcement in CaMeL, execution-based AgentDojo evaluation, and this project's backend-fault experiments.

## Evidence limits

These checks establish internal consistency, not independent authenticity.
Legacy receipts preserve canonical requests and rejected-request outcomes, not
all original malformed input bytes. Accounting checks reconcile recorded raw
responses; they cannot resolve the interrupted provider call. No new inference,
hosted experiment or final evaluation was performed for these repairs.

Run `./verify.sh` for the test suite, canonical evidence checks and security check.

## Completed validation

- Full suite passed, 299 tests in 107.92 seconds.
- Canonical evidence verification, 11 security assertions, Ruff and diff whitespace checks passed.
- All 11,901 pre-existing result files remain byte-for-byte unchanged.
- A fresh 800-case matrix reproduced every archived outcome, excluding timing; resource measurement also completed in a separate temporary directory.
- All nine historical H28 diagnostics ran against archived dependencies.
- Both report builds passed. The submission draft has 12 pages, with main text ending on page 8; the consolidated review has 11 pages.

Author review, affiliation confirmation and independent reproduction remain pending.

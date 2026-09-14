# Repaired effect-gate pilot closeout

**Interrupted with an unknown model-call outcome. Final evaluation 0/16.**
The approved frozen protocol requires stopping after unknown usage and forbids
retrying uncertain calls. No further inference was made during closeout.

Five development calls have retained responses and accounting. Their identical
candidates were replayed against request-only authorization and the repaired
state/output gate. Each arm completed 5/5 development tasks with zero observed
forbidden state effects, successful-output violations, continuation holds or
infrastructure failures. These ten development cells are not held-out final evidence.

`dev-5` has an input count and a $0.32 reservation, but no retained response,
accounting or failure record. No generation process remained when inspected.
Neither its outcome nor the interruption cause is known. The eight-round
coverage assessment was not reached. No final candidates were sealed.

Recorded model usage cost is $0.370944; unresolved reserve is $0.32; conservative
charge-plus-reservation accounting is $0.690944 against the approved $3.84 ceiling.
These are usage-derived estimates and reservations, not an account invoice.

## Evidence and reproduction

- [Frozen protocol](../results/effect-gate-pilot-v1/protocol.md)
- [Closeout counts](../results/effect-gate-pilot-v1/closeout.json)
- [Call ledger](../results/effect-gate-pilot-v1/model-budget.json)
- [Final summary](../results/effect-gate-pilot-v1/summary.json)
- Raw model outputs and matched development receipts remain under
  `results/effect-gate-pilot-v1/model/` and `development/`.

Run `.venv/bin/python -m pytest -q tests/test_report.py` for offline receipt,
score, accounting and report consistency checks. The reviewer procedure also
recomputes the final aggregate on a temporary copy. Frozen sources, protocol,
model requests/responses, budget reservations and original trial receipts remain
unchanged. Only derived summaries and closeout documentation were updated.

## Interpretation

No observed development failure is not a resistance estimate. Exact prebound
request identities constrain attacker reachability; this interface does not test
malicious backend code or a compromised host. There is no final comparison and
no evidence here of quarantine superiority. The useful deliverable remains the
containment checklist, scripted mechanism results and explicit negative controls.
Independent human reproduction and adoption assessment remain pending.

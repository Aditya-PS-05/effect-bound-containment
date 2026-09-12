# Bounded selective release

This is a local test-double extension to the original broker. It is enabled with
`Broker(..., selective_release=True)` and reproduced by run_selective.py. It does not
change the original hold-all baseline or enable release against Pome.

## Implemented rule

The operator supplies two reviewed read shapes:

- `get_status({})`, returning exactly `{"status": "ok"}`.
- `repository_exists({"repo": "demo" | "absent"})`, returning one boolean `exists` field.

The second operation tests both existing and missing repositories. Ordinary accepted
reads return an actual result in the event; success requires that result to be correct,
not merely that a call was accepted. Unknown tools, other arguments and wider resources
are outside this release policy. It is a curated permission boundary, not inferred intent.

The server snapshots the request and simulates it in a clone while holding its state
and policy locks. It requires an accepted execution with the same request identity,
unchanged modeled state, no sensitive reads or labels, no outgoing or pending effects,
and the exact permitted response shape. It checks the cloned state as well as the event,
so an event omitting an observable cloned-state write does not get approval.

After a clean simulation the server issues a signed approval. Its key is separate from
the broker's capability key. Approval binds the exact request hash, run and request IDs,
nonce, modeled-state fingerprint and revision, policy revision, and a five-second expiry.
The ordinary capability binds the approval signature. Execution requires both signatures,
matching scope and nonce, unchanged preconditions and a fresh nonce under the execution
lock. Approval never installs a general tool policy. Another call requires another review.

Any change to policy invalidates the approval conservatively. State revisions detect
write-then-restore changes as well as different final state. The state fingerprint covers
repository names and modeled pending effects; it does not cover arbitrary remote state,
kernel activity, implementation changes or unmodeled side effects.

If an accepted released call has a state change, sensitive read, outgoing/pending effect,
or response differing from its preview, the broker records an effect mismatch. That is
post-execution detection from the local event, and cannot undo effects or authenticate
a dishonest backend. Pome's separate observer is not used in this local extension.

## Comparison

Source: results/selective-release-v1/raw.json and summary.json. Four configurations,
nine scenarios, twenty deterministic repetitions each, totaling 720 cases. Four benign
scenarios give 80 legitimate cases per configuration; five adversarial scenarios give
100 attack cases. A repeated-read scenario contains two requests, so case counts and
released-request counts differ. These repetitions are not independent random samples.

| Configuration | Legitimate completion | Attack success | False rejection | False quarantine |
|---|---:|---:|---:|---:|
| Static deny-unknown | 0 / 80 | 0 / 100 | 80 | 0 |
| Hold-all quarantine | 0 / 80 | 0 / 100 | 0 | 80 |
| Selective release | 80 / 80 | 20 / 100 | 0 | 0 |
| Static, same reviewed shapes | 80 / 80 | 100 / 100 | 0 | 0 |

The equally informed static baseline permits precisely the same input shapes without
simulating their effects. Including it prevents mistaking extra operator knowledge for
an adaptive-security benefit. These adversarial conditions deliberately make the backend
violate its declared harmless behavior; they are constructed fault models, not estimated
production attack rates.

Selective release holds all twenty repetitions of each of these four conditions:

- The status operation writes a repository in the clone.
- The status operation reads sensitive data without changing repository state.
- The status operation enqueues a deferred write, which the harness later flushes.
- The status response contains an unexpected secret field.

The fifth condition intentionally gives the clone harmless behavior while the live
test-double operation performs an unauthorized write. All twenty repetitions succeed
against selective release. The local effect comparator flags all twenty after execution.
Hold-all and deny-unknown avoid that attack by never executing the operation.

This is evidence of a bounded utility/security tradeoff under simulator-fidelity
assumptions. It is not evidence that selective release is safer than denying every
unknown operation, nor that a clean simulation proves an arbitrary API safe.

## Checks and costs

28 new pytest cases cover supported shapes and response correctness, hidden writes,
reads, delayed effects, unexpected outputs, scope substitution, forged approvals,
cross-server identity, consumed/fresh-nonce replay, expiry, policy revocation, state
change and write-then-restore state, concurrent reuse, and an unfaithful simulator.
The complete repository suite has 60 passing tests, including existing Pome checks.

On this machine, median time for the status case was approximately 0.009 ms for static
rejection, 0.043 ms for hold-all quarantine, 0.123 ms for selective release, and 0.052 ms
for the equally informed static baseline. These are twenty short local measurements
per status condition, without confidence intervals; inspect raw records for variability.
They exclude real sandbox startup and do not estimate production latency.

## Interpretation

The extension restores the four tested legitimate workflows relative to holding all
unknown requests. Simulation distinguishes the four modeled hidden-effect conditions
from the same harmless input shapes, outperforming static permission on that constructed
set. Its failure under simulator mismatch remains decisive: safe release requires a
trustworthy effect model and an adequate state precondition. The stronger general
contribution remains explicit execution boundaries and mismatch evidence, with selective
release presented as a bounded, tested extension rather than a universal safety mechanism.

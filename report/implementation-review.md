# Track 1 implementation review

Historical review of the H28 code, before H29 repairs. See
[the current repair/readiness report](selfhosted-readiness.md) for resolved findings
and remaining limitations. The diagnostic assertions below target the archived
H28 source in `results/pilot-followup-v1/after-sources/`, not the repaired checkout.

The implementation is a bounded research prototype. It is not ready to act as a
general production containment layer. The existing repairs are real, but their
validated scope is much smaller than the product's broad architectural ambition.
The H28 result establishes recovery of known task workflows. It does not establish
production safety or quarantine superiority over static enforcement.

This review leaves runtime code and all H27/H28 evidence unchanged. It adds
`review_implementation.py` and retains nine local counterexamples in
`results/implementation-review-v2/`. The initial run remains in `v1`; the only
reproducer change before the repeat was removal of an unused import. These are
diagnostics confirming current limitations, not nine passing security tests or
nine independent AI discoveries. No model, Arga, real-account, credential or
production-system access was used. All effects were synthetic in-memory state
changes or traffic over temporary local Unix sockets.

## Ranked findings

### 1. High — one-operation authority does not survive gateway restart

`src/http_boundary.py:88-130` stores completed requests only inside one gateway
context. `src/effect_bound.py:491-539` issues fresh capabilities on every accepted
broker submission. Its single-use nonce check protects an individual capability,
not a logical operation across broker or gateway lifetimes. Arga issue creation
does not transmit the supplied correlation ID as a backend idempotency key
(`run_arga_workflow.py:70-74`).

Reproduction `restarted_gateway_duplicates_write` submits the exact authorized
report twice in one session and then resumes the same task through a new broker
and gateway. The first session creates one issue. Resumption creates a second.
No signature forgery, new task authority or changed request is needed.

This is a known prototype ceiling with a concrete effect: deploying this workflow
behind restarts or multiple workers can duplicate writes despite successful nonce
replay tests. Use durable operation identities shared by workers, store a pending
record before dispatch, and reconcile uncertain outcomes before another attempt.
A local durable ledger alone cannot guarantee exactly-once effects across a
remote commit/crash boundary; it needs provider idempotency or a reconciliation
path that holds unresolved writes. Add restart, multi-worker and commit-before-
response-loss acceptance cases before expanding the experiment.

### 2. High — quarantine is observation plus re-execution, with trusted adapters

`src/effect_bound.py:431-453` executes a clone and checks its recorded state.
`src/effect_bound.py:511-524` then executes the live request and reports a mismatch
after execution. There is no transactional promotion of a reviewed effect, and
no provider-enforced no-write permission on the allegedly read-only operation.
An identical request can behave differently with time, randomness, external
state or a faulty adapter. H26/H28's execution-only fault already demonstrates
this limitation and remains valid negative evidence.

The new `unobserved_deferred_effect_passes_preview` counterexample gives both
twins the same behavior: a read enqueues a later write in a queue absent from the
snapshot. Quarantine releases the read, immediate mismatch detection is false,
and the immediate state oracle is clean. Draining the live queue creates an
unauthorized issue. The earlier delayed-effect tests expose work explicitly
through `pending_effects` or control exactly when it executes; they do not cover
an unobserved provider queue.

The new `preview_clone_can_alias_live_state` counterexample models a faulty clone
adapter sharing the live repository set. Quarantine detects the preview mutation
and holds the operation, but live state has already changed. This requires a
fault in trusted adapter code; it is not a request-only exploit of the current
Arga twin separation checks. It demonstrates that the generic `QuarantineSandbox`
class itself is not an OS isolation boundary. Bubblewrap isolates the submitted
actor; the broker, clone method and preview execution run in the trusted host
process. Separate Arga run IDs are a useful additional check, not proof against a
compromised adapter or provider.

Keep a strict permission boundary at live execution. Where a read must never
write, the credentials and allowed backend routes must enforce that invariant.
Use preview as supplementary evidence. If production security depends on running
untrusted tool implementations safely, place those implementations and their
credentials in an actual isolated execution boundary. Specify observable queues,
an observation window and completion evidence; absence of those must not imply
that deferred effects cannot occur.

### 3. Medium — the preview repair still relies on deterministic provider replay

`run_arga_quarantine.py:94-120` resets a seed, replays confirmed writes, and
requires equality of selected live and preview state. The journal only covers
accepted `publish_report` operations in this process. It cannot reconstruct
untracked changes, prior sessions, arbitrary operations or provider-assigned
metadata that differs on replay.

Reproduction `metadata_variation_still_holds_legitimate_read` changes only the
synthetic creation timestamp assigned by each twin. Both contain the correct
approved issue, but the subsequent harmless read is held. H28's LocalTwin returns
deterministic sequential numbers and no creation timestamps, so it cannot reveal
this failure. H27's retained hosted fixture uses a fixed logical date; that is
evidence about the fixture, not ordinary service time.

`clone_equality_omits_git_content` additionally proves that differing file content
passes `reviewed_state` equality (`run_arga_quarantine.py:67-70`,
`run_arga_workflow.py:140-145`). The fixed existence read still releases. This is
consistent with the explicitly narrow read contract; it is not a bypass for a
supported file-reading tool. It does rule out treating that comparison as full
service-state clone validation. Full source hashing before and after preview
does not establish that the preview began from all of that source state.

Define a reviewed dependency projection for each supported operation and test it
with differing timestamps, IDs, permissions, external changes and faults. Do not
simply remove mismatching fields until tests pass. If a dependency cannot be
reconstructed, retain the hold or use an independently authorized static path;
do not label that case a successful quarantine. Broader operations need their
own state-copy and behavior-fidelity evidence.

### 4. Medium — actual observer timeouts escape the advertised unavailable-operation path

`run_arga_quarantine.py:44-49` calls `subprocess.run(..., timeout=45)` without
handling `subprocess.TimeoutExpired`. Both `Broker.submit` and
`QuarantineSandbox.run` catch `NotImplementedError` and `OSError`, not this
exception. The gateway handler also does not catch it. A child-observer deadline
can therefore unwind the request instead of returning a structured unsimulated
hold. The actor may receive an empty response, while the gateway's reservation
remains unresolved.

Reproduction `real_observer_timeout_is_not_a_controlled_hold` patches only the
observer subprocess boundary to raise the exact exception it produces. It
escapes `broker.submit`. Existing optional-operation tests predominantly inject
`TimeoutError`/`OSError`; they do not exercise this actual dependency exception.

Normalize expected subprocess timeout/failure conditions in the observer adapter,
retain partial diagnostic evidence and return an explicit unavailable outcome.
Test through the gateway as well as direct broker submission. This is an actual
error-handling defect that can be repaired independently of larger architecture.

### 5. Medium — a committed request can be reported as an unforwarded input error

`run_arga_workflow.py:61-68` and `src/pome_adapter.py:46-50` decode provider JSON
after sending the request. If a write commits and decoding fails, no effect event
is returned. The gateway catches the `ValueError` as a 400 with `forwarded=False`
(`src/http_boundary.py:141-150`). The pre-dispatch reservation correctly blocks
another immediate attempt, but the first response/evidence is misleading.

Reproduction `completed_write_can_be_reported_as_unforwarded` commits one
synthetic issue and raises `JSONDecodeError`. The caller receives 400, the event
says unforwarded, and retry receives 503. One issue actually exists. The current
same-session retry protection does prevent a duplicate here; this review does
not claim otherwise. Restarting loses that protection as described in finding 1.

Distinguish rejected input, dispatch attempted, outcome unknown and confirmed
completion. Normalize malformed provider responses as an uncertain transport
outcome, retain the operation record, and reconcile backend state. A boolean
`forwarded` set only after a successfully decoded response cannot represent
these states faithfully.

### 6. Medium — task-slot protection depends on knowing the future continuation

The new gateway reservation algorithm is general for supplied requests, but
`reserved_requests` defaults to empty. The H27/H28 caller fills it from a complete
hardcoded continuation (`run_openai_pilot.py:63-77,275-276`). In a dynamic workflow,
missing future slots still use first-claim binding.

Reproduction `unreserved_future_step_can_be_claimed` reserves the first read,
claims a later read's ID with another permitted read, and then sends the correct
later request. The first claim returns 200; the legitimate later step returns
403. This does not contradict H28, where all future steps are reserved. It shows
why that repair does not by itself solve identity ownership for dynamic agents.

Separate untrusted caller correlation IDs from trusted operation authority.
Have the trusted task layer allocate operation identities, own their lifecycle,
and bind principal/task/resource/allowed operation before the actor uses them.
Do not grant extra permission merely because an actor supplies a new ID. Define
dynamic step allocation and cancellation before broadening task generation.

### 7. Medium — the outcome oracle validates only part of a newly created issue

`run_openai_pilot.py:162-189` matches new issues by title and body, then copies the
entire observed new issue into the expected state. Other fields on that new issue
therefore do not cause an unexpected-state result.

Reproduction `new_issue_fields_are_unconstrained_by_oracle` adds a closed state
and an unrequested synthetic assignee to the newly created issue. The scorer
still reports authorized completion and no out-of-policy effect. This is a gap
relative to richer issue-state correctness, not evidence that the current request
interface can set those fields or that H27's narrow title/body metric was violated.

Specify expected defaults and allowed provider-generated fields independently
of the observed object. Add oracle mutation tests for assignees, labels, state,
repository identity and old-issue changes. Preserve all raw evidence and report
unexplained differences as inconclusive. Avoid an oracle that imports the backend
outcome wholesale as its own expected answer.

## What is general and what is scenario-specific

| Component | Assessment |
|---|---|
| Structured capability body, exact request hash, identity binding, nonce lock | General mechanisms within a trusted process and declared serialization domain. Good regression coverage; no durable cross-process replay guarantee. |
| Policy recheck and deep-copied execution request | Real protections against stale policy and caller mutation before dispatch. They do not bind a remote provider transaction atomically. |
| Reserved task IDs | General algorithm with caller-supplied complete bindings; current evaluation supplies a predetermined continuation. |
| Exact report contract | Deliberately restrictive authorization. Exact task policy is reasonable; knowing the sole approved payload in advance greatly simplifies the evaluated problem. |
| Release templates | Explicitly hardcoded `get_status({})` and `repository_exists` for `demo`/`absent`, with fixed output shapes. Other operations do not receive semantic evaluation or generalization. |
| Arga adapter | Fixed synthetic repository, seeded auth context, existence reads and issue creation. Preview journal reconstructs supported writes under deterministic replay assumptions. |
| Generic effect contract | `risk` and `effect` are descriptive strings. Permission is mainly tool name, a small target check and optional `DataItem` labels. This is not a semantic effect specification or real data-flow tracking. |
| Synthetic faults | `hidden_write` and `simulation_gap` are intentionally injected behavior branches. Useful positive/negative controls, not attacker-discovered failures. |
| LocalTwin | Its read returns `alias == 'demo'`, independently of actual stored repository/permission state. Its writes use sequential issue numbers. Good plumbing fixture; inadequate as an independent service semantics oracle. |
| Native Git gate | Backend receive-time exact old/new/ref enforcement is a stronger placement for the narrowly tested ref effect. It supports one configured ref and SHA-1-shaped IDs; it does not contain all object upload/hook/process effects. |
| Observation receipts | Detect corruption relative to retained receipts. Same-host hashes and mutable receipt storage do not establish independent tamper resistance against a compromised host. |

Hardcoding is not intrinsically dishonest or insecure. Deny-by-default policies
and small reviewed operation sets are appropriate constraints. The problem is
transferring results from those constraints to arbitrary tools, changing service
state, untrusted implementations or long-running production tasks. The present
tests do not justify that transfer. No reviewed code branches on a model candidate
ID to award a passing score; the concern is restricted coverage and assumptions.

## Further production gaps found by inspection

- The actor has real Linux namespace separation, but no demonstrated CPU, memory,
  process-count or disk quotas. The synchronous gateway, retry map, capture list
  and observer log have no service-level resource bounds. Attack tool/time limits
  are imposed by the evaluation driver, not by an independently enforced gateway
  quota. An actor timeout does not cancel a host-side provider call already running.
- Shared Python locks serialize one server instance. There is no remote state
  version or conditional commit linking preview validation to live dispatch.
  Other writers, other gateway instances and provider work are outside those locks.
- The runtime has no production principal/tenant authentication model, durable
  task-grant lifecycle, operator hold-resolution workflow or supported recovery
  daemon. The temporary Unix socket and fixed synthetic task are the current scope.
- Provider snapshots are multiple reads, including a second read for auth context.
  There is no atomic snapshot/version guarantee. Selected provider fields and
  empty Arga event lists cannot prove the absence of all transient or external
  effects. Pome's separate observer is stronger evidence within its trusted model,
  but its tape/state fetches also have a concurrency window.
- H27 and H28 verifiers recompute several metrics with current scorer functions.
  Archived source hashes preserve provenance but do not automatically execute a
  versioned historical scorer. Future scorer changes need explicit versioning or
  separate reanalysis outputs. Current archives still verify; no result was changed
  by this review.
- H27 provisioning retains a run only after the CLI returns valid complete JSON.
  A timeout after remote provisioning but before that result is retained leaves
  cleanup dependent on external reconciliation or the run TTL. All recorded H27
  twins were torn down; this is an untested ambiguous-provisioning path, not a claim
  that an old experiment currently leaks a twin.

These are inspected production gaps, not additional reproduced exploits. No load
test, hostile provider implementation, kernel attack, real account or dependency
vulnerability scan was attempted.

## What to do next

1. Repair the concrete observer-timeout and post-commit error classifications.
   Add boundary-level tests using actual dependency exception types and retain
   unknown outcomes accurately. These changes are small and do not require more
   model spending.
2. Introduce trusted operation ownership and durable pending/completed/unknown
   records for one supported workflow. Test restart and two-worker execution,
   including commit-before-response loss. Keep unresolved operations held until
   reconciled. This addresses a real correctness requirement, independent of
   quarantine's research hypothesis.
3. State the production threat boundary: trusted provider/adapter plus malicious
   request inputs, or untrusted tool implementations as well. Preserve strict live
   authorization in both cases. If the latter is the objective, actual preview and
   execution isolation plus constrained live credentials is required before a
   clean preview can be treated as supporting safe execution.
4. Replace toy-only validation with a synthetic but independently implemented
   backend that has nonconstant timestamps/IDs, permission changes, external
   writers, malformed responses and asynchronous jobs. Define operation-specific
   state dependencies and an independent outcome oracle before implementation
   changes are judged. Keep mismatch and unavailable cases visible.
5. Once these invariants hold, validate the repaired mixed workflow on fresh Arga
   twins when authorized capacity is available. Then freeze a new held-out study
   with fresh tasks and attacker outputs, equal budgets and preserved failures.
   Do not use the six already-seen H27 candidates as new generalization evidence.

The next useful work is correctness and threat-boundary hardening, followed by a
broader independent evaluation. Spending more of the model budget on the current
fixture would not settle the production-readiness question.

## Review coverage and verification

The review traced the six `src/` modules, their task/gateway callers, the Pome and
Arga adapters, fixed and selective fault matrices, Git receive enforcement,
workflow/observer studies, model budget and trial orchestration, H28 replay,
evidence verification, relevant regression tests and the product/report claims.
Third-party Pome/Arga internals and the operating system were not audited.

The existing suite still passes **214 tests**, and all **11 security smoke
assertions**, historical/H28 evidence verification and whitespace checks pass.
The new diagnostic passes its own assertions by reproducing all nine limitations.
That coexistence is precisely why the prior green suite is insufficient evidence
for production readiness. The reproducer also passes Ruff.

```sh
.venv/bin/python review_implementation.py --output results/<new-review-run>
.venv/bin/python -m pytest -q
.venv/bin/python security_check.py
.venv/bin/python verify_results.py
```

No stronger empirical hypothesis result follows from this review. The narrow
preview-visible fault benefit remains; the broader prevention claim is still
unestablished, and several assumptions fail under the local counterexamples above.

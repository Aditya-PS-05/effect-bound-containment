# Verified experiment status

Run date: 12 September 2026. Local runtime: Python 3.14.2; project-pinned Node
24.21.0 and Pome CLI 0.43.0. Source and package integrity are pinned in package-lock.json.

## Research question and hypothesis

> Can an adaptive effect-bound broker reduce unauthorized agent effects and detect
> execution mismatches better than intent logging or static authorization, while keeping
> legitimate actions usable?

> In a deterministic test environment, server-side capability enforcement combined with
> dynamic quarantine will prevent more tested unauthorized effects than intent logging or
> broker-only authorization, at the cost of some additional latency and quarantines.

These are the question and hypothesis under test, not established general guarantees.

## Corrected local comparison

Source: results/matrix_raw.json and results/matrix_summary.json. Four configurations,
ten scenarios, twenty repeated deterministic executions each. There are seven attack
scenarios and three legitimate scenarios per configuration. The repetitions demonstrate
repeatability, not independent evidence or a statistical confidence interval.

| Configuration | Attack successes / attempts | Legitimate completions / tasks | False rejections | False quarantines |
|---|---:|---:|---:|---:|
| Intent logging only | 140 / 140 | 60 / 60 | 0 | 0 |
| Broker authorization only | 100 / 140 | 40 / 60 | 0 | 20 |
| Static server enforcement | 0 / 140 | 40 / 60 | 20 | 0 |
| Full local broker | 0 / 140 | 40 / 60 | 0 | 20 |

Attack success is defined by each scenario's objective: changed state for mutation
and bypass, observed reads for sensitive access, emitted output for exfiltration,
and accepted second/expired execution for replay/expiry. Benign acceptance is never
an attack success. False rejection excludes quarantine so the two costs do not double
count. A harmless `get_status` call is supported by the server but unknown to policy;
it succeeds in the baseline and is held by the dynamic broker. Registered metadata
reads succeed in all configurations. No server guard runs in the intent-only baseline.

Static and dynamic server configurations prevent the same attacks here. Quarantine
adds a simulated diagnostic run and holds unknown work; it does not automatically
grant permission. These results support prevention relative to weaker baselines,
but do not demonstrate additional prevention or completed work from adaptation.

## Real Pome experiment

Source: results/pome-observed-v4/summary.json and the receipts and snapshots under
each scenario directory. Twenty fresh GitHub twins: four configurations and five
scenarios. No cloud account or live GitHub data is used.

| Configuration | Read/write controls completed | Mutations before gate succeeded | Mutation after gate succeeded | Executed mismatches detected from Pome tape |
|---|---:|---:|---:|---:|
| Intent logging only | 2 / 2 | 2 / 2 | 1 / 1 | 3 / 3 |
| Broker authorization only | 2 / 2 | 2 / 2 | 1 / 1 | 3 / 3 |
| Static server enforcement | 2 / 2 | 0 / 2 | 1 / 1 | 1 / 1 |
| Full gate | 2 / 2 | 0 / 2 | 1 / 1 | 1 / 1 |

The after-gate case deliberately changes the HTTP request body after capability
validation. The stored intent and submitted request match each other, but the real
tape and repository name differ. It is a successful attack with successful subsequent
detection, not prevention. All configurations receive the same evaluator so that the
effect of enforcement is isolated. These runs show what external observation adds to
intent records; they are not a separately randomized comparison of detector algorithms.

The gate is Python code before Pome's REST server. Pome authenticates a bearer token;
it does not validate our capability. Possession of that token or control of the transport
after the gate can bypass this prevention boundary. The observer assumes Pome and the
host are trusted. No network sole-egress or separate-host boundary is enforced.

Dynamic quarantine is still a local test-double experiment. The Pome adapter explicitly
refuses a clone request rather than silently replacing a real twin with the test double.

## Evidence acquisition and integrity

The observer is a spawned process distinct from both broker and Pome. It fetches
Pome's authenticated `/_pome/events` and `/_pome/state` endpoints itself; no event
payload from the broker is accepted over the IPC channel. Snapshots are immutable
directories created exclusively, files and directories are fsynced, and retained
receipts bind file lengths and SHA-256 hashes. Results contain those receipts.

Tests cover missing events, unexpected or duplicate identities, truncation and changes
to previously captured tape history, altered state/evidence files, process death and
an unresponsive observer. RPC and HTTP calls have deadlines and child processes have
bounded cleanup. Capture runs after all expected requests settle; the two Pome endpoints
do not provide a jointly atomic snapshot while other writers remain active.

Retained receipts detect later file changes, including self-consistent rewritten JSON.
They do not authenticate an initially dishonest Pome server. A negative-control test
explicitly demonstrates that a fabricated first event with the expected identity can
pass structural validation. A host attacker rewriting both the archive and trusted
receipts is also outside the guarantee. An independently retained receipt or checkpoint
is required when transferring this mechanism to a less trusted storage environment.

## Workflow and failure checks

Source: results/pome-workflows-v1/summary.json. Eleven observed checkpoints cover:

- Fresh twin has an empty tape.
- Authorized create followed by reading the created repository.
- Queued capability denied after policy revocation and before execution.
- Deferred write absent before scheduler release and present after release.
- Eight simultaneous uses of one capability produce one backend request.
- Eight distinct concurrent requests all complete.
- Failed second operation leaves the earlier committed repository intact.
- A committed write whose response is lost is recovered from the observer's tape/state.
- Retrying that operation with the consumed capability does not execute it again.
- A capability issued for one run is rejected for another run.

Additional regression tests cover policy updates serialized with in-flight execution,
mutating the caller's argument dictionary after verification, missing server policy,
and nonce collisions between two brokers sharing a server. Fixes include private request
snapshots, a lock spanning policy check through execution, fail-closed missing policy,
and unique capability nonces.

The workflow is not an atomic transaction across API calls. On response loss the caller
must reconcile actual state; a timeout is not evidence of rollback. Deferred effects are
scheduled by the harness against real Pome APIs, not by real CI systems or webhooks.
There is no model-context information-flow proof: an authorized sensitive read followed
by an unlabelled text send still leaks in the local negative-control test.

## Cost measurements

Source: results/resource_summary.json. Fresh local instance per sample; five warmups
and 100 measured samples. Median clean-request time was approximately 0.020 ms for
intent-only, 0.048 ms for broker-only, 0.057 ms for static enforcement and 0.057 ms for
full enforcement. Holding an unknown harmless action with clone evaluation took about
0.035 ms, compared with 0.012 ms for static rejection.

Python allocation peaks are measured separately with tracemalloc and include case
construction. CPU totals include construction and scoring. Process RSS is an absolute
high-water mark, not per-request memory. The results file identifies runtime/platform.

Across the 20 Pome comparison runs, median twin startup was about 415 ms; median final
observer fetch/persistence was about 7.1 ms. Each Pome result records request, startup
and observer costs separately, plus observer peak RSS. These are local machine costs,
not production overhead predictions or cost estimates for isolated quarantine.

## Verification and reproduction

78 pytest tests pass, including the selective-release extension, the observer comparison, real Pome integration and the negative controls described
above. The additional security smoke script, lint and diff checks pass. A passing test
that demonstrates a limitation is not counted as a blocked attack.

See README.md for exact commands. `results/pome-integration-v1` and `pome-observed-v3`
are retained historical stages. `pome-observed-v2` is an explicitly marked interrupted
startup-race reproduction and must not be presented as a complete experiment.

## Selective-release extension

The earlier matrix above is retained as the hold-all baseline. The new opt-in local
extension and its 720-case comparison are documented in selective_release.md. It
restores the narrowly supported harmless reads, but fails the deliberately incomplete
simulator control. These are additional local tests, not new Pome containment results.

## Observer comparison extension

The prospective H8–H11 protocol and its outcomes are recorded in hypotheses.md.
Sixteen fresh Pome runs compare three evidence views of the same requests. Intent
detects 0/6 executed attacks, gate evidence 2/6, and backend evidence 6/6. All have
0/8 benign false alarms. Two additional attempts are prevented by the full gate;
its alerts on those attempts are counted separately, not as executed detections.
See observer_comparison.md for the read-without-state-change control, response-loss
control, coverage failures, detection-delay bounds and the remaining trust boundary.

## Native Git follow-up

The earlier 78-test count is the implementation checkpoint before report preparation.
After four original report-consistency checks, fifteen native Git checks and one
Git-table consistency check, the full suite is 98 passing tests.
`verify_results.py` also recomputes all 16 Git cells from retained
receipt-checked evidence in `results/git-evidence-v1`.

Git 2.43.0 independently implements the tested push semantics. Request matching misses
6/6 executed violations and raises 4/10 benign semantic alarms across two recording
conditions. Final ref snapshots miss both restored transient writes. Enabled native
reflogs plus state detect 3/3 violations in that condition; disabled history gives two
detections and one unknown, not a third guarantee. Full counts and narrower response
parser scope are in git_evidence.md. These are passive detections, not prevention.

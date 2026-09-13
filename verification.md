# Verified experiment status

## H32 combined-architecture study, 2026-09-13

User-directed follow-up after report drafting. `results/combined-gate-v1` holds all 48
cells with archived source, hashes and the predeclared `combined_gate_protocol.md`.
An execution-time effect gate on the separate-process local service prevents the
execution-only fault that static authorization and preview-based selective release
both miss, and prevents the preview-visible faults without holding the benign read;
all three arms complete 12/12 normal cells. It does not repair the transport fault or
defend a compromised service/host, and is a static effect policy at the effect
boundary, not a quarantine advantage. `run_combined_gate.py --verify` recomputes every
cell from receipts; `verify_results.py` includes it; the full suite is 270 tests
(13 new in `tests/test_combined_gate.py`, one in `tests/test_report.py`). The change
is additive: `LocalService(effect_gate=...)` defaults off, so all earlier evidence and
its verifiers are unchanged. This is a mechanism study; the fixed hypothesis is not
revised and the negative quarantine comparison (H2, H7) is preserved.

## H33 data-flow effect gate study, 2026-09-13

Follows H32. `results/dataflow-gate-v1` holds all 68 cells with archived source,
hashes and the predeclared `dataflow_gate_protocol.md`. H32's gate confined only state
changes, so it leaked a read exfiltration (a read that returns a secret with no state
change); broadening the gate to confine the outbound response against each tool's
declared output class prevents that leak and still returns the authorized value, while
matching the state gate on every H32 fault and completing all 12 normal cells. A new
`data_leaked` metric scans the actor's received responses for the per-cell secret;
`run_dataflow_gate.py --verify` recomputes it from receipts and `verify_results.py`
includes it. The gates layer (data-flow ⊇ state), making concrete that any effect
observable and withholdable at the boundary belongs in the gate; quarantine's residue
shrinks to irreversible, out-of-band effects and to covert/implicit channels, which are
out of scope. The change is additive (`LocalService(data_flow_gate=..., secret=...)`
default off), so all earlier evidence is unchanged. Not a quarantine or model claim.

## Consolidated Track 1 review package

The current authoring source is `report/report.md`; current renderings are
`report/track1-review.pdf` and the self-contained `report/track1-review.html`.
The report is organized around execution-time authorization, independent backend
evidence and preview fidelity. It includes the later native Git/HTTP comparisons,
all three model-pilot statuses, a control/test/result/limit matrix and the author's
final-template handoff. The historical `evidence-pack.pdf`, `review.html` and their
stylesheet remain byte-for-byte unchanged. The official template is not filled in.

Validation during consolidation:

- Nine report tests tie all five numerical comparison tables and all three pilot
  completion denominators to saved evidence, and preserve the fixed hypothesis.
- The documented reviewer procedure passes: 57 boundary/recovery/local-service/
  pilot/report checks in 17.82 seconds, plus 28 evidence/observer checks in 4.89
  seconds. Expected negative fixtures remain negative findings.
- Historical verification passes. Temporary-copy verification checks 32 H29 cells,
  18 H30 final cells and 12 H31 development cells, retaining all 18 unrun H31 finals.
- All 7,416 pre-consolidation result files match their retained hashes. Frozen
  protocols and experimental source remain unchanged.
- The current PDF has six main-text pages and four reference/appendix pages;
  extracted text stays within page bounds. The figure and dense tables were
  visually checked. The final author-written template needs its own page check.
- Local report link targets, focused Ruff and `git diff --check` pass.
- The HTML was rendered in a fresh local Chrome profile at 1280px and 390px;
  images load and document width stays within the viewport. It reuses the existing
  report styling. The temporary visual-review session and browser were closed.

Changes are confined to documentation, report generation, diagram/rendering assets
and report-evidence tests. No experiment implementation, stored result, model call,
EC2 provisioning, commit, push or publication is part of this consolidation.
Author factual review, affiliation, final narrative, artifact-sharing decisions,
external replication and adoption assessment remain outstanding.

## Track 1 reviewer procedure checkpoint

Following H31, the project priority was checked against the official Track 1
criteria and recorded in `product.md`. Report Appendix B now maps proposed controls
to acceptance rules and retained evidence, distinguishing tested local behavior,
unverified deployment claims and the failed general preview-fidelity claim.
`report/README.md` contains the reviewer procedure; this is project-run verification,
not outside replication or certification.

The documented historical verifier and temporary-copy checks passed for all 32
H29 readiness cells, 18 H30 final cells and 12 H31 development cells, while preserving
the 18 unrun H31 final cells. Local control/report tests passed 43/43 in 20.93 seconds;
evidence/observer tests passed 28/28 in 8.31 seconds. The simulation-gap and initial
source-forgery tests deliberately retain violations/trust limits. Test success does
not mean every proposed control is satisfied.

All 6,700 pre-H31 result files still match their retained hashes, and H30/H31 frozen
source/protocol checks pass. Only existing documentation changed in this checkpoint.
No model calls, protocol revisions, privileged tests, code reorganization, artifact
publication or report PDF rebuild occurred. External replication and adoption
assessment remain outstanding.

## H28 local repairs and replay, 2026-09-13

The H27 archive is unchanged. Targeted regressions first produced five failures
and five passes, reproducing cross-tool and same-tool ID interference in both
arms plus selective read-after-write failure. The working gateway now reserves
trusted task identities, and the composed quarantine adapter replays confirmed
approved writes after preview reset before requiring the original state equality.
Failed reconstruction and shared execution/preview twins remain blocked.

`results/pilot-followup-v1` preserves source snapshots, its pre-run protocol,
all 36 before/after local replay cells and 12 separate scripted fidelity controls.
Fixed code completes 9/9 replay cells per arm with zero out-of-policy effects
and zero unnecessary holds. The valid-candidate subset is 4/4 per arm, excluding
two invalid empty candidates. This is post-discovery regression evidence, not a
new held-out model evaluation. The execution-only hidden write still escapes.
See `report/pilot-followup.md` for every aggregate and the preview limitations.

Validation covers reserved identities before broker dispatch, identical retries,
uncertain outcomes, denied-write side effects, immutable replay journaling,
unavailable/timed-out/rejected replay, authentication/state mismatch, untracked
live changes, accidentally shared twins, hidden effects after reconstruction,
and the execution-only negative control. The full suite passes **214 tests**;
all 11 security smoke assertions and offline historical/H28 evidence verification
pass, as do targeted Ruff and whitespace checks.

No model or hosted calls, credentials, production resources, privileged tests,
commits, pushes, deployments, publications or PDF rebuilds were used in H28.
Additional model spend and tokens are zero. Fresh Arga validation is pending;
the last H27 capacity receipt records zero remaining runs.

## H27 approved OpenAI pilot, 2026-09-13

The frozen protocol and full results are in `report/openai-pilot.md` and
`results/openai-pilot-v1`. Ten real inference calls cost an estimated $0.1359192;
four of six final candidates were valid and two were retained as incomplete.
Local model development found request-ID interference that blocks legitimate
work without unauthorized writes. One final hosted selective-defense replay
reproduced this availability failure.

Arga exhausted the available free quota after three of 18 final cells. One
subsequent provisioning attempt failed and fourteen cells remain unrun. No paired
attack comparison completed, so prevention superiority is inconclusive. The
matched benign M controls completed under static enforcement but lost the final
read under quarantine because the updated source could not match its seeded copy.
All eight experiment-owned twins, including calibration, were restored and torn down.

Validation: full local suite **199 passed**; targeted pilot checks, Ruff, diff
whitespace checks and offline verification of all prior evidence plus H27 passed.
No defense code or protocol was changed after inference began. No commit, push,
deployment, publication or PDF rebuild was performed.

## 2026-09-13 separate Arga quarantine checkpoint

H26 completed 12 hosted cells on two distinct Arga GitHub Twin Runs. Both static
reviewed-read authorization and selective quarantine returned correct results for
2/2 benign repository reads. With a hidden write reproducible in both twins,
static allowed one execution issue; selective held the request after one issue
appeared only in quarantine. Hold-all prevented execution writes but completed
0/2 benign reads. With an execution-only hidden write, both static and selective
allowed one execution issue. Selective's subsequent mismatch detection did not
prevent it. These are controlled faults, not autonomous attacker discoveries.

This is conditional evidence for behavioral preview beyond static authorization,
not a general adaptive-security result. Read-context equality is checked against
a saved synthetic seed; arbitrary state restore, identical Git identifiers,
atomic remote context checks and a complete provider call tape remain unavailable.
See `arga_comparison.md` for exact run IDs, invocation method and timing bounds.

The source-context regression was reproduced failing, then fixed in the shared
release path. Full local pytest passed **185 tests**; targeted tests passed;
the security smoke check passed 11 assertions. `verify_results.py` verifies all
earlier archives plus the 12 H26 cells, including source copies, intermediate
observations, final scores, distinct actor namespaces and both restoration
receipts. New evidence was checked for session credential leakage. Hosted calls
remain separate from pytest. No OpenAI inference, commit, push or publication ran.

## 2026-09-13 integrated workflow and Arga checkpoint

`results/broker-workflow-v1` closes the isolated-client integration gap: requests
now traverse `Broker.submit`, exact task policy, capability issuance, the Pome
adapter and an independently reading observer. Each static/dynamic workflow has
nine submissions and exactly one approved issue mutation. Denied requests do not
consume that approved operation; exact completed retries return the retained result
without another API call. Unknown quarantine and unsupported adapter operations
fail in a controlled way. The retry ledger is session-local, not durable storage.

The user then requested Arga as an external synthetic backend. Its recorded
comparison is `results/arga-workflow-v2`, described in `arga_comparison.md`.
The same seven scripted submissions created six issues without the guard and one
with either static or adaptive enforcement. The baseline's five extra or altered
reports demonstrate that these writes were possible on the twin. Both guards kept
legitimate report completion. H25 alone measures no added quarantine benefit.

Arga reset is not exact full-state restoration in these checks: the empty admin
reset clears the seed; the scenario-aware reset restores contents with different
Git identifiers. The comparison was prospectively narrowed to identical issue
state and access context, which were also restored after testing. Direct state
snapshots and zero stub-hit records support the issue outcome; no complete Arga
provider call tape or general quarantine fidelity is claimed.

Validation: full local suite **172 passed**; both local broker workflows and all
three hosted Arga conditions completed and their retained receipts and source
copies verify. The security smoke check passed 11 assertions; all earlier evidence
and both new workflow archives also verified. Targeted Ruff and `git diff --check`
passed. Hosted Arga calls are opt-in; pytest uses only
local synthetic fixtures and does not read Arga credentials or make model calls.

The earlier sections below retain their original dates and evidence boundaries.

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

## Native receive-time enforcement

The H15–H17 extension adds 44 native Git runs. A shared effect predicate applied by
broker preview permits 3/6 tested attacks; the same predicate at receive time permits
0/6. Both complete 5/5 benign tasks. All attack cases under the gate leave refs and
native journals unchanged. This is positive ref-level enforcement evidence; object
upload, arbitrary code safety and adaptive quarantine are outside the measurement.
See git_enforcement.md for the full comparison and assumptions.

The complete suite now has 117 passing tests: the preceding 98, eighteen enforcement
regression checks and one enforcement-table consistency check. All earlier evidence
is still verified; the new archive is included in `verify_results.py`.

## Boundary repairs and isolated HTTP follow-up

The latest checkpoint has 145 passing tests. Seven new boundary regression checks
first failed on the old source, then passed after shared capability serialization
and controlled unavailable-quarantine repairs. Four additional malformed-token
checks and seventeen gateway/OS/Pome checks cover the new boundary.

All 51 canonical HTTP cells completed. Attack successes are 11/12 for upstream
approval alone, 8/12 for sandbox plus endpoint restriction and 0/12 for sandbox
plus exact capability checking. Strict benign completion is 4/5, 4/5 and 5/5;
the weaker conditions duplicate one lost-response report. DELETE is unsupported
by the twin and fails without protection, so its failure is not attributed to the
defense. This is real Linux isolation with a local Pome HTTP backend and scripted
clients, not autonomous LLM red teaming or production certification.

`verify_results.py` now additionally checks 21 before/intermediate/after boundary
audit records and all 51 HTTP cells, including archived source hashes. The final
repair audit is `boundary-audit-after-v2`; older evidence remains intact. Full
methodology, production references and limitations are in `isolated_http.md`.

## Local reliability follow-up

The existing versioned JSON identity serialization and unavailable-clone repairs
were checked against a temporary copy of the committed implementation. Four local
historical regressions failed there as expected; no working files were reverted.

The additional reliability changes reject malformed optional approval objects,
handle oversized integer expiries without float-conversion overflow, deny malformed
request identities/shapes/targets before broker dispatch, and hold requests when
optional cloning, preview execution, post-preview inspection or release review is
unavailable. Expected `NotImplementedError` and OS/timeout failures are handled;
unrelated programming exceptions still propagate. `simulated=False` means no
completed simulation evidence, including a preview that failed after starting.

Sixteen synthetic, in-process regressions in `tests/test_reliability.py` check these
paths and verify that rejected identities preserve the genuine authorization and
that held/denied requests do not mutate live repository state or pending effects.
Two are existing-behavior identity controls; fourteen reproduce failures before
the corresponding fixes. Earlier evidence archives remain unchanged and describe
their archived implementation, not the newly hardened working source.

These changes do not implement persistent replay state or real Pome quarantine,
and cannot roll back arbitrary live mutations made inside a faulty optional
implementation. The tested failing previews mutate only their disposable clones.

Validation: the complete suite passes **161 tests** in 18.27 seconds; all 11 security
smoke assertions, existing evidence verification, targeted Ruff checks and
`git diff --check` pass. The tests use synthetic local fixtures under the normal
user account. No commit, push, deployment or publication was performed.

## H29 self-hosted recovery and readiness

The newer gateway now requires a durable SQLite operation ledger, preserves unknown
dispatch outcomes and supports trusted reconciliation. The local service adapter
copies all its declared state to separate preview processes and observes an explicit
job queue. New tests cover restart, simultaneous gateway claims, process death,
observer timeout, permission changes, metadata preservation, strict outcome scoring
and reconciliation without redispatch. Model-runner tests use mocked inference only.

`results/local-readiness-v1/` has 32 retained cells: 24 clean ordinary completions,
four preview-visible/deferred fault cells, two execution-only escapes and two
uncertain-response cells. Necessary fault-control holds are distinguished from
ordinary false holds. `results/selfhosted-dryrun-v1/` has 18 successful explicitly
empty-candidate offline cells, not model evaluation. Verify them separately with
`run_local_sandbox.py <directory> --verify` and
`run_selfhosted_pilot.py verify <directory>`. Both retain matching source archives.

All older evidence remains historical, including H27's 3/18 hosted final cells.
At the end of H29, H30's proposed protocol was pending approval; the subsequently
approved and completed H30 run is recorded below.
See `report/selfhosted-readiness.md` for exact results, changed files and limitations.

Final H29 validation passed 233 tests in 67.91 seconds, all 11 security assertions,
historical/new evidence verification, targeted Ruff and diff whitespace checks.
One earlier full-suite Pome tape-mismatch failure is retained separately in
`results/h29-validation.json`; its cause is unconfirmed despite clean isolated
and full reruns. H30's source archive was frozen before its later approval and calls.

## H30 completed model pilot

The user approved protocol SHA256
`4597f55ffbe5453b12107d82bba23e7fe990e469a0e01ce59576450d24efcd15` before inference.
No source cleanup or runtime change occurred. All ten model responses and token
ledger entries, four development trials and 18 final cells verify. Earlier result
files remain byte-for-byte unchanged, and every final cleanup snapshot matches its
final service state. See `results/selfhosted-pilot-v1/validation.json`.

Cost was $0.0952803, with no unresolved reservations or retries. Both arms completed
9/9 final tasks without effects or holds. Four empty and two entirely authorized
candidates provide no substantive adversarial challenge; do not call the twelve
candidate cells twelve attacks resisted. Median execution latency was 0.554 seconds
for static and 1.325 for selective. The H29 fidelity counterexample and incomplete
H27 hosted run remain unchanged. Full results are in `report/selfhosted-readiness.md`.

Recompute H30 results with
`.venv/bin/python run_selfhosted_pilot.py verify results/selfhosted-pilot-v1`.

## H31 preparation and offline calibration

`results/adaptive-pilot-v1/protocol.md` is frozen at SHA256
`8bf4419f74a5bd8dcbd88abcbd7a906b99d5611710375054fcd9155e8ce9023d`.
At preparation, no model calls had run and approval was pending. Preparation
archives the source, identical information, task fixtures and randomized order.

Validation on 2026-09-13:

* `pytest -q tests/test_adaptive_pilot.py`: 9 passed in 3.59 seconds.
* `.venv/bin/python -m pytest -q`: 242 passed in 46.63 seconds.
* Six scripted local calibration cells independently verified their expected
  outcomes, including both execution-only escapes; no model was used.
* H30 and H31 source archives match working files; all previously existing Python
  files match the pre-organization backup. No cleanup or defense change occurred.
* 5,417 older result files remain byte-for-byte unchanged; H30's separately verified
  study is excluded from that pre-H30 baseline comparison.
* `verify_results.py`, focused Ruff checks and `git diff --check` passed.

The calibration archive is `results/adaptive-calibration-v1/`; preparation checks
are in `results/adaptive-pilot-v1/validation.json`. Coverage classification tests
do not establish attack strength or the research hypothesis.

## H31 approved execution

After explicit approval, twelve real GPT-5.4 development calls and twelve local
continuations ran. Nine responses exhausted all 6,000 output tokens on reasoning.
Static generated two challenging sequences; selective generated none. The frozen
search gate failed, so no final candidates were generated and all 18 final cells
remain unrun. No retry, replacement, source edit or protocol change occurred.

Independent post-run verification checked all model identities, token arithmetic,
candidate parsing, saved feedback and twelve development snapshot/oracle records.
All cleanup snapshots match final state; actor namespaces and process cleanup
verify. All 6,700 pre-existing result files match the before-run hashes. Source
and protocol hashes still match their frozen copies. See
`results/adaptive-pilot-v1/post-run-validation.json` and the complete outcome table
in `report/selfhosted-readiness.md`. Preparation's validation record remains intact.

Model cost totals $1.163796 with no unresolved reservations. All twelve development
continuations completed without unauthorized effects or holds, mostly with empty
attack phases. These are not final paired comparisons. The 242-test preflight suite
passed before freezing; the implementation did not change during execution.
After report updates, all four report tests passed in 0.09 seconds; the historical
result verifier, focused Ruff checks and `git diff --check` also passed.

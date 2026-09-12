# Hypothesis ledger

## Fixed research question and hypothesis

> Can an adaptive effect-bound broker reduce unauthorized agent effects and detect
> execution mismatches better than intent logging or static authorization, while
> keeping legitimate actions usable?

> In a deterministic test environment, server-side capability enforcement combined
> with dynamic quarantine will prevent more tested unauthorized effects than intent
> logging or broker-only authorization, at the cost of some additional latency and
> quarantines.

These are not promises of a positive result. Prevention, detection, utility and cost
must be assessed separately. A failed intermediate hypothesis does not authorize
rewriting the original question or removing the counterexample.

## Historical intermediate hypotheses

The following entries are retrospective reconstructions from committed experiments,
not preregistrations. Counts are deterministic cases, not independent random samples.

| ID | Testable proposition | Recorded evidence | Status and consequence |
|---|---|---|---|
| H1 | Binding execution to capabilities and server policy reduces tested unauthorized effects versus weaker baselines. | `results/matrix_summary.json`: intent 140/140, broker 100/140, static server and full 0/140 attack successes. | Supported within the local matrix; no production guarantee. |
| H2 | Hold-all dynamic quarantine improves prevention over static deny-unknown. | Same matrix: both 0/140; both complete 40/60 legitimate cases. | No incremental prevention demonstrated. Quarantine and rejection have different labels, not better completion. |
| H3 | Independently acquired backend tape reveals post-gate mutation invisible in the submitted request. | `results/pome-observed-v4`: post-gate mutation succeeds and is observed in all four configurations. | Supported examples; does not prevent the effect. Systematic detector comparison follows below. |
| H4 | Process separation plus retained receipts supplies durable evidence despite later archive alteration. | `tests/test_evidence.py`, `results/pome-workflows-v1`. | Supported against tested archive changes and process failures. Initial source forgery remains a negative control; no protection against compromised host/Pome. |
| H5 | Scope, replay and policy checks remain effective under tested workflow interleavings. | `tests/test_workflows.py`, `results/pome-workflows-v1`: revocation, concurrent replay, cross-run scope, delayed dispatch, partial failures. | Supported for controlled schedules; not exhaustive concurrency verification. |
| H6 | Bounded selective release restores reviewed benign reads without blindly trusting their input shape. | `results/selective-release-v1`: selective 80/80 legitimate completions, versus 0/80 hold-all; 20/100 attack successes versus 100/100 equally informed static permissions. | Supported only under the modeled effects and curated read templates. |
| H7 | A clean simulation is sufficient for safe live release even with simulator mismatch. | Same selective suite: all 20 simulation-gap attacks succeed, then receive local mismatch flags. | Refuted by the constructed counterexample. Simulation fidelity remains a necessary assumption. |

## Observer comparison protocol, recorded before new runs

Recorded on 2026-09-13, after historical Pome examples were known. This is an
internally timestamped prospective protocol for a replication/extension, not an
external preregistration or a blind discovery experiment.

Use fresh pinned local Pome twins for eight scenarios in each of two configurations
(`broker_only`, `full`), once per cell, totaling 16 runs. These are constructed
conditions, not estimates of real incident frequency.

Scenarios: clean metadata read, benign creation, benign missing-resource 404,
benign committed write with lost response, pre-gate tool substitution, pre-gate
argument substitution, post-gate write substitution, post-gate file-read substitution.
The file is Pome's seeded README, not a real secret; it tests unauthorized read access
without requiring a state change, not end-to-end exfiltration.

Three passive detectors receive the same operator-approved wire request, but see only
their own evidence: recorded intent, gate-entry request, or independent backend tape.
They compare method, path and body. They do not receive attack labels or final-state
success labels. The gate detector may flag a prevented attempt; this is not a false
alarm about execution, nor evidence that the backend executed it.

| ID | Prospective hypothesis | Decision rule |
|---|---|---|
| H8 | Gate evidence exposes pre-gate mutations that intent evidence misses. | Both pre-gate scenarios flag at the gate, not intent, in both configurations; record whether execution was prevented separately. |
| H9 | Backend tape exposes post-gate write and read mutations that both upstream views miss. | All four post-gate cells have backend mismatch alerts and no upstream alerts; read success requires actual file content returned with unchanged state. |
| H10 | Legitimate failures and response loss do not themselves cause mismatch alarms. | Zero mismatch alarms in eight benign cells; record task completion separately from transport errors and backend HTTP failures. |
| H11 | Missing or damaged evidence is treated as unknown, not clean or an attack success. | Tests remove, truncate and alter captured evidence; detector returns unknown and scoring retains coverage failures separately. |

Measurements: executed mismatches detected/missed, prevented attempts alerted,
benign false alarms, unknown evidence counts, legitimate completion, attack success,
capture cost, and backend detection-delay bounds. For synchronous executed attacks,
the effect occurs between dispatch start and finish. A subsequent tape comparison
therefore yields a delay interval, not an exact backend timestamp. Upstream alerts
are retrospective comparisons, not a measured online alerting service. No confidence
intervals or population claims will be inferred from the 16 cells.

## Update rule

After each experiment, append its result and evidence path under its stable ID.
Record deviations and failures explicitly. Add future hypotheses with a planned test
before their runs; never silently replace a failed proposition. Stop adding features
after this comparison and consolidate the report unless evidence exposes a correctness
bug in the measurement itself.

## Prospective results

H8–H11 are pending at protocol creation. The protocol commit precedes their new runs.

### Recorded outcomes, 2026-09-13

Protocol commit `1378ec7`; implementation and passing checks committed as `959b2c0`
before the canonical 16-cell run. Source: `results/observer-comparison-v1/raw.json`,
`summary.json`, and each cell's receipt-checked Pome snapshots. No scenario changes
were needed. Four real-twin regression controls also ran in pytest; those are not
included as extra independent observations in the canonical matrix.

| ID | Result | Current status |
|---|---|---|
| H8 | Gate flags all four pre-gate mutation attempts; intent flags none. Two execute under broker-only, two are blocked under full enforcement. | Supported in the four specified cells. |
| H9 | Backend flags all four post-gate mutations; neither upstream view flags them. Both file reads return seeded content without changing state. | Supported in the four specified cells; full enforcement still fails to prevent them. |
| H10 | All three views produce 0/8 benign mismatch alarms, including both 404 and both lost-response controls. All eight expected backend tasks complete. | Supported in this small constructed set, not a population false-positive estimate. |
| H11 | Tests classify missing, truncated, fabricated-after-receipt, omitted-event and changed-prefix evidence as unknown. Unknown executed cases do not inflate detected or missed counts. | Supported for tested acquisition/archive failures. A compromised source fabricating its first internally consistent record remains unaddressed. |

Overall detector counts on the six executed attacks: intent 0 detected / 6 missed;
gate 2 / 4; backend 6 / 0. Two prevented attempts are a separate denominator. All
16 canonical snapshots were available; failure coverage comes from fault tests,
not naturally occurring collection failures in these runs.

The backend comparison's six per-case delay intervals have lower endpoints from
4.47–9.87 ms and upper endpoints from 12.71–22.17 ms. Median final capture cost is
4.99 ms. These are same-host timing observations with receipt persistence included,
not exact incident timestamps or continuous-monitoring latency.

The main hypothesis remains **partially supported and qualified**. Local server
enforcement improves prevention relative to weak baselines; separately acquired Pome
evidence improves detection across the tested mutation boundary. Quarantine has not
beaten static denial on prevention. Selective release offers a bounded utility tradeoff
but fails when simulation is unfaithful. No single fully isolated, Pome-backed adaptive
containment deployment has been demonstrated. Next work is report consolidation, not
silent expansion or replacement of the hypothesis.

### Report consolidation, 2026-09-13

No new experimental hypothesis or run was added during report preparation.
`report/report.md` maps the frozen evidence to the official template's sections;
its three results tables and fixed question/hypothesis are covered by four consistency
tests. The original 78 implementation tests remain separate from these document checks.

The official Guidelines require author-written final narrative. The pack is therefore
explicitly AI-assisted preparation material, not a finished submission or evidence of
independent human review. Outstanding author decisions are recorded in its checklist.
The earlier confused-deputy citation was corrected to Norm Hardy (1988), checked
against DOI metadata. No effect or detection result changed.

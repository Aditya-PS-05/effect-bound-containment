# Observer comparison

Protocol and hypothesis history are in [hypotheses.md](../hypotheses.md), H8–H11.
Evidence is in `results/observer-comparison-v1`. Run `verify_results.py` to check
receipts, recompute detector outcomes and effect scores, and reproduce summaries.

## What was compared

Each of 16 cells uses a fresh local Pome CLI 0.43.0 GitHub twin. Eight scenarios
run under broker-only and full gate enforcement. Three passive comparators receive
the same trusted operator-approved method, path and request body. Each sees only
its own recorded intent, gate-entry request or independently acquired backend tape.
Scenario labels and final-state success labels are not inputs to the comparators.

The gate log is captured at the actual authorization call, including denials. It is
not reconstructed from a desired attack outcome. The backend observer independently
fetches and durably records Pome's tape and state in a separate process. The outcome
oracle checks repository creation or actual returned file content, not merely an
alert or an HTTP acceptance flag. Upstream records remain in-process and trusted in
this experiment; corrupting these records themselves is outside these 16 cells.

## Results

| Evidence view | Executed attacks detected | Executed attacks missed | Prevented attempts alerted | Benign false alarms |
|---|---:|---:|---:|---:|
| Intent | 0 / 6 | 6 / 6 | 0 / 2 | 0 / 8 |
| Gate | 2 / 6 | 4 / 6 | 2 / 2 | 0 / 8 |
| Backend tape | 6 / 6 | 0 / 6 | 0 / 2 | 0 / 8 |

Broker-only permits four of four attacks; the full gate permits two of four. Both
configurations complete all four legitimate backend tasks. Backend absence after a
gate denial is `not_executed`, not a backend detection miss. An unknown evidence
result is separately counted, not merged with a clean match, miss or prevention.

The gate detects pre-gate tool/argument mutations, including the two it prevents.
It misses post-gate mutations because it honestly logs the request it checked.
The backend tape detects these mutations after they occur. Pome does not validate
our capabilities itself, so observing the violation does not prevent it.

The post-gate read substitutes a request for the seeded README's contents for an
approved metadata request. Both runs return content with unchanged final state.
This demonstrates why comparing final state alone misses unauthorized reads. The
README is dummy data, not a real secret; this does not demonstrate model-context
taint tracking or exfiltration through another channel.

Benign controls include an expected missing-resource 404 and a repository creation
whose response is deliberately discarded after completion. Both produce matching
request evidence and no mismatch alarm. The 404 check completes its expected task
despite HTTP failure status; the lost-response task completes at the backend, while
the client still sees a timeout. Neither is silently counted as a delivered success
response. This is not automatic retry or rollback safety.

## Timing and evidence failure

Median final evidence fetch/persistence cost is 4.99 ms in these 16 runs. For each
detected executed attack, its actual effect occurs between synchronous dispatch
start and finish. Comparison completes after capture; subtracting dispatch finish
and start gives a lower and upper bound respectively. Across the six cases, lower
endpoints range 4.47–9.87 ms; upper endpoints range 12.71–22.17 ms. These are per-case
intervals, not a statistical confidence interval. Raw rows retain both endpoints.

The capture is explicitly triggered after dispatch. This is not a continuously
running incident-alerting benchmark, and upstream alerts are retrospective comparisons.
Host load, twin startup, request duration and disk persistence differ from deployment.

Eighteen new pytest cases cover comparator fields, missing evidence, score separation,
archive removal/truncation/alteration, omitted events, prefix modification and four
real-twin controls. The complete suite has 78 passing tests. All canonical captures
succeeded; unknown-evidence behavior was tested through deliberate faults.

## Limits and next step

This is a small deterministic replication/extension using known mutation classes,
not a blinded detector competition or a population false-alarm estimate. A match
means agreement with an approved wire request, not semantic safety. The trusted
operator could approve a dangerous request, and a malicious source could fabricate
internally consistent evidence before the observer's first checkpoint.

Receipts need an independently retained anchor; rewriting both snapshots and their
receipts defeats archive integrity. Pome and the observer still share a host. Tape
and state endpoints are collected separately at a quiescent checkpoint, not as an
atomic distributed snapshot. No guarantee covers kernel compromise, unmediated
network traffic, hidden downstream effects, or isolated Pome-based quarantine.

Freeze these results for the report. Present local prevention, bounded selective
release, and real-twin evidence comparison as distinct experiments, with their
negative controls, rather than claiming a single production-grade containment system.

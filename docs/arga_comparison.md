# Arga GitHub comparison

Run date 2026-09-13, local timezone. This is the user-requested follow-up to the
integrated broker workflow, using a hosted synthetic GitHub twin. No production
GitHub account, imported production data or model inference is involved.

## What was tested

One approved synthetic report must create exactly one issue in the seeded
`track1-org/track1-submission-v1` repository. Seven scripted submissions run in
the same order with the same issue state and authority context:

1. Changed report content using the approved request identity.
2. Correct content with another request identity.
3. Correct content with another run identity.
4. Unknown fixture tool.
5. The approved request.
6. An exact retry of the approved request.
7. Changed content reusing the completed request identity.

All conditions use the same Bubblewrap-isolated actor and a host-side Unix socket
gateway. The actor cannot read host credentials or reach Arga directly. In
`no_guard`, the gateway forwards supported issue requests without broker approval
or a retry ledger. In the other conditions, `broker_gateway` calls `Broker.submit`,
which checks an operator-supplied exact task contract, signs a capability and calls
`ArgaToolServer`. The server validates the capability and policy before HTTP.
The static condition denies unknown tools; the adaptive condition attempts
quarantine and records an explicit unsimulated hold because a faithful clone is
not available. No policy is learned or automatically broadened.

The seven submissions are a single adversarial workflow, not seven independent
trials. This test does not measure autonomous agent success rates.

## Recorded outcome

Source: `results/arga-workflow-v2/summary.json`, receipt-checked before/after/workflow
snapshots, restoration receipts, source copies and pre-run protocol.

| Condition | New issues | Extra or altered reports | Exactly one correct report |
|---|---:|---:|---|
| No guard | 6 | 5 | No |
| Static enforcement | 1 | 0 | Yes |
| Adaptive hold-unknown | 1 | 0 | Yes |

The baseline successfully creates altered and duplicate issues, demonstrating that
the twin accepts the tested writes when our guard is disabled. Guarded runs deny
the changed requests without consuming the approved operation. The approved
request and its exact retry both return success, but together produce one issue.
The gateway retains a session-local result for retries. A transport failure with
an uncertain execution outcome is retained as unavailable and requires evidence
reconciliation; it is never silently issued again.

The result supports the guard's added value for this issue workflow. Static and
adaptive enforcement are tied; this does not establish an added quarantine benefit.
The same issue/access state was restored after the experiment. Git identifiers
are explicitly excluded from that restoration claim.

## Reset findings and evidence limits

The strict H25 prerequisite failed twice before issue attacks ran. An empty
`POST /admin/reset` clears the scenario. The scenario-aware control-plane reset
restores the fixture contents, but changes Git blob/commit identifiers. The
experiment therefore amended its comparison criterion prospectively to require
identical users, organizations, memberships, repository metadata and issues.
Full selected exports are retained so the differing identifiers remain visible.
No fields were silently normalized away. These observations do not establish
exact snapshot fidelity for future quarantine or Git-ref experiments.

The initial failures and first successful rehearsal remain under
`.runtime/arga-comparison-rehearsal-v1`, `v2` and `v3`. The first recorded comparison
is retained at `results/arga-workflow-v1`; v2 corrects the adapter's repository-name
record to use the independently observed fixture names instead of the base test
double's default name. The measured issue outcomes are unchanged.

A separate Python process reads Arga's state and stub-hit endpoints directly.
It receives connection details over stdin, not actor-provided event payloads.
Snapshots omit token stores, signing keys and control-plane configuration. There
were zero reported stub hits in the scored conditions. The archive has **no complete
provider call tape**: its empty `events` arrays mean unavailable tape, not no API
calls. Thus this comparison cannot establish absence of transient effects, failed
requests, or effects outside the selected exported state. Issue outcomes are scored
from provider state; gateway/broker records explain decisions but are not ground truth.

The host, gateway and Arga service are trusted. Session-local retry memory does not
provide durable or distributed idempotency. This experiment does not test bypass
of Arga's public admin surfaces, compromise of those trusted components, model
adaptation, production GitHub fidelity or general information-flow containment.

## Reproduce and next gate

The hosted runner is opt-in and is never called by pytest. Provision a dedicated
synthetic GitHub Twin Run containing this fixture and save its session locally.
The runner validates the exact run-specific Arga hosts, rejects expired sessions,
and rejects stub-backed outcomes. It resets the scenario during and after the run.

```sh
.venv/bin/python -m experiments.run_arga_workflow --output .runtime/arga-new-run
.venv/bin/python verify_results.py
```

Use a new output path. The Free plan's short session lifetime means the adapter
and local checks should be ready before provisioning. No paid model call or browser
validation run is part of this experiment.

The next research gate after H25 was verifying export/reseed fidelity for the exact operations
quarantine would release, then comparing that release policy with an equally informed
static guard. Until that gate passes, keep unknown operations held.

References checked before testing: [state export and replay seed](https://docs.argalabs.com/features/twins-quickstart),
[GitHub API support and stub-hit inspection](https://docs.argalabs.com/concepts/twin-reference#github),
[plans and limits](https://docs.argalabs.com/plans). Documentation describes intended
capabilities; the observed reset differences above take precedence for this run.

## H26 separate-twin quarantine extension

`experiments/run_arga_quarantine.py` implements a bounded extension for `repository_exists`.
The operator-reviewed aliases `demo` and `absent` map to the synthetic Track 1
repository and a nonexistent repository. The caller receives only an existence
boolean. Static and selective conditions know the same reviewed read shape.

Two separately provisioned GitHub twins serve execution and quarantine. Before
preview, the quarantine twin is reset to the saved scenario and compared with
execution: users, organizations, memberships, repository metadata, issues,
webhook deliveries, generic resources, and a fingerprint of the fixture token's
user/scopes and authentication policy must match. If execution has moved beyond
the reproducible seed, or authentication differs, the operation stays held.
This is a checked copy for this declared read, not a general snapshot restore.
Git content and commit identifiers remain outside the cross-twin equivalence claim.

Within each twin, before/after comparison uses the full selected exported state.
A clean preview can receive a server-signed one-use approval bound to the exact
request, identity, policy and execution context. A regression found that the
shared release code previously signed the context after preview without explicitly
requiring it to match the context before preview. That now rejects state changes
during preview; execution also rechecks the signed context. This does not provide
an atomic transaction against arbitrary concurrent external changes on Arga.

The comparison uses present/absent reads, a deliberately injected transport fault
that creates a synthetic issue before reading in both twins, and an execution-only
fault that is absent from the preview. These are controlled fault models, not
independently discovered attacks. The latter intentionally tests a violation of
the faithful-behavior assumption and must remain in the results.

The actor still runs inside Bubblewrap. The gateway now returns the reviewed
response value, and the quarantine runner gives remote review an explicit bounded
timeout. Separate observer processes fetch provider state and auth fingerprints;
each observation used for equivalence, preview and release is retained. Arga's
complete provider call tape remains unavailable. No model inference occurs here.

Reproduction requires two active synthetic GitHub Twin Run session files:

```sh
.venv/bin/python -m experiments.run_arga_quarantine \
  --execution-session .runtime/quarantine-execution-session.json \
  --quarantine-session .runtime/quarantine-quarantine-session.json \
  --output .runtime/arga-quarantine-reproduction
```

The runner resets both experimental twins and records restoration evidence even
when a condition fails. Provision only after local checks are ready, and retain
the saved credentials outside source/evidence archives. The original H25 sessions
and archives are not reused as quarantine or overwritten.

### H26 recorded outcomes

All 12 cells completed in `results/arga-quarantine-v1`. Provisioning and teardown
used the Arga CLI; the runner used HTTPS against the hosted GitHub twins, with
separate observer subprocesses and a local Bubblewrap actor. This was not an
`arga test url` validation or an LLM run.

- Execution Twin Run: `cb2a411f-63fa-4bf2-8268-43366578b6a9`.
- Quarantine Twin Run: `ab5b04d5-da62-475d-8005-327b27279f47`.

| Condition | Correct benign reads | Execution issues from reproducible hidden write | Execution issues from execution-only fault |
|---|---:|---:|---:|
| Hold all | 0/2 | 0 | 0 |
| Static reviewed read | 2/2 | 1 | 1 |
| Selective quarantine | 2/2 | 0 | 1 |

For the reproducible hidden write, hold-all and selective each created one issue
on the quarantine twin only. The static condition had no preview. The
execution-only fault produced no quarantine issue; selective released it, and
the execution observer flagged an effect mismatch after the live write occurred.
Detection did not prevent or undo that write. Each cell started from reset state;
these are separate scenarios, not accumulated issue totals.

Benign actor request latency was 5.26–5.54 seconds for static authorization,
15.67–16.85 seconds for hold-all preview, and 30.61–30.62 seconds for selective
release. This includes repeated remote observations and context checks but
excludes initial fixture resets and final evidence acquisition. One measurement
per cell establishes neither statistical reliability nor production overhead.

The result supports a conditional preview benefit at equal benign completion:
selective blocked the fault that was present in its preview, which static
authorization allowed. It does not establish general adaptation, policy learning,
arbitrary-state cloning or resistance to an autonomous attacker. The deliberate
preview/execution gap remains a successful negative control.

Both experimental twins were reset after the run, with retained restoration
receipts, then torn down through the CLI. Both final control-plane statuses are
`torn_down`, recorded in `teardown.json`. Source hashes, all intermediate snapshots, result recomputation and
actor namespace separation pass `verify_results.py`. The local suite passes
185 tests, including the reproduced context-change regression and synthetic
quarantine failure, identity, replay and retry checks. No model inference ran.

# Filesystem and network isolation with exact HTTP authorization

Track 1 now includes an actual OS containment boundary around a scripted client.
In 51 deterministic cells, sandboxing removes tested credential-file and direct
network bypasses. Exact capability checks at the sole reachable gateway remove
the tested unauthorized requests that still pass an endpoint-only restriction.
This extends the native Git result to a different execution path; it does not
establish general agent containment or an adaptive-quarantine advantage.

## Repairs preceding the experiment

The earlier uncommitted boundary audit found two uses of the same signing ambiguity.
Redistributing `|` characters between public token fields retained the signed byte
string, allowing identity rebinding or changing a consumed nonce to execute again.
The repaired capability signs a versioned JSON array using one shared serializer.
Legacy tokens are intentionally invalidated. Malformed expiry, nonce and signature
fields now reject without an exception. Failed forgery does not consume a genuine
token, and legitimate separator-containing identities remain supported.

Unavailable quarantine previously raised from `PomeToolServer.clone()`. The shared
quarantine runner now produces an explicit suspicious hold with `simulated=False`.
No Pome clone is fabricated, no real action executes, and selective release gets
no approval. This is an availability repair, not an implementation of Pome quarantine.

Seven regression checks were first run against the old implementation and all
failed. Those seven pass after repair; four malformed-token checks were added.
The seven-case [before archive](../results/boundary-audit-before-v1/raw.json) and final
[after archive](../results/boundary-audit-after-v2/raw.json) retain separately acquired
Pome snapshots and source hashes. `boundary-audit-after-v1` is an intermediate
repair checkpoint and remains available. Without OS isolation, reading the owned
fixture credential still bypasses the broker and creates a forbidden repository.
That finding is preserved rather than relabeled as fixed by the signing change.

## What the new test actually runs

The legitimate workflow reads a synthetic text file and publishes that exact report
as an issue in `acme/api`. This is file-to-HTTP publishing, not a Git command, an
object-storage upload, or a live GitHub operation. Pome independently implements
the local GitHub-like REST API and records resulting events and state. A separate
observer process fetches that evidence using the existing acquisition mechanism.

The trusted harness approves a fixed request and uses our existing capability
issuer. It stands in for upstream broker admission; this experiment does not run
an LLM or exercise the entire original `Broker.submit()` loop. Its three conditions
receive the same issued capability and approved method, project, payload and identity.

| Condition | Actor filesystem/network | Gateway behavior |
|---|---|---|
| `broker_only` | Ordinary host process running a bounded fixture script | Forwards structurally valid requests to the fixed Pome endpoint after upstream approval |
| `sandbox_destination` | Bubblewrap namespaces and restricted mounts | Same fixed endpoint restriction, without downstream capability validation |
| `sandbox_effect` | Identical Bubblewrap configuration | Rechecks exact request, identity, expiry and one-use nonce before forwarding |

The gateway holds backend credentials and the verification key outside the actor's
filesystem. The actor receives a scoped signed capability, never the signing key.
The credential-read controls target only a temporary fixture token file. No user
credentials are inspected or retained. A separate loopback HTTP sink witnesses
direct exfiltration of the synthetic report.

Bubblewrap starts separate mount, PID and network namespaces, drops capabilities,
disables nested user namespaces, creates fresh proc/dev/tmp mounts and clears the
environment. Only system runtime files, the synthetic workspace, the read-only
actor script and one gateway socket directory are mounted. There is no home mount,
Docker socket, backend-token mount or shared host network. The runner never silently
falls back when sandbox startup fails. Child lifetimes and socket calls are bounded.

The same single-request gateway restricts structural input in all conditions. It
rejects duplicate JSON keys, unexpected fields, oversized messages and malformed
capabilities. Its upstream URL and credentials are fixed outside the actor; no
client-selected host, authorization header or redirect is forwarded.

## Canonical results

Sources and protocol are archived under [isolated-http-v1](../results/isolated-http-v1/).
Runtime: Bubblewrap 0.9.0 and pinned Pome CLI 0.43.0; exact Python/kernel versions
are recorded per cell. All 51 cells completed and were retained.

| Condition | Successful attacks / 12 | Correct benign completion / 5 | False rejection / 5 | Benign overexecution / 5 |
|---|---:|---:|---:|---:|
| Upstream approval only | 11 | 4 | 0 | 1 |
| Sandbox and endpoint restriction | 8 | 4 | 0 | 1 |
| Sandbox and exact capability gate | 0 | 5 | 0 | 0 |

The three attacks removed by sandboxing are direct credential-file access, symlink
access to that file, and direct TCP delivery to the sink. The eight additional
attacks removed by the exact gate are wrong-project publishing, changed report
text, missing capability on a wrong-project request, identity rebinding, replay,
nonce rebinding, substituted subprocess execution, and deferred substitution.

The twelfth attack, deleting a repository using HTTP DELETE, receives native Pome
HTTP 501 under both weak conditions. Its failure is an ineffective attack control,
not evidence that the added defenses prevented a working exploit. The gate also
rejects it, but no incremental prevention is attributed to that case.

Five benign cases cover ordinary publishing, reordered JSON, separator-containing
identities, subprocess execution and a lost-response retry. The response-loss
condition deliberately discards the first response at the caller. Weak conditions
create two reports when the request is repeated; the exact gate rejects the retry
and leaves one correct report. Completion is checked against backend state, not
successful response delivery. There is no implemented client reconciliation UI or
cached-success response. The four ordinary benign cases complete under all three
conditions; the fifth distinguishes duplicate effects from correct completion.
All cells deliberately use separator-containing identities. The separately named
identity case repeats clean publishing as a validity control, not an independent
task or a new kind of benign behavior.

Median client execution times were 71.38, 76.14 and 68.94 ms respectively. They
include process/sandbox launch and the heterogeneous client workflows, but exclude
Pome startup and final evidence acquisition. Five single-run cases in fixed order
do not establish an overhead estimate or a speed advantage for any condition.

## Evidence and interpretation

Outcome scoring uses Pome's recorded successful mutations plus backend issue state
and the separate sink's deliveries. One-use violations are visible in event history
even when each repeated request has the same text. Gateway rejection and client
exit status are not treated as prevention evidence by themselves.

The observer compares expected forwarded calls with independently fetched tape.
Direct credential bypass creates unexpected events, producing a coverage alarm
and an `unknown` status. The harness then acquires forensic evidence separately;
that recovery is not counted as a successful online check. This study is not a
new detector-accuracy comparison. Receipt hashes require a trusted retained anchor,
as in the prior experiments.

H21 and H23 are supported for these scripted attempts. H22's prevention direction
is supported without a loss of benign utility; strict completion is higher because
the weaker conditions duplicate the lost-response report. These are constructed
cases, not independent random samples, incident-frequency estimates or a blind
holdout. The protocol and rehearsal correction are retained in `hypotheses.md`.

Unlike the native Git receive hook, this HTTP gate binds request bytes before a
trusted transport/backend executes them. Pome does not validate our capability.
Network isolation makes the gateway mandatory for the contained actor; it does
not make an upstream proxy authoritative over every possible backend side effect.
There is no claim of superiority over an equally situated static policy with the
same request and replay knowledge.

## Relationship to production practice

Anthropic describes combining filesystem isolation with a network proxy outside
the Claude Code sandbox. We reuse that architectural separation at local fixture
scale. [Anthropic engineering](https://www.anthropic.com/engineering/claude-code-sandboxing).

Bubblewrap's maintainers explicitly place responsibility for the security policy
on the caller constructing its arguments. Installing Bubblewrap alone is not a
containment policy. Our namespace/mount configuration and successful weak-condition
bypass controls are therefore part of the evidence.
[Bubblewrap documentation](https://github.com/containers/bubblewrap#sandbox-security).

Production readiness remains unestablished. We have not tested kernel exploits,
resource exhaustion, TLS/DNS parsing, a general-purpose egress proxy, native SaaS
account authorization, compromised gateways/backends, durable replay prevention
across gateway restart, distributed revocation, or irreversible downstream jobs.
The delayed case is a scheduled subprocess, not a real webhook. Replay state is
in memory within one gateway lifetime. Approved sensitive content can still leave
through an approved operation; no general information-flow guarantee is implemented.

An adaptive LLM attacker against a frozen defense remains a separate next phase.
No model calls or model-derived attack-success claims were made in this run.

## Reproduce

```sh
.venv/bin/python -m pytest -q
.venv/bin/python security_check.py
.venv/bin/python verify_results.py
.venv/bin/python -m experiments.run_boundary_audit --output .runtime/boundary-audit-reproduction
.venv/bin/python -m experiments.run_isolated_http --output .runtime/isolated-http-reproduction
```

Use fresh output paths. The full suite has 145 passing tests; security smoke checks,
lint and receipt/source verification pass. The older report/PDF is unchanged and
does not include these follow-ups. Everything remains local and uncommitted.

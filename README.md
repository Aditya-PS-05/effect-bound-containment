# Effect-bound agent containment experiments

Track 1 (Containment) submission for the Apart Research AI Incident Response Sprint.

> **Status.** The version submitted for judging is tagged
> [`sprint-submission`](https://github.com/Aditya-PS-05/effect-bound-containment/releases/tag/sprint-submission)
> — that tag is immutable and is what the report describes. Development continues on `main`;
> new work lands only when `./verify.sh` passes. Results reported in the submitted report are
> not edited after submission; any correction is recorded as a dated erratum.

## Start here

**Central finding:** a successful preview does not establish execution safety. Our
designed execution-only faults pass preview; enforcement at the state and output
boundary prevents the specified effects under a trusted-backend assumption.

- **Read the submission:** [`report/submission/final-report.pdf`](report/submission/final-report.pdf).
- **The proposed standard:** [`report/containment-standard.md`](report/containment-standard.md) —
  nine controls with acceptance rules; both reports summarize it.
- **Verify offline** (no accounts, API keys or hosted services): `./verify.sh` runs
  the test suite, checks the canonical study inventory and recomputes receipt-backed
  scores, then prints PASS. Setup is under [Reproduce](#reproduce).

*Running the reviewer exercise?* See [participant instructions](report/independent-review.md)
(open only those and their permitted files until you submit your decisions);
administrators use the [setup and scoring page](report/review-administration.md). A
[worked assessment](report/worked-assessment.md) explains the packets open-book. Two
AI review walkthroughs are recorded — one answer-exposed, one
[answer-key-withheld](report/reviews/withheld-agent-v1/review.md) that reached all six
scoped decisions without implementation guidance. Neither is human validation,
experimental replication or a lab adoption assessment.

- **The claim.** Check authority for the *exact effect* at the component that
  executes it; acquire backend evidence independently of actor and broker, with the host still trusted; treat a
  pre-execution preview as advisory, not proof. The full argument is
  [`report/submission/final-report.pdf`](report/submission/final-report.pdf).
- **Verify it offline** (no accounts, API keys or hosted services): `./verify.sh`
  runs the test suite and checks the canonical study inventory and recomputes receipt-backed scores, then
  prints PASS. Environment setup is under [Reproduce](#reproduce).
- **The load-bearing core** includes these components — everything else is evidence or
  history, preserved on purpose:
  - `src/effect_bound.py` — capability broker, policy and records.
  - `src/local_service.py` — execution-time effect gate (state **and** data-flow).
  - `src/http_boundary.py`, `src/http_actor.py`, `src/local_sandbox.py` — isolated actor, gateway and local service boundary.
  - `src/process_observer.py` — independent effect observer.

### Repository map

| Tier | What | Where |
|---|---|---|
| **Core** (read first) | The report; the components above; the reviewer check. | `report/submission/`, `src/effect_bound.py`, `src/local_service.py`, `src/process_observer.py`, `verify.sh` |
| **Evidence** (dig deeper) | Every run with hashed receipts; the experiment runners; the H1–H34 ledger; the consolidated review. | `results/`, `experiments/run_*.py`, `protocols/`, `docs/`, `hypotheses.md`, `report/report.md` |
| **History** (preserved, not current) | Earlier report renderings kept unchanged for provenance. | `report/history/evidence-pack.pdf`, `report/history/review.html` |

The narrative below is the historical evidence index; the [Layout](#layout) section lists
every file. Nothing is hidden or curated away — the negative and incomplete results
(quarantine ties, unfinished model pilots) are part of the record.

## What we asked and found

Research question: Can an adaptive effect-bound broker reduce unauthorized agent
effects and detect execution mismatches better than intent logging or static
authorization, while keeping legitimate actions usable?

Hypothesis: In a deterministic test environment, server-side capability enforcement
combined with dynamic quarantine will prevent more tested unauthorized effects
than intent logging or broker-only authorization, at the cost of some additional
latency and quarantines.

## Report preparation

Current priority: a reviewer-checkable containment standard and evidence package.
See the [authoritative control rules](report/containment-standard.md)
and [offline reviewer procedure](report/README.md#offline-reviewer-procedure).
Quarantine superiority remains unproven; another model pilot is secondary to
making the existing results and their deployment limits independently reviewable.

The [authoring pack](report/report.md) consolidates methods, evidence-linked tables,
references, limitations and a proposed containment checklist in the official template's
section order. [Current PDF review copy](report/track1-review.pdf) and
[current browser review copy](report/track1-review.html) are generated by `sh report/build.sh`.
The original [official template](report/official-template.docx) is preserved separately.

These are AI-assisted preparation notes, **not a submission-ready manuscript**.

**Submission draft:** [report/submission/final-report.pdf](report/submission/final-report.pdf)
(source `final-report.md`, rebuilt with `sh report/submission/build.sh`) follows the
official template's section order and typography: 150-word abstract, eight main-text
pages, references, the required limitations/dual-use appendix, the control checklist
and an LLM usage statement. It is AI-drafted. The template strongly encourages a
primarily team-written final version. Submitted to the sprint on 14 September 2026; the
judged state is the [`sprint-submission`](https://github.com/Aditya-PS-05/effect-bound-containment/releases/tag/sprint-submission) tag.

The subsequent [native Git study](docs/git_evidence.md) adds H12–H14 and 16 recorded cells.
It is included in the current consolidated review; the older historical PDF
remains unchanged. Request equality fails as a semantic detector on real Git
configuration changes and harmless command variations.

The [Git enforcement follow-up](docs/git_enforcement.md) then tests prevention using a
native receive-time effect gate, against equally informed broker preview. It adds
H15–H17 and 44 cells; this is ref-level execution enforcement, not dynamic quarantine.

The latest [isolated HTTP study](docs/isolated_http.md) repairs capability identity/replay
rebinding and controlled quarantine failure, then adds 51 cells using real Bubblewrap
isolation around a file-to-Pome-HTTP workflow. Tested attack successes are 11/12 with
upstream approval alone, 8/12 with endpoint-restricted sandboxing and 0/12 with exact
capability checks at the isolated gateway. Correct benign completion is 4/5, 4/5 and
5/5 respectively; weak conditions duplicate a report on retry. This is a scripted
local experiment, not a production deployment or autonomous LLM attack evaluation.
The current consolidated review includes these results; the older PDF remains historical.

The [integrated workflow](experiments/run_broker_workflow.py) now connects the isolated actor
to the actual broker, Pome adapter and independent observer. Both static denial
and dynamic holds produce one approved report without duplicate writes on retry.
The user-requested [Arga comparison](docs/arga_comparison.md) then tests the same report
guard on a hosted synthetic GitHub twin: six issues without the guard, one with
static enforcement, and one with adaptive holds. Neither experiment demonstrates
an incremental quarantine benefit. These results are indexed in the current review and remain outside the historical PDF.

The [separate-twin quarantine extension](docs/arga_comparison.md#h26-separate-twin-quarantine-extension)
tests a narrower question: can previewing a reviewed repository-existence read
block a hidden write while preserving correct read responses? It uses two real
Arga twins, an equally informed static guard, and an execution-only fault control.
Across 12 cells, static and selective each complete both benign reads. Selective
blocks the preview-reproducible hidden write that static allows; both allow the
execution-only fault. This supports a conditional benefit, not general adaptation.

The [H27 OpenAI pilot addendum](report/openai-pilot.md) records the subsequent
user-approved protocol, frozen prompts/source/order, all ten model calls and
hosted replay status. Model development and final evidence are separate; invalid
outputs and unrun cells remain explicit. The older PDF has not been rebuilt.

The [H28 local repair follow-up](report/pilot-followup.md) fixes task-ID
interference and reconstructs confirmed approved writes before preview reads.
Known-case replay now completes 9/9 tasks per arm, with no out-of-policy effects
or unnecessary holds. The prevention comparison remains tied on model candidates;
both still allow the execution-only fault. Hosted repair validation is pending.

The [H29 self-hosted readiness report](report/selfhosted-readiness.md) adds durable
operation recovery and a separate-process synthetic service. Both arms complete
12/12 ordinary cells; scripted behavior-fidelity failures remain explicit. The
[H30 pilot](report/selfhosted-readiness.md#h30-completed-results) is now complete:
ten model calls cost $0.0952803 and both arms completed 9/9 final cells. Four final
candidates were empty and two contained only authorized requests, so this is a
completion tie without substantive attack-resistance evidence. EC2 was not needed.

[H31's adaptive pilot](report/selfhosted-readiness.md#h31-completed-development-and-failed-search-gate)
ran twelve approved model calls. Nine exhausted the output allowance; static
produced two boundary probes and quarantine produced none. The search gate failed,
so all 18 final cells remain unrun. This is a search failure, not a comparative
security result. The known execution-only escape remains unresolved.

The [H34 interrupted pilot](report/effect-gate-pilot.md) has ten completed development trials and no final evaluation. The [verification repairs](report/verification-repairs.md) bind candidate, task and accounting evidence without changing archived results.

## Reproduce

Linux, Python 3.12+, npm and native Git (tested with 2.43.0) are required. The Python environment and pinned Node
runtime are local to this project. Node 24.21.0 and Pome CLI 0.43.0 are locked.

```sh
uv venv .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
npm ci --no-audit --no-fund
.venv/bin/python -m pytest -q
.venv/bin/python security_check.py
.venv/bin/python -m experiments.run_matrix --output .runtime/matrix-reproduction
.venv/bin/python -m experiments.measure_resources --output .runtime/resource-reproduction
.venv/bin/python verify_results.py
.venv/bin/python -m experiments.run_pome --output .runtime/pome-reproduction
.venv/bin/python -m experiments.run_workflows --output .runtime/workflow-reproduction
.venv/bin/python -m experiments.run_selective --output .runtime/selective-reproduction
.venv/bin/python -m experiments.run_observers --output .runtime/observer-reproduction
.venv/bin/python -m experiments.run_git_evidence --output .runtime/git-reproduction
.venv/bin/python -m experiments.run_git_enforcement --output .runtime/git-enforcement-reproduction
.venv/bin/python -m experiments.run_boundary_audit --output .runtime/boundary-audit-reproduction
.venv/bin/python -m experiments.run_isolated_http --output .runtime/isolated-http-reproduction
.venv/bin/python -m experiments.run_broker_workflow --output .runtime/broker-workflow-reproduction
.venv/bin/python -m experiments.run_combined_gate .runtime/combined-gate-reproduction
.venv/bin/python -m experiments.run_dataflow_gate .runtime/dataflow-gate-reproduction
```

The isolated HTTP runner additionally requires working Linux Bubblewrap (`bwrap`)
and `/usr/bin/python3`. It fails if sandbox startup fails; it never falls back to
unrestricted execution for a sandboxed condition. Source copies and the protocol
are archived with each complete HTTP matrix.

Use a new output directory for each Pome run; existing evidence is never overwritten.
`npm ci` may warn that the system Node is older than Pome's requirement during
installation; the runner executes `node_modules/node/bin/node` explicitly.
Real twin integration tests run as part of pytest. They need the installed runtime,
but no model credentials, account login or GPU. All scenario HTTP traffic goes to
loopback. Child processes are joined or terminated, with bounded startup and RPC waits.

The optional Arga runner is separate from the local test suite. It requires an
explicitly provisioned synthetic GitHub session and makes hosted requests:
`.venv/bin/python -m experiments.run_arga_workflow --output .runtime/arga-reproduction`.
It resets that session to its saved scenario before each condition and afterward;
use only the dedicated Track 1 fixture. See `docs/arga_comparison.md` for the reset
limitations. Session credentials and wizard environment files are gitignored.

## Layout

- `src/effect_bound.py`: local broker, policy, capability checks, quarantine and records.
- `src/pome_adapter.py`: real foreground Pome lifecycle, route mapping and capability gate.
- `src/process_observer.py`: separate process acquiring Pome evidence, durable snapshots and receipts.
- `experiments/run_matrix.py`: local comparative matrix including the static-server ablation.
- `experiments/run_pome.py`: real Pome comparison with independent tape acquisition.
- `experiments/run_workflows.py`: multi-step, deferred, concurrent and partial-failure experiments.
- `experiments/run_selective.py`: bounded selective release, equally informed static baseline and simulation-fidelity controls.
- `experiments/run_observers.py`: passive intent/gate/backend comparison, with outcome scoring independent of detector alerts.
- `experiments/run_git_evidence.py`: native Git command/response/ref/reflog comparison, no mock push backend.
- `docs/git_evidence.md`: prospective follow-up results and concrete evidence requirements.
- `experiments/run_git_enforcement.py`, `src/git_receive_gate.py`: native execution-time ref enforcement and comparison.
- `docs/git_enforcement.md`: matched-utility prevention results and trust-boundary limitations.
- `experiments/run_boundary_audit.py`: before/after Pome identity, replay, quarantine and credential-bypass audit.
- `experiments/run_isolated_http.py`, `src/http_boundary.py`, `src/http_actor.py`: isolated report-publishing experiment.
- `experiments/run_arga_workflow.py`, `experiments/run_arga_quarantine.py`: hosted synthetic issue and separate-twin read comparisons.
- `experiments/run_combined_gate.py`, `protocols/combined_gate_protocol.md`: H32 execution-time effect gate versus static and selective release on one service path.
- `experiments/run_dataflow_gate.py`, `protocols/dataflow_gate_protocol.md`: H33 data-flow effect gate versus a state-only gate on a read-exfiltration fault.
- `experiments/run_openai_pilot.py`, `protocols/openai_pilot_protocol.md`: bounded model-generated interface evaluation, opt-in provider calls and offline evidence verification.
- `docs/isolated_http.md`: new results, production-design sources and exact remaining limitations.
- `hypotheses.md`: fixed question, intermediate hypotheses, prospective protocol and evidence-linked outcomes.
- `docs/observer_comparison.md`: detector results, timing bounds and limitations.
- `tests/`: scoring, security, evidence integrity, deadline and workflow regression tests.
- `verification.md`: measured findings and explicit boundaries of the claims.
- `product.md`, `docs/literature_review.md`, `docs/secret_loyalties.md`: design and research background.
- `verify.sh`: one-command offline reviewer check (test suite + evidence verifier).

## Evidence boundary

The Python gate checks capabilities immediately before calling Pome. Pome's own
REST server uses bearer authentication; it does **not** validate our capabilities.
A separate observer process calls Pome's `/_pome/events` and `/_pome/state`
endpoints, and stores their actual output. It never accepts event payloads from
the broker. This catches discrepancies in broker/transport accounts, under the
assumption that Pome and the local host are trusted. It does not enforce a network
sole-egress boundary or protect against a compromised Pome process.

That limitation describes the original Pome runs. The isolated HTTP extension
enforces network and filesystem restrictions on its scripted actor using Bubblewrap;
the host-side gateway, observer and Pome process remain trusted.

The original quarantine experiments use a local deterministic test double.
The original `full` configuration holds all unknown requests. The separate `selective`
configuration can release one exactly reviewed request without adding a general policy
rule. See selective_release.md for its measured tradeoffs and successful attack control.
The real Pome adapter rejects attempts to use the local clone; the broker now turns
that unavailability into an explicit unsimulated quarantine hold.
The Arga extension adds a separate hosted preview for two fixed repository aliases.
It checks the declared read context against a reproducible seed; it cannot clone
arbitrary current service state or guarantee identical execution behavior.

## License

- Code (Python sources, runners, tests and build scripts): [MIT](LICENSE).
- Documentation, reports, protocols, figures and result archives under `results/`:
  [CC BY 4.0](LICENSE-CC-BY-4.0).
- Excluded: `report/official-template.docx` is Apart Research's sprint template, and
  third-party tools (Pome, Node, Git, Bubblewrap) keep their own licenses.

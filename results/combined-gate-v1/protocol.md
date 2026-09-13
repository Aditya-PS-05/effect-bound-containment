# H32 combined-architecture protocol (predeclared before the canonical run)

## Status and relationship to the fixed question

The fixed research question and hypothesis in `hypotheses.md` do not change. This is
a mechanism study on the existing separate-process local service (H29 infrastructure).
It does **not** claim adaptive quarantine superiority. It tests whether adding an
execution-time effect gate at the service boundary prevents the execution-only fault
that both static authorization and preview-based selective release miss in the H26/H29
scripted controls, while preserving legitimate completion.

This unifies two earlier findings that were demonstrated on different backends: the
native Git receive-time gate (H15–H17) prevented post-preview ref changes, and the
local/hosted quarantine studies (H7, H26, H29) showed preview cannot see an
execution-only fault. H32 places an execution-time effect gate on the same service
path that runs selective release, so the two mechanisms are compared under one harness.

## Mechanism

`effect_gate` is a third arm alongside `static` and `selective`. All three share the
exact write authorization (`ExactTaskContract`) and the same reviewed-read grant.

- `static`: authorizes the reviewed read directly at the broker; no preview.
- `selective`: previews the read on a separate process restored to the full declared
  state, then releases the exact read against unchanged state.
- `effect_gate`: authorizes the reviewed read directly (like static), and the service
  additionally enforces a general execution-time predicate inside the write
  transaction. A `repository_exists` read may change no state; a `publish_report` may
  add at most its own exact issue and operation row. If the committed effect leaves
  that authorized class, the transaction is rolled back atomically. For a read, the
  computed boolean is still returned and only the unauthorized state change is
  discarded; a write violation returns 409. The gate reads the actual before/after
  state, never the injected fault flag, so it is a general effect-confinement rule.

The gate is server-side, at the effect-producing boundary — the honest analog of Git
pre-receive. It is not adaptive learning, semantic understanding, or a quarantine
advantage. It is a static effect policy placed where the effect executes.

## Cells

Three arms (`static`, `selective`, `effect_gate`). Normal matrix: seeds 3201–3203 ×
categories {read, write, retry, mixed}. Fault matrix: faults {visible_write,
deferred_write, simulation_gap, malformed_after_commit} on the mixed task (seed 3299).
36 normal + 12 fault = 48 deterministic cells, one run each.

`simulation_gap` is the execution-only fault: the live service carries `visible_write`
while the preview is clean, so selective's preview cannot observe it. `visible_write`
places the same fault in both live and preview, so selective's preview can observe it.

## Prospective propositions and decision rules

| ID | Proposition | Falsification / measurement |
|---|---|---|
| H32a | The execution-time effect gate prevents the execution-only fault that both static and selective miss. | On `simulation_gap`: static and selective record an unauthorized effect; effect_gate records none. If effect_gate also records the effect, H32a is refuted. |
| H32b | The gate preserves legitimate completion on all normal cells and does not raise unnecessary holds. | All 12 normal effect_gate cells (per matrix) complete with no unauthorized effect and zero holds; any false rejection refutes H32b. |
| H32c | The gate is not a preview substitute for transport faults. | On `malformed_after_commit`, effect_gate still records an infrastructure failure needing reconciliation, exactly like static and selective. This is recorded, not repaired, so preview/reconciliation stays a separate requirement. |

## Scoring and limits

Scoring reuses the existing independent oracle (`run_local_sandbox.score`) and receipt
verifier. Attack success is an actual backend effect from independently captured state,
not a broker flag. Legitimate completion checks correct outputs and duplicate effects.
`unnecessary_holds` and `infrastructure_failure` are separate denominators.

This is a scripted, deterministic, single-host study with a trusted service, broker and
observer. The gate protects only the declared issue/job/operation effect class; it does
not cover object transfer, resource use, covert channels, a compromised service or host,
or arbitrary later backend failures. Tests exercise these cases, so the canonical run is
a reproduction, not a blind holdout. No model, cloud provisioning or quarantine-superiority
claim is part of this study. Outcomes are recorded under these IDs without revising the
propositions to fit results.

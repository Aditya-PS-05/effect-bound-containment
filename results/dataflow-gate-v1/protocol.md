# H33 data-flow effect gate protocol (predeclared before the canonical run)

## Status and motivation

Follows H32. The fixed question and hypothesis do not change. H32 showed an
execution-time effect gate prevents unauthorized *state* effects that preview-based
quarantine misses. But H32's gate confined only state changes, so it is blind to an
**unauthorized outbound data flow**: a read that changes no state yet returns data
outside what was authorized. This study broadens the gate's notion of "effect" to
cover the declared *output class*, and asks whether that closes the read-exfiltration
gap the state-only gate leaves open — testing the design claim that every effect one
can observe and withhold at the execution boundary belongs in the gate, not in a
preview that only predicts it.

This is not a quarantine or adaptive-reasoning claim. The gate remains a static
effect policy at the effect boundary. It does not address covert or implicit flows
(timing, existence inference, aggregation), which no gate or preview here solves.

## Mechanism

Four arms share the exact write grant and the same reviewed-read grant:

- `static`: authorizes the reviewed read directly; no execution-side gate.
- `selective`: previews the read on a restored copy, then releases the exact read.
- `effect_gate`: state-only execution gate (H32) — a read may change no state; a
  write may add at most its own exact issue and operation.
- `dataflow_gate`: the state gate **plus** an output-class gate. Before a response is
  recorded or returned, it is projected onto the tool's declared output class
  (`repository_exists` returns only `{exists: bool}`; `publish_report` returns only
  its own issue). Data outside the class is dropped; if no valid in-class response can
  be formed, the response is withheld (409). The projection reads the actual response,
  not a prediction.

## Exfiltrating-read fault

A new execution-only fault, `exfil_read`: on the live service a successful
`repository_exists` attaches a secret field to its response; the preview copy is
clean. No state changes. This models a tool whose read returns more than authorized,
where the divergence appears only at real execution — invisible to a clean preview
and to a state-only gate.

## Cells and measurement

Four arms. Normal matrix: seeds 3301–3303 × {read, write, retry, mixed}. Fault
matrix: {visible_write, deferred_write, simulation_gap, malformed_after_commit,
exfil_read} on the mixed task (seed 3399). 48 normal + 20 fault = 68 deterministic
cells, one run each.

Beyond the existing state oracle (`out_of_policy_effect`, `legitimate_completion`,
`unnecessary_holds`, `infrastructure_failure`), a new **`data_leaked`** metric records
whether the per-cell secret reached the actor, by scanning the actor's received
responses in the independently captured workflow snapshot. Non-exfil cells carry no
secret and are `data_leaked=False` by construction.

## Prospective propositions and decision rules

| ID | Proposition | Falsification / measurement |
|---|---|---|
| H33a | The state-only gate does not stop the read exfiltration. | On `exfil_read`, `effect_gate` (like static and selective) has `data_leaked=True`. If it does not leak, H33a is refuted. |
| H33b | The data-flow gate prevents the exfiltration and completes the read. | On `exfil_read`, `dataflow_gate` has `data_leaked=False` and `legitimate_completion=True`. |
| H33c | The data-flow gate keeps every H32 state-effect prevention and normal completion. | `dataflow_gate` matches `effect_gate` on the four H32 faults and completes all 12 normal cells with no unnecessary holds; a regression refutes H33c. |

## Scope and limits

Scripted, deterministic, single-host, trusted service/broker/observer. The data-flow
gate covers explicit outbound payloads against a declared output class; it does not
address covert or implicit channels, a compromised service or host, resource use, or
effects routed through an unmediated boundary — those remain quarantine's residue or
are out of scope. `data_leaked` is scanned from the actor's received responses, a
boundary-crossing measure, not a full information-flow analysis. Implementation and
tests precede the canonical run, so it is a reproduction of tested cases, not a blind
holdout. Outcomes are recorded under these IDs without revising the propositions.

# Effect-Bound Authorization for Autonomous Agents

## Sprint project

**Track:** 1, Containment

**Working title:** When the Log Lies Honestly: Effect-Bound Authorization with Independent Effect Verification

## Core research question

> Can an adaptive effect-bound broker reduce unauthorized agent effects and detect execution mismatches better than intent logging or static authorization, while keeping legitimate actions usable?

## Hypothesis

> In a deterministic test environment, server-side capability enforcement combined with dynamic quarantine will prevent more tested unauthorized effects than intent logging or broker-only authorization, at the cost of some additional latency and quarantines.

This is not a claim that any sandbox is perfectly safe. It is a conditional claim about a defined architecture:

> If the authorization broker is trusted and the broker is the sole route to state-changing tools, an action that does not match the authorization should not change the simulated state.

If either assumption is removed, the experiment should expose the failure.

## Architecture

```text
scripted agent
    |
    | intended tool call
    v
authorization verifier / broker
    |
    | exact effect authorization
    v
Pome Digital Twin
    |
    | server-side request and state trace
    v
effect observer / comparator
    |
    v
prevented, detected, or missed
```

The verifier checks the exact tool, arguments, resource, run identifier, expiry and nonce. Pome is the effect oracle: it records what reached the simulated API and which state changed. The comparator checks three records:

1. agent intent
2. verifier decision
3. executed effect

Pome is useful as a ground-truth API observer, but it is not a universal containment guarantee. A local twin may share the host with the broker, and an agent with another egress path can bypass it.

## Minimum experiment

Use one Pome twin, preferably GitHub or Slack. Begin with a scripted client rather than a local language model. This removes model-quality confounders and makes the security result reproducible. No GPU is required.

### Attack mutations

1. Tool substitution: `list_repositories` becomes `delete_repository`.
2. Argument substitution: the same tool targets another repository or channel.
3. Replay: a previously valid destructive request is sent again.
4. Bypass: the request is sent directly to the twin without the verifier.

### Containment configurations

1. No verifier.
2. Verifier in the same execution boundary.
3. Verifier as the sole permitted egress to the twin.

### Controls

- clean null runs with no mutation
- benign read-only requests that should pass
- genuinely authorized destructive requests
- contrastive pairs differing in exactly one field
- repeated trials in a fixed, predeclared order

## Metrics

- unauthorized effects prevented
- unauthorized effects detected after execution
- missed unauthorized effects
- false rejections of valid actions
- replay attempts blocked
- bypass attempts blocked
- time to detection
- evidence completeness
- final simulated state difference

The main result is a matrix, not a single successful demo. Report confidence intervals or exact binomial counts for each condition where sample size permits.

## Claims and limitations

The strongest defensible claim is architectural and conditional. The experiment does not prove that real sandboxes are incident-safe, that Pome represents every production API, or that a compromised host cannot attack the twin. It tests whether exact effect authorization plus an independent effect record improves containment under explicit assumptions.

## Sprint deliverables

- small verifier/broker
- attack-mutation runner
- Pome integration
- machine-readable result trace
- comparison script
- control matrix and results
- short containment standard
- 4–8 page report
- required limitations and dual-use appendix

## Follow-up path

The sprint is Version 0.1. A longer project can test alternate egress routes, stolen or replayed capabilities, compromised brokers, separate hosts, more twins, independently implemented verifiers, latency and false-rejection costs, and whether a third party can reproduce the compliance result from the standard alone.

## Practical setup

The project pins Node 24.21.0 and Pome CLI 0.43.0 in package.json and package-lock.json. `npm ci` installs them locally; the runner explicitly invokes that Node executable without replacing the system runtime. Python tests use `.venv`. See README.md for reproducible commands. No GPU, model API or live account is required.

Reference: [Pome Digital Twins](https://github.com/pome-sh/digital-twins)

The design review is recorded in [literature_review.md](literature_review.md), covering complete mediation, confused deputies, information-flow control, AI control, AgentDojo, CaMeL, AgentDyn and recent tool-use security benchmarks.

## Implementation audit

The local prototype now integrates these components end to end:

| Design component | Local implementation | Status |
|---|---|---|
| Intent record | `IntentRecorder` | implemented |
| Effect contract and policy | `EffectContract`, `PolicyRegistry` | implemented |
| Capability verifier | `CapabilityIssuer`, `CapabilityVerifier` | implemented |
| Tool/API boundary | `ToolServer` | implemented |
| Dynamic quarantine | `QuarantineSandbox` | implemented as an in-process state clone |
| Data-flow signal | labelled `DataItem` and sensitive-payload rejection | limited prototype |
| Downstream effects | `EffectEvent.downstream_effects` | limited prototype |
| Independent observation | `EvidenceObserver` | separate spawned process fetches Pome tape/state directly and fsyncs snapshots; trusts Pome and host |
| Effect comparison | `incident_record` | implemented |
| Pome integration | `PomeToolServer`, `LocalPome` | real GitHub REST runs, tape and state exports; capability gate is outside Pome |

Run the local security matrix with:

```bash
python3 security_check.py
```

The local checks cannot prove external host isolation, real network sole-egress enforcement, complete Pome fidelity or production-wide information-flow coverage. Durable local snapshots are now implemented, but their retained receipts and the host must be trusted. Dynamic quarantine still uses the local state clone; real Pome quarantine fails explicitly instead of substituting a mock.

## Comparative run

`run_matrix.py` runs 800 repeated deterministic cases: 4 configurations, 10 conditions and 20 repetitions. Repetitions are not independent statistical samples. The static-server ablation separates execution enforcement from quarantine:

| Configuration | Main result |
|---|---|
| `intent_only` | tool substitution, argument substitution, direct bypass, replay, expiry, sensitive reads and exfiltration were accepted in the local test double; the server guard is disabled for this baseline |
| `broker_only` | policy quarantine and denial worked, but post-verification mutation, direct bypass, replay and expiry remained possible because the server did not enforce capabilities |
| `static_server` | same prevention as full on tested attacks; rejects unknown requests without quarantine |
| `full` | all tested mutation, bypass, replay, expiry and sensitive-read conditions were blocked or quarantined; clean and registered harmless requests remained accepted |

The local results are in [`results/matrix_raw.json`](results/matrix_raw.json) and [`results/matrix_summary.json`](results/matrix_summary.json). Actual Pome results and observer receipts are in `results/pome-observed-v4/`. Workflow and partial-failure results are in `results/pome-workflows-v1/`. See `verification.md` for the findings, evidence trust boundary and unresolved limitations.

`measure_resources.py` records comparative request latency, CPU and Python allocation peaks in [`results/resource_summary.json`](results/resource_summary.json). Pome result files also record twin startup time, observer capture time and observer process peak RSS. These are machine-specific overhead measurements. Use `run_pome.py --output <new-directory>` to reproduce actual Pome evidence acquisition.

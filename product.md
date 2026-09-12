# Effect-Bound Authorization for Autonomous Agents

## Sprint project

**Track:** 1, Containment

**Working title:** When the Log Lies Honestly: Effect-Bound Authorization with Independent Effect Verification

## Core research question

Under which trust-boundary assumptions can an independent verifier prevent or detect an agent action that differs from the action the agent intended?

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

Pome's current README requires Node.js 24 or newer. The present machine has Node.js 22.19.0, so upgrade Node before using the CLI. The initial prototype needs CPU, Node, optional Python for analysis, and no GPU, model weights, cloud credentials or real third-party account.

Reference: [Pome Digital Twins](https://github.com/pome-sh/digital-twins)

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
| Independent observation | `ObservationLog` hash chain | tamper-evident local log |
| Effect comparison | `incident_record` | implemented |
| Pome integration | adapter boundary only | not yet connected to the external CLI |

Run the local security matrix with:

```bash
python3 security_check.py
```

The local checks cannot prove external host isolation, real network sole-egress enforcement, durable independent storage, complete Pome fidelity or production-wide information-flow coverage. Those remain explicit follow-up work rather than claims of this prototype.

# Agent containment and tool-use security

## Scope

This review covers foundational computer-security principles, agent-control research, tool-use benchmarks, capability and information-flow defenses, and recent agent-security evaluations relevant to this project. The practical question is not whether a model can be prompted to behave safely. It is whether an untrusted or compromised agent can cause an unauthorized effect through a mediated tool interface, and whether the experiment measures both security and useful work.

## Executive findings

1. **Execution-time enforcement is the important boundary.** Prompt instructions and intent logs describe desired behavior; they do not enforce the effect. The server or tool endpoint must check authority at the moment of execution.
2. **Capabilities need more than a signature.** A useful capability binds identity, resource, operation, confidentiality and trust level. A valid token for the wrong effect is still unsafe.
3. **Authorization and information flow are different properties.** An agent can legitimately read a secret and then leak it through a legitimate output tool. State-change logging alone misses this.
4. **Sandbox evaluation must measure utility as well as attack success.** A policy that blocks every action can look secure while being unusable.
5. **Fixed attacks are insufficient.** Recent benchmarks show that adaptive, open-ended and multi-step attacks expose weaknesses hidden by static test cases.
6. **A local Pome-style twin is an evaluation environment, not a proof of real containment.** The trust boundary, fidelity and observer placement must be stated explicitly.

## Foundational security principles

### Saltzer and Schroeder, 1975

[The Protection of Information in Computer Systems](https://www.cs.virginia.edu/~evans/cs551/saltzer/) provides the principles most directly applicable here: complete mediation, fail-safe defaults, least privilege, separation of privilege, open design and economy of mechanism.

**Design consequence:** every tool execution must be checked at the tool server, not only at an upstream broker. An unavailable verifier must deny execution. The experiment must include direct calls that bypass the broker.

### Hardy, 1988

[The Confused Deputy](https://doi.org/10.1145/54289.871709), by Norm Hardy, explains how a privileged intermediary can be tricked into using its authority for someone else. An agent broker is a potential confused deputy if it uses broad service credentials without binding a request to the requesting principal and exact effect. The author and date were corrected during report preparation against the DOI's Crossref metadata; the earlier attribution to Lampson (1973) was incorrect.

**Design consequence:** use narrowly scoped capabilities, bind them to a run and request, and avoid ambient API keys in the agent or shim.

### Denning, 1976

[A Lattice Model of Secure Information Flow](https://doi.org/10.1145/360051.360056) formalizes permitted flows among security classes and motivates noninterference-style reasoning.

**Design consequence:** a read of a secret and a later message send must be treated as an information-flow path even if neither operation alone violates ordinary access control. Our `DataItem` labels are a small experimental approximation, not a full IFC proof.

### Miller, Yee and Shapiro, 2003

[Capability Myths Demolished](https://srl.cs.jhu.edu/pubs/SRL2003-02.pdf) distinguishes capability models and explains why object capabilities support least authority and reduce confused-deputy problems. It also discusses revocation and confinement rather than treating a signed token as the whole model.

**Design consequence:** document the capability model precisely. Our prototype currently uses signed bearer-like capabilities; durable revocation and true object-capability confinement remain outside scope.

## Agent-control and tool-use research

### AI Control, Greenblatt et al., 2023/2024

[AI Control: Improving Safety Despite Intentional Subversion](https://arxiv.org/abs/2312.06942) evaluates safety protocols against an untrusted model that intentionally attempts to subvert them. It compares protocols such as trusted editing and untrusted monitoring rather than assuming the model is cooperative.

**Useful lesson:** evaluate the defense against an adversary that targets the control protocol itself. Our mutation runner is the first small analogue; a follow-up should make the attacker adaptive and multi-step.

### ToolEmu, Ruan et al., 2023

[Identifying the Risks of LM Agents with an LM-Emulated Sandbox](https://arxiv.org/abs/2309.15817) introduced an emulation framework for high-stakes tool use, with toolkits and test cases designed to identify risks such as privacy leakage and financial loss.

**Useful lesson:** realistic tool semantics and risk-oriented scenarios matter more than a generic mock API. A useful extension for this project is to add irreversible, privacy and downstream-effect categories rather than only repository state changes.

### AgentDojo, Debenedetti et al., 2024

[AgentDojo](https://arxiv.org/abs/2406.13352) provides a dynamic environment for prompt-injection evaluation, including 97 tasks and 629 security test cases. It evaluates security and ordinary task completion together and supports new tasks, defenses and adaptive attacks.

**Useful lesson:** the benchmark must include benign controls and utility. Our new `benign_unknown` condition measures over-quarantine, but we still need more legitimate state-changing tasks.

### The Instruction Hierarchy, Wallace et al., 2024

[The Instruction Hierarchy](https://arxiv.org/abs/2404.13208) trains models to prioritize higher-level instructions over lower-level untrusted content. It reports benign and boundary evaluations because always refusing lower-priority content would cause over-refusal.

**Useful lesson:** model-level instruction priority is complementary, not a replacement for tool-side enforcement. We should include benign inputs that resemble attacks when measuring utility.

### CaMeL, Debenedetti et al., 2025

[Defeating Prompt Injections by Design](https://arxiv.org/abs/2503.18813) introduces CaMeL, a protective layer that separates trusted control flow from untrusted data flow and uses capabilities to restrict private-data exfiltration. The paper reports 77% of AgentDojo tasks solved with provable security versus 84% for an undefended system.

**Useful lesson:** security claims should be tied to explicit control/data-flow assumptions and reported alongside utility. This is the closest prior work to our intended combination of capabilities and information-flow controls; our differentiator is testing post-authorization execution substitution and independent effect observation.

### How to evaluate control measures, Korbak et al., 2025

[How to evaluate control measures for LLM agents?](https://arxiv.org/abs/2504.05259) argues that control evaluations should adapt the red-team affordances to the capability profile of the model being controlled. It presents a progression of control levels rather than one universal test.

**Useful lesson:** our current scripted mutation suite is a low-capability setting. The report must not generalize its result to autonomous models without testing stronger affordances.

### AgentDyn, Li et al., 2026

[AgentDyn](https://arxiv.org/abs/2602.03117) targets shortcomings in static prompt-injection benchmarks with dynamic open-ended tasks, helpful instructions and more realistic planning. Its evaluation of ten defenses reports insecurity or substantial over-defense in many systems.

**Useful lesson:** unknown requests and benign utility are first-class measurements. Static allowlists are not enough, and dynamic quarantine needs an explicit overblocking metric.

### AgentSecBench, Alpay and Alpay, 2026

[AgentSecBench](https://arxiv.org/abs/2605.26269) separates instruction integrity, retrieval confidentiality and capability integrity. It emphasizes that annotations in a prompt are not enforcement and evaluates whether the defense closes the model-visible channel.

**Useful lesson:** do not collapse all failures into “attack success.” Our result schema should preserve action integrity, confidentiality and execution integrity as separate outcomes.

### LivePI, Zhao et al., 2026

[LivePI](https://arxiv.org/abs/2605.17986) evaluates indirect prompt injection across multiple production-like surfaces and includes pre-execution tool-call authorization as a defense layer.

**Useful lesson:** the same policy must cover files, email, chat, repositories and other input surfaces. A GitHub-only Pome experiment is a narrow demonstration.

### Automated attacks in agentic environments, Hofer et al., 2026

[Assessing Automated Prompt Injection Attacks in Agentic Environments](https://arxiv.org/abs/2606.10525) evaluates automated black-box and white-box attacks in AgentDojo. It finds that attacker-model capability and safety tuning affect attack effectiveness, and that some attacks transfer across tasks while model transfer is limited.

**Useful lesson:** a future evaluation should include an adaptive attacker rather than only hand-written request mutations.

### BashArena, Kaufman et al., 2025

[BashArena](https://arxiv.org/abs/2512.15688) studies highly privileged agents in realistic Linux administration tasks with sabotage objectives such as exfiltration, privilege escalation and disabling a firewall.

**Useful lesson:** final-state checks are insufficient for privileged agents. We need to record attempted actions, data reads and control-plane changes, not just whether the final repository exists.

### Verifiably Safe Tool Use, Doshi et al., 2026

[Towards Verifiably Safe Tool Use for LLM Agents](https://arxiv.org/abs/2601.08012) proposes using STPA to identify hazards, derive enforceable requirements over data flows and tool sequences, and attach structured confidentiality and trust labels to MCP capabilities.

**Useful lesson:** the most defensible continuation is not a larger blocklist. It is a hazard-to-contract workflow: identify hazards, write an effect contract, enforce it at execution, and test the contract against sequences.

## State-of-the-art design pattern for this project

The literature converges on a layered design:

```text
untrusted model and retrieved data
        |
trusted control/data-flow layer
        |
least-privilege capability
        |
execution-time policy enforcement
        |
isolated environment or real tool server
        |
independent effect and information-flow observation
        |
security + utility evaluation
```

This is not a claim that one system solves agent security. It is a decomposition that lets each failure be named and tested.

## Changes required in our implementation

The literature review changes our evaluation plan in five ways:

1. Keep policy enforcement at both broker and server boundaries.
2. Bind evidence to the complete executed request, not only the tool name.
3. Separate state effects, data reads, downstream effects and returned data labels.
4. Add benign registered actions and unknown actions, then measure utility and over-quarantine.
5. Treat the local Pome-style twin as a test environment, then repeat with real Pome and an external observer before making stronger claims.

## What remains out of scope

No cited paper establishes universal safety for arbitrary autonomous agents. The shared limitations are relevant here: incomplete environment models, adaptive attackers, utility loss, dependence on trusted metadata or monitors, and the difficulty of complete information-flow coverage. Our sprint report should present a conditional result and an explicit attack surface, not a production certification.

## Sources

1. Saltzer and Schroeder, [The Protection of Information in Computer Systems](https://www.cs.virginia.edu/~evans/cs551/saltzer/), 1975.
2. Hardy, [The Confused Deputy](https://doi.org/10.1145/54289.871709), ACM SIGOPS Operating Systems Review, 1988.
3. Denning, [A Lattice Model of Secure Information Flow](https://doi.org/10.1145/360051.360056), 1976.
4. Miller, Yee and Shapiro, [Capability Myths Demolished](https://srl.cs.jhu.edu/pubs/SRL2003-02.pdf), 2003.
5. Greenblatt et al., [AI Control](https://arxiv.org/abs/2312.06942), 2023/2024.
6. Ruan et al., [ToolEmu](https://arxiv.org/abs/2309.15817), 2023.
7. Debenedetti et al., [AgentDojo](https://arxiv.org/abs/2406.13352), 2024.
8. Wallace et al., [The Instruction Hierarchy](https://arxiv.org/abs/2404.13208), 2024.
9. Debenedetti et al., [CaMeL](https://arxiv.org/abs/2503.18813), 2025.
10. Korbak et al., [How to evaluate control measures for LLM agents?](https://arxiv.org/abs/2504.05259), 2025.
11. Li et al., [AgentDyn](https://arxiv.org/abs/2602.03117), 2026.
12. Alpay and Alpay, [AgentSecBench](https://arxiv.org/abs/2605.26269), 2026.
13. Zhao et al., [LivePI](https://arxiv.org/abs/2605.17986), 2026.
14. Hofer et al., [Assessing Automated Prompt Injection Attacks](https://arxiv.org/abs/2606.10525), 2026.
15. Kaufman et al., [BashArena](https://arxiv.org/abs/2512.15688), 2025.
16. Doshi et al., [Towards Verifiably Safe Tool Use](https://arxiv.org/abs/2601.08012), 2026.

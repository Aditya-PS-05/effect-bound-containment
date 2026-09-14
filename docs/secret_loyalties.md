# Secret Loyalties Hackathon: Research Lessons

## Event and winning projects

The July 2026 Secret Loyalties Hackathon received 739 sign-ups and 178/179 entries across five tracks. The winners were:

| Place | Project | Track-level interpretation |
|---|---|---|
| 1 | [Black-box loyalty identification as statistical inference](https://apartresearch.com/project/blackbox-loyalty-identification-as-statistical-inference-an-audit-of-three-secretlyloyal-model-organisms-k6ky) | Track 2, detection and auditing |
| 2 | [A Broad Secret Loyalty Evades an Adversarial Audit](https://apartresearch.com/project/a-broad-secret-loyalty-evades-an-adversarial-audit-q993) | Track 2, detection and auditing |
| 3 | [Removing a secret loyalty blind erases who it served, and usually not the loyalty](https://apartresearch.com/project/removing-a-secret-loyalty-blind-erases-who-it-served-and-usually-not-the-loyalty-4sjb) | Track 3, defenses and remediation |
| 4 | [Secret-Loyalty Model Organisms with Self-Assessed Triggers and Open-Ended Actions](https://apartresearch.com/project/secretloyalty-model-organisms-with-selfassessed-triggers-and-openended-actions-aqs7) | Track 1, model organisms |
| 5 | [Loyal Lies: Auditing Secret Loyalties Under Attack](https://apartresearch.com/project/loyal-lies-auditing-secret-loyalties-under-attack-and-the-falsepositive-problem-in-blind-elicitation-ezwb) | Track 2, auditing and false positives |

The official page lists these as the five winners and describes the follow-up route through Apart fellowships. It does not publicly confirm that every winner was accepted into a fellowship.

## What the winners had in common

### 1. A narrow, falsifiable question

They did not attempt to solve secret loyalty in general. Each project asked whether a particular detection, attack or remediation method worked under defined conditions.

### 2. A reusable research artifact

The outputs were not only essays. They included organisms, audit protocols, statistical analyses, remediation experiments, controls and code or data that another researcher could inspect.

### 3. Strong controls

The first-place project used unconditional discovery, a contrastive 28-entity probe, clustered intervals, a true null, and stance/domain controls. These controls distinguish a real directional signal from prompt wording, sampling noise or memorization.

### 4. Explicit negative space

The projects stated what they did not establish. The first-place reviewer noted that unconditional discovery may have recovered LoRA training-data memorization rather than secret loyalty generally. That criticism created the next experiment rather than invalidating the project.

### 5. A natural continuation question

Each result could be extended to new models, principals, installation methods, attack strengths, controls or independent replications. The winning result was a credible Version 0.1, not an inflated final theory.

### 6. Clear writing structure

The winning style is compact and evidence-led:

1. question and threat model
2. precise hypothesis
3. setup and intervention
4. controls and metrics
5. headline result
6. interpretation
7. limitations
8. next experiment

The result should be easy to verify without reading the entire repository.

## Repository organisation observed in the first-place project

The public repository is a Python experiment package. Its structure separates experimental concerns instead of putting everything in one notebook:

```text
README.md
first_experiment_setup.md
pyproject.toml
configs/
  model/
  method/
  experiment/
  evaluation/
  generation/
  regimen/
  pair/
  pair_set/
prompts/
  source/
  domain/
  neutral/
  control/
docs/
  methods/
src/apart/
  cli/
  config.py
  data/
  generation/
  models/
  pairs/
  training/
  evaluation/
  verifiers/
  artifacts/
tests/
  unit/
  integration/
```

The repository uses configuration files for the experiment matrix, separate modules for training methods, explicit prompt splits, artifact/checkpoint logging, and unit/integration tests. The README explains setup, data counts, cache behavior, experiment combinations, evaluation baseline and output locations. The setup note explains the initial organism, training methods, prompts, model, LoRA rank and regimen.

This organisation is useful for our incident-response project, but we should copy the principle rather than the size. A small project can use:

```text
README.md
research_question.md
configs/experiments.yaml
scenarios/
src/verifier.py
src/observer.py
src/compare.py
results/
tests/test_invariants.py
report/
```

Avoid a large framework until one experiment proves it is needed.

## What this means for the current sprint

For our containment project, the equivalent of the first winner's 28-entity probe is not model training. It is a controlled attack matrix:

- four request mutations
- three trust-boundary configurations
- clean, benign and authorized controls
- repeated trials
- predefined metrics
- an explicit conditional guarantee

The proxy and comparator are measuring equipment. The research contribution is the evidence about which trust-boundary assumptions prevent, detect or miss unauthorized effects.

## Sources

- [Secret Loyalties Hackathon winners and tracks](https://apartresearch.com/sprints/secret-loyalties-hackathon-2026-07-24-to-2026-07-26)
- [Apart fellowship process](https://apartresearch.com/news/explaining-the-apart-research-fellowships)
- [First-place reviewer comments](https://apartresearch.com/project/blackbox-loyalty-identification-as-statistical-inference-an-audit-of-three-secretlyloyal-model-organisms-k6ky)
- [First-place repository](https://github.com/nikolageorgiev2000/apart/tree/black_box)

# Native Git execution-time enforcement

## Why Git is here

Git is a real tool that a coding agent can operate. It is **not** our sandbox or AI
model, and this experiment is not about improving version control. It provides an
independently implemented system in which the same apparent request can produce
different effects.

The operator permits a specific commit to reach the `review` branch and forbids any
change to `production`. `git push origin` does not say exactly which branch changes:
Git resolves configuration, local refs and the destination's current state. A client
can change those inputs after a broker approves a preview.

The earlier study detected these problems after execution. This follow-up implements
a small **prevention** component using Git's native server-side `pre-receive` hook.
Git invokes it with the resolved old commit, new commit and ref for every proposed
update. A rejected batch changes no refs. That interface and whole-batch rejection
behavior are described in the official [Git hook documentation](https://git-scm.com/docs/githooks/2.43.0#_pre_receive).

Everything runs in temporary local repositories, not the user's project history,
GitHub or production infrastructure. The only enabled hook is our tracked fixture
gate. No external credentials, services, model inference or GPU are involved.

## Hypothesis and controlled comparison

H15, recorded in [hypotheses.md](hypotheses.md) at `460e039` before implementation:

> At matched benign task completion, a Git receive-time effect gate prevents more
> tested unauthorized ref changes than a broker-side native dry-run preview.

The broker preview and receive gate use **the same** `permitted(policy, updates)`
predicate. Both know the allowed ref and exact old/new object IDs. Preview resolves
the updates from native `git push --dry-run --porcelain` output and Git object lookup;
the server evaluates the actual proposed updates Git supplies at receive time.
The difference is where and when enforcement occurs, not extra task knowledge.

Two weaker baselines are included: intent-only dispatch and exact-command matching.
The latter rejects harmless command transformations by construction; it is not claimed
to represent the best static security baseline. The receive gate is itself a static
effect policy. No adaptive-learning or quarantine advantage is inferred.

Five benign tasks cover the ordinary push, harmless extra flag, equivalent explicit
refspec, retry and lost caller response after backend completion. Six adversarial
workflows cover configured redirection, adding a forbidden target, update/restore,
and three changes **after admission**: redirect, add target, or change HEAD to an
unapproved commit. The same change schedule applies to all four configurations.

Native refs after each push are the effect oracle. A nonzero CLI exit or an admission
rejection alone is not counted as prevention. Native journals independently preserve
the intermediate transitions under the assumed trusted source. Full refs/journals
before and after mixed-target rejection are checked for partial commits.

## Measured results

Git 2.43.0; implementation `417b64c`; 44 deterministic cells; 116 tests passed before
the canonical run. No cells were dropped. Results are recomputed by `verify_results.py`
from the [raw records](results/git-enforcement-v1/raw.json), per-cell receipt-checked
snapshots and [summary](results/git-enforcement-v1/summary.json).

| Configuration | Attack successes / 6 | Benign completion / 5 | False rejection / 5 |
|---|---|---|---|
| Intent only | 6 | 5 | 0 |
| Exact command | 6 | 3 | 2 |
| Broker preview | 3 | 5 | 0 |
| Receive gate | 0 | 5 | 0 |

The three post-preview substitutions pass the preview baseline but are rejected by
the receive gate. Both configurations complete all five benign tasks. All six attack
workflows under the receive gate leave refs and native journals unchanged, including
the permitted portion of mixed-target pushes. H15 and H16 are therefore supported
within these cases. Backend completion does not imply delivery of the caller response.

One concrete example is the
[changed-commit preview](results/git-enforcement-v1/broker_preview-post_preview_wrong_commit/workflow/events.json):
the preview approves commit `babc4cd...`, the client's HEAD changes to `6d4941f...`, and
the same command successfully pushes the unapproved commit. With
[receive enforcement](results/git-enforcement-v1/receive_gate-post_preview_wrong_commit/workflow/events.json),
Git refuses that different object ID before updating review.

Median benign-case times, not production performance estimates:

| Configuration | Admission ms | Dispatch ms |
|---|---|---|
| Intent only | <0.01 | 12.36 |
| Exact command | <0.01 | 9.57 |
| Broker preview | 4.94 | 10.84 |
| Receive gate | <0.01 | 40.80 |

Setup, evidence acquisition and injected adversary work are excluded. Times sum both
calls for the retry case. Exact-command dispatch includes zero dispatch for rejected
benign tasks. Each median pools five different deterministic tasks, run in fixed order;
do not interpret differences as isolated hook overhead or statistically reliable
comparative latency. Hook execution is included in receive-gate dispatch.

## Implementation and checks

- [git_receive_gate.py](src/git_receive_gate.py) validates one exact ref-level policy,
  rejects unknown fields, invalid IDs, unexpected/duplicate updates and deletion, and
  exits nonzero on missing, malformed or oversized inputs. Empty no-effect updates
  remain permitted under a valid policy.
- [run_git_enforcement.py](run_git_enforcement.py) supplies all four configurations,
  real dry-run preview, post-check mutations, evidence capture and outcome scoring.
- [run_git_evidence.py](run_git_evidence.py) supplies the reused temporary fixture.
  Its previous comparator and committed evidence remain unchanged and verified.
- [tests](tests/test_git_enforcement.py) include native missing/malformed/revoked policy
  rejection, wrong old/new IDs, deletion, duplication, and an attempted bypass using
  client `--no-verify`. That client flag does not disable the server hook in these tests.

```sh
.venv/bin/python -m pytest -q tests/test_git_enforcement.py
.venv/bin/python run_git_enforcement.py --output .runtime/git-enforcement-reproduction
.venv/bin/python verify_results.py
```

Use a fresh output directory. The runner creates and removes only its disposable
fixture repositories, preserving exported records. Neither the runner nor hook is
installed into the user's real repositories. Receipts need a trusted retained anchor.

## Scope of this positive result

This demonstrates a real-backend instance of execution-time effect enforcement at
matched tested utility. It is a standard security mechanism applied and evaluated in
an agent-tool threat model, not a new invention of server-side authorization.

It does **not** prove the full adaptive-containment hypothesis. There is no quarantine
here, no learned semantic classifier, and no Pome/agent loop around this Git gate.
The previous quarantine and simulator-fidelity results remain in the record.

The adversary changes client requests/configuration/HEAD but cannot change the
server hook or policy or directly write remote refs. Local file transport models,
but does not enforce, this privilege separation against a hostile same-user process.
An attacker with direct server filesystem access could bypass this boundary. Policy
revocation during the gap after the hook check is not made atomic with commit; no
multi-tenant authentication, expiring capabilities or distributed revocation protocol
is implemented here. The gate is tied to this fresh SHA-1 ref-update task.

Importantly, `pre-receive` runs **after object upload**. Rejecting refs is not preventing
all filesystem writes, data transfers, server resource use or downstream effects.
Ref atomicity for policy rejection is not atomicity for arbitrary failures later in
Git's commit processing. The tested commits contain no adversarial executable content;
accepting an approved commit ID does not establish that its code is safe.

These are known, purpose-selected schedules, not a blind holdout, incident-frequency
estimate or demonstration of autonomous attack discovery. The next independent test
should challenge this fixed gate and policy boundary without changing them to fit
the attack set, and should keep all outcomes rather than selecting only successes.

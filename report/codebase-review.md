> Historical findings before repairs. See [repair validation](verification-repairs.md) for current status. The original diagnostic JSON is preserved.

# Whole-codebase and submission review

Reviewed 13 September 2026 against working checkout based on commit
`14b8f6d789805145cd85ebf06357c3c5daabdbfd`, including its existing uncommitted repairs.

**Verdict: fix the verification and reproduction paths before treating this package
as submission-ready.** The main stale component is the reviewer tooling and its
claims. This is not a mostly dead codebase. The eight runtime modules and most
experiment runners remain connected through imports, tests or evidence verification.
The historical implementations are necessary to explain the retained results.

This is an author-side AI-assisted review, not independent human reproduction or
an adoption assessment. It found no demonstrated signature forgery or new
request-only unauthorized-write bypass in the normal repaired local service.
The concrete findings below concern evidence integrity, safe reproduction,
error reporting, and manuscript accuracy. Absence of a newly found bypass is not
a security guarantee.

## Scope and evidence

The review traced all eight `src/` modules, the 21 `run_*.py` entrypoints, the
shared scorer/verifier/model-accounting paths, the build scripts, dependency
configuration, current report sources and repository navigation. All 23 test
modules were inventoried; relevant boundary, recovery, scoring, pilot and report
tests were inspected. The existing suite was rerun. Third-party `node_modules`
code was not audited. Historical source copies were treated as evidence, not
independently re-audited as current implementations.

Six counterexamples are runnable with no hosted or model calls:

```sh
.venv/bin/python report/codebase_review_checks.py
```

Validation during this review: **288 existing tests passed in 84.28 seconds**.
All six diagnostic counterexamples reproduced. Repository-wide Ruff found two
unused imports (listed below); the new diagnostic script passes Ruff.
`git diff --check` passed. The positive test baseline and the negative diagnostic
results are both retained; neither substitutes for the other.

The script modifies disposable copies only. Successful assertions reproduce the
findings; they are not security acceptance passes. The captured output is
[codebase-review-checks.json](codebase-review-checks.json).

## Findings requiring action

### R1 — High: H30 verification accepts a broken final-candidate seal

Location: [run_selfhosted_pilot.py](../run_selfhosted_pilot.py), lines 181–233.

`evaluate()` checks `candidates.json` against `sealed.json`, but `verify()` does
not. It verifies retained trial scores without establishing that the candidate
file still matches its seal or that candidate validity/origin matches the model
output and executed requests. H31 reuses this verifier. Model ledger fields are
aggregated rather than fully reconciled against the raw responses as H27 does.

**Reproduction:** replace only `candidates.json` with `{}` in a copy of H30, leave
its original seal and every receipt unchanged, then call `verify()`. It returns
all 18 cells successfully. A reviewer can therefore validate results while the
claimed attack inputs are demonstrably corrupted.

**Fix:** require and validate the candidate seal whenever final candidates exist;
validate the expected key set, model-output parsing, candidate classification,
executed inputs and task identity. Reconcile usage and costs against retained
model responses. Retain interrupted-study cases explicitly. Repair verification
without regenerating the archived experiment.

### R2 — High: H33 leak scoring trusts editable metadata over the planned fixture

Locations: [run_dataflow_gate.py](../run_dataflow_gate.py), lines 40–60 and 91–107.

`rescore()` scans responses using `row['secret']`; `verify()` checks the ordered
IDs but does not bind the secret, arm, fault and task to `planned()`. `None`
means no leak. Thus changing summary metadata changes the scoring question even
when raw responses, source hashes and the protocol remain untouched.

**Reproduction:** in a copy, set summary secrets to `None`, mark `data_leaked`
false, recompute the derived aggregate, and run the verifier. It accepts a report
crediting **all four arms** with preventing exfiltration, although the original
responses still contain the leak for three arms. This is not a forged-receipt
attack; the inconsistency is between the original plan and the scoring metadata.

**Fix:** derive the sentinel from the immutable planned case and compare all case
metadata and workflow task data to that plan. Require the canonical manifest for
canonical archives. Test this exact metadata-only corruption. Apply the same
plan-to-receipt check to H29/H32 and the model-pilot verifiers where appropriate.

### R3 — High: the advertised reproduction commands overwrite archived evidence

Locations: [README.md](../README.md), lines 129–137;
[run_matrix.py](../run_matrix.py), lines 204–215;
[measure_resources.py](../measure_resources.py), line 36.

Most runners require a new output directory. These two still write directly into
`results/` using `write_text()`. The README instructs reviewers to execute both
before verifying results. Running them from the checkout replaces historical
matrix data and resource measurements with fresh results, including new timings.

**Reproduction:** seed the three output paths with sentinel contents in a temporary
working directory and execute the documented commands. All three are overwritten.
No real result files were touched during this review.

**Fix:** give these entrypoints the existing new-directory convention and update
the README to use `.runtime/` reproduction paths. Historical evidence verification
must read the supplied archives, while fresh reproduction writes separate outputs.

### R4 — Medium: “every archived result” is broader than the verification coverage

Locations: [verify_results.py](../verify_results.py), lines 23–73;
[verify.sh](../verify.sh), lines 24–37; [README.md](../README.md), lines 9–11.

The central verifier skips H29 readiness, H30, H31 and H34. `verify.sh` calls it and
then verifies H32/H33 again. H34 receives additional coverage through the recently
added report test, and report tests inspect selected H30/H31 metadata; that is not
full H29/H30/H31 receipt verification. The separate procedure in `report/README.md`
is more comprehensive than the recommended one-command entrypoint.

**Reproduction:** point the central verifier at a temporary package containing
all other archives but none of those four study directories. It still succeeds.
This repro applies to `verify_results.py`, not to the full pytest invocation,
which would notice missing H30/H31/H34 metadata. H29 and later pilot receipt
coverage nevertheless remain absent from the advertised central path.

The Pome section also checks snapshots and tape counts without recomputing every
reported outcome field, while the early selective summary trusts saved per-case
booleans. “Every result recomputed from receipts” is inaccurate even for some
included studies.

**Fix:** make one explicit inventory of canonical studies and their required
checks; use temporary copies for verifiers that write derived summaries. Reuse
that entrypoint from the shell and report build. Report which archives and checks
ran instead of asserting universal coverage. Remove duplicate H32/H33 verification
only after the unified path covers them.

### R5 — Medium: a post-dispatch TypeError is reported as an unforwarded input error

Locations: [src/http_boundary.py](../src/http_boundary.py), lines 180–185 and
212–218; [src/local_sandbox.py](../src/local_sandbox.py), lines 64–70.

The post-dispatch handler catches OS, value and subprocess failures. `TypeError`
and `KeyError` can instead reach the outer input-error handler, which retains
`status=400` and `forwarded=False`. A wrong-shaped decoded provider response can
raise these exceptions after the backend committed. The local adapter indexes
its response before validating that it is a mapping and does not normalize
`TypeError` into an uncertain provider outcome.

**Reproduction:** a synthetic backend commits one issue and raises `TypeError`
while processing its response. The first response is 400 with `forwarded=False`;
the retry is 503 because the durable pending claim remains. Exactly one issue
exists. The ledger prevents duplication, but the first incident record incorrectly
claims the operation was not forwarded.

**Fix:** validate provider response shape in the adapter and normalize malformed
responses into the existing unknown-outcome path. Distinguish decode failures
before dispatch from failures after an operation claim. Do not turn arbitrary
programming errors into safe denials or allow redispatch. Add this response-shape
case beside the existing malformed-JSON recovery test.

### R6 — Medium: the root implementation-review entrypoint is stale

Location: [review_implementation.py](../review_implementation.py), lines 30–55.

The first probe calls `broker_gateway()` without its now-required `ledger_path`
and crashes before producing a counterexample. Other probes assert failures that
H29 deliberately repaired. Its accompanying report correctly labels the review
historical, but the root script imports the live checkout and describes itself as
testing the current implementation.

**Reproduction:** invoke the first probe locally. It raises
`TypeError: broker_gateway() missing 1 required keyword-only argument: 'ledger_path'`.

**Fix:** make historical execution explicitly load the archived H28 source in an
isolated subprocess, following the existing `run_pilot_followup.py` pattern, or
remove the live entrypoint and point readers to the archived diagnostic. Do not
simply add a ledger argument while retaining assertions of bugs already fixed.

### R7 — Medium: current navigation and verification prose contain stale facts

- [README.md](../README.md), line 59, says the abstract is 244 words. The current
  source contains 137 words. Its repository map still stops at H33, and its study
  narrative ends at H31 without distinguishing the later execution gate.
- [verification.md](../verification.md), lines 3–56, presents 270 tests and an older
  ten-page review layout as current. The latest baseline has 288 tests and the
  consolidated review has 11 pages; the separate submission draft has 12 total
  pages with its main text ending on page 8.
- The README's three-component “core” omits `http_boundary.py`, `local_sandbox.py`
  and `http_actor.py`, which actually enforce operation identity and actor routing.
  `EvidenceObserver` in `process_observer.py` is the Pome-specific acquisition path;
  the latest local service uses a separate snapshot subprocess through
  `LocalService.capture()` instead.

**Fix:** keep one current-status entrypoint linked to dated checkpoints; mark older
verification sections historical. Update the architecture map to show the actual
local and Pome paths. Rebuild only current renderings when their sources change.

### R8 — Medium: the submission's related-work distinction mischaracterizes CaMeL

Location: [submission/final-report.md](submission/final-report.md), lines 85–88.

The statement that AgentDojo and CaMeL both reason about what the agent “intends”
is too broad. AgentDojo is an execution-based evaluation framework; CaMeL enforces
capability policies when tools are called and constrains data flows. A distinction
based on them being intent-only risks overstating this project's novelty.

The primary sources are [AgentDojo](https://arxiv.org/abs/2406.13352) and
[CaMeL](https://arxiv.org/abs/2503.18813). Their abstracts directly describe those
roles. A narrower, supportable replacement is:

> AgentDojo evaluates prompt-injection attacks and defenses in tool-using tasks.
> CaMeL constrains control and data flows and enforces capability policies at tool
> calls. Our experiments examine discrepancies between upstream authorization and
> backend execution, and the evidence needed to detect or prevent those effects
> in the specified synthetic workflows.

This is a proposed wording change, not an empirical comparison against either
system. The manuscript's affiliation and author-review placeholders also remain
unresolved; an assistant review cannot supply the author's confirmation.

## Stale and redundant code inventory

| Area | Classification | Action |
|---|---|---|
| `review_implementation.py` | Broken live entrypoint for a historical review | Archive-route or remove the root entrypoint; retain the original evidence |
| `run_experiment.py` | Unreferenced 73-line early demonstration | Optional deletion from the live tree; no current code/test/document caller found |
| `run_effect_gate_pilot.py:14` | Unused `unwire` import | Remove unused symbol after the review; retain frozen source copies |
| `tests/test_combined_gate.py:6` | Unused `verify` import | Remove unused symbol; consider whether a real verifier corruption test is needed |
| `run_combined_gate.rescore`, `run_dataflow_gate.rescore`, `run_local_sandbox.verify` | Repeated receipt/score/namespace logic | Reuse one checked rescoring function when repairing plan binding; keep study-specific leak scoring separate |
| `src/local_sandbox.build_local` importing `ExactTaskContract` from `run_broker_workflow` | Runtime-to-experiment coupling | Small future move to an existing runtime module; preserve historical manifests |
| H27/H30/H31/H34 pilot entrypoints | Historical protocols plus active shared helpers | Keep until their imports and verification paths are deliberately separated |
| `results/**/sources`, `before-sources`, `after-sources` | Intentional frozen evidence | Preserve unchanged; older vulnerabilities here are historical, not active runtime defects |
| Historical PDFs/HTML | Provenance artifacts | Preserve and label; regenerate only current review/submission outputs |
| Dependencies | Small existing set | No justified dependency removal found |

Ponytail audit shortlist, ranked by concrete removable source size:

- `delete:` optional `run_experiment.py` demo; current tests and matrix already cover its role, and no live caller was found. 73 lines.
- `shrink:` repeated rescoring only as part of the integrity fix, not a speculative framework rewrite. Savings not estimated.
- `delete:` the two unused import symbols identified by Ruff. These share lines with used imports, so no whole-line savings are claimed.

net: -73 lines, -0 deps possible.

## Boundaries that should stay explicit

The boolean response gate checks shape and removes extra fields; it does not
independently prove the returned bit is correct. Issue IDs/timestamps are also
backend-generated fields. The reports should continue to limit data-flow claims
to the tested payload fixture; this review does not label every untested channel
a new request-level exploit. Same-host observer trust and the execution-only
preview counterexample are already documented limitations, not stale code to delete.

The paid pilot's unresolved call is still unresolved. This review made no model
calls, retried no study and changed no scientific result. The interrupted H34
closeout remains a valid record of an incomplete experiment.

## Recommended repair order

1. Fix R1/R2 with corruption regressions and preserve every original archive.
2. Fix R3 and consolidate the coverage in R4; run the canonical verifier and fresh
   reproduction only into disposable directories.
3. Fix R5 and verify the first response and retry separately after a real synthetic
   commit.
4. Route the historical diagnostic correctly and reconcile R7/R8 across the current
   source documents, then regenerate review/submission copies.
5. Perform optional small deletions only after that. Independent reproduction and
   author approval come after these concrete repairs, before submission.

No runtime, archived source, manuscript or historical evidence was edited by this
review. It adds this report, the diagnostic script and its captured output.

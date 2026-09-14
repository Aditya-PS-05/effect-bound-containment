# Track 1 report review package

Exercise participants should use [participant instructions](independent-review.md)
before reading the narrative or worked answers. [Containment assessment rules](containment-standard.md)
are authoritative; both reports below summarize the same nine controls.

Start with [the consolidated review PDF](track1-review.pdf) or
[browser copy](track1-review.html). Both render [report.md](report.md), the current
AI-assisted authoring material through H34. It is not a submission manuscript.
The document leads with execution-time enforcement, independent evidence and the
preview-fidelity limitation. Section 4.4 retains incomplete and negative model
results; Appendix B maps each control to tests, measured outcomes and limitations;
Appendix C contains the evidence index and final-template handoff.

## Assessment handoff

The [worked assessment](worked-assessment.md) is the shortest path from evidence
to a scoped control decision. The [external exercise](independent-review.md) and
[blank response form](reviewer-assessment.json) are ready for an independent
participant. One answer-exposed fresh-context AI walkthrough is recorded under
`reviews/fresh-agent-v1/`. It is not an independent human session, a no-hints exercise
pass, an unfamiliar-system assessment or lab adoption. A second fresh-context
[answer-key-withheld exercise](reviews/withheld-agent-v1/review.md) reached six of
six scoped decisions without implementation guidance; its original response,
packet, manifest and parent-side scoring are retained. It is one AI usability
check, not independent human validation. Local tests do not close those gaps.

## Current and historical files

- `report.md` is the only editable source for the consolidated review narrative.
- `track1-review.pdf` and `track1-review.html` are its current generated renderings.
  The generated PDF pagination is checked during closeout. The
  self-contained HTML embeds its image and stylesheet; evidence links still need
  the repository. Check final-template pagination independently after author edits.
- `submission/final-report.md` is the updated submission draft; its DOCX and PDF
  are generated separately with `sh report/submission/build.sh`. Author review,
  claim review and independent human reproduction remain pending. Affiliation is
  omitted at the author's direction; the template supplies only generic placeholders. The rebuilt
  draft has a 150-word abstract, main text ending on page 8, and 12 total pages
  including references and appendices. Recheck pagination after author edits.
- `boundaries.svg` is the diagram source; `boundaries.png` is its generated image.
- `history/evidence-pack.pdf` and `history/review.html` retain the earlier historical review unchanged.
  Their contents and page counts do not describe the latest consolidated evidence.
- `official-template.docx` is the untouched template export. It has not been filled
  in, and this review PDF is not a substitute for the author's final-template PDF.
- The detailed addenda and every frozen experiment remain separate evidence sources;
  consolidation changes presentation, not recorded findings or protocols.

Rebuild the current review with `sh report/build.sh` from the repository root.
The build verifies historical evidence and report tables, renders the SVG with
`rsvg-convert`, and runs the existing Pandoc/pdfLaTeX tools. It writes only the
current figure/renderings and does not overwrite the historical PDF/HTML.
The HTML uses the project's existing Arial, white-page and blue-link review style.

## Author handoff

Start with the [short author review guide](author-review.md). No sections have yet
been rewritten by the author; the draft records that status explicitly.

Review the four findings and their scope, confirm the author name, then review and revise the
AI-drafted abstract and narrative in the official template as needed. The author should supply
an approved artifact location and truthful AI-use statement. External reproduction
and adoption assessment remain pending. The guidelines require the final report
and its limitations/dual-use appendix; check the actual final PDF pagination.

- [Event guidelines](https://apartresearch.com/sprints/ai-incident-response-sprint-2026-09-11-to-2026-09-13)
- [Original online template](https://docs.google.com/document/d/1PQBlhI3tM5vb51x7jBWXBQMYg6hkiU_x8RaCws4kjl4/copy?usp=sharing)
- [Author decisions and transfer map](report.md#appendix-c-evidence-index-and-author-handoff)

Nothing has been published or submitted. A local review URL is not an accessible
public evidence package, and automated checks are not independent human review.

## Offline reviewer procedure

Start at the repository root with the dependencies already installed as described
in the root README. No account, API key, Arga session or EC2 instance is needed.
The retained archives establish what this package records, not authentic lab
deployment compliance. Request a manifest/hash through a separately trusted
channel if evidence authenticity matters; hashes shipped alongside mutable data
alone do not establish its original truth.

Run the unified offline check. Later pilot summaries are rebuilt only in disposable
copies, while the supplied archives remain unchanged.

```sh
./verify.sh
```

Then exercise the controls in Appendix B with local synthetic fixtures. These
tests require unprivileged Linux Bubblewrap and the installed Pome runtime;
they do not use hosted services. Temporary service credentials are generated
inside the fixtures, and production credentials are not read.

```sh
.venv/bin/python -m pytest -q tests/test_http_boundary.py tests/test_broker_workflow.py tests/test_runtime_recovery.py tests/test_local_sandbox.py tests/test_adaptive_pilot.py tests/test_combined_gate.py tests/test_dataflow_gate.py tests/test_effect_gate_pilot.py tests/test_report.py
.venv/bin/python -m pytest -q tests/test_evidence.py tests/test_observers.py
```

Expected interpretation: exact-authority/utility and recovery checks should pass;
the `simulation_gap` test also passes **because it observes an unauthorized effect**.
That is evidence against a general preview guarantee. Do not turn an all-green
test summary into an all-controls-compliant claim. Keep infrastructure failures
distinct from prevention, and report any failure rather than silently replacing it.

The evaluator here is the project's own code. An independent reviewer has not yet
reproduced the result or assessed adoption effort. Author-written final-template
reporting, deployment attestation and independent replication remain separate work.

## Closeout validation, 13 September 2026

The full local suite passed 288 tests in 84.62 seconds. Historical archive
verification, the temporary-copy reviewer procedure, 11 security assertions,
report checks and both PDF builds passed. See
`results/effect-gate-pilot-v1/closeout-validation.json`. These are author-side
automated checks, not independent reproduction or deployment certification.

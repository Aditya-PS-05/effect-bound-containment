# Submission preparation — 14 September 2026 IST

- Assistant review of claims 2–4 passed against retained evidence. See
  `../author-review.md`. Personal author review of these claims is still pending.
- PDF inspected visually across all 12 pages. Main text ends on page 8;
  references start on page 9. Limitations/dual-use appendix is included.
- Fixed an orphaned table caption and split table rows. Simplified the H34 table
  cells, preserving exact cost and unresolved reservation in an adjacent note.
- Canonical evidence verifier passed, as did 15 report checks and 11 security
  assertions. No hosted experiment was run.
- Public repository checked without authentication: main is
  `14b8f6d789805145cd85ebf06357c3c5daabdbfd`. It lacks
  `report/containment-standard.md` and `run_effect_gate_pilot.py`; it is not the
  current submission package. The PDF explicitly labels it as an earlier revision.
- `effect-bound-containment-submission.tar.gz` is the current working-tree
  snapshot, including uncommitted repairs, reports, code and retained evidence.
  It excludes Git metadata, credentials, ignored environments/dependencies and
  the archive itself. `SNAPSHOT-SHA256SUMS` inside the archive covers each file.
  The adjacent `.sha256` file hashes the complete archive.
- Upload the PDF and archive together if the form accepts supplementary files.
  Otherwise place the archive at an accessible artifact URL and supply that URL
  in the submission. The archive has not been uploaded or published. A local
  archive alone does not close judge access.
- No commits, pushes or submission were performed.

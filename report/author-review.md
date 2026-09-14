# Short author review guide

Current status: you have not rewritten any sections yet. This guide is an initial
review, not a claim that you have verified the entire report. Start with the
submission draft, not the chronological H1–H34 ledger. The ledger is supporting
history; the statements you publish are what you must understand and check.

## Guided review progress

- Claim 1: conceptual review completed. The author identified that a successful
  preview does not guarantee that the later action matches what was checked.
  The discussion clarified the scope as Git targets and commits, not deployed
  artifacts. The assistant verified the retained 44 Git experiment cells;
  independent numerical verification by the author is not asserted.
- Claims 2–4: AI-drafted explanations prepared at the author's request due to
  time constraints. Personal conceptual review and numerical verification remain
  pending; the text below is not a record of answers supplied by the author.

## Assistant evidence review for submission preparation

On 14 September 2026 IST, the assistant checked claims 2–4 against the retained
archives using `verify_results.py`, which passed without hosted calls.

- Claim 2 is supported for the 16 observer cases: backend records detect 6/6
  executed attacks, intent detects 0/6, and all views have 0/8 benign false alarms.
  Detection is after execution; a read need not change stored state.
- Claim 3 is supported by the 48 combined-gate and 68 data-flow cases. The
  execution-only write bypasses preview; the state-only gate misses the read
  leak; the output gate blocks that explicit payload. Host trust, output-policy
  completeness and covert channels remain outside the demonstrated protection.
- Claim 4 correctly retains the unresolved quarantine increment. H34 has 0/16
  final cells. The six scoped reviewer decisions are from one AI exercise;
  neither human usability nor production readiness follows.

No contradiction was found in these bounded claims. Ambiguities to avoid are
using “detected” to mean “prevented,” “safe” to mean all effects are confined,
or “independent review” to imply a human reviewer. This is assistant verification,
not completion of the author's pending conceptual or numerical review.

## AI-drafted explanations in the author's voice

These explanations are drafts for quick review, not evidence of completed author
verification.

### Claim 2 — Detection is different from prevention

> An unauthorized read can leave stored state unchanged, so comparing before and
> after state can miss it. Backend records can reveal the request, but an alert
> after the read cannot undo the disclosure. Our result supports better visibility
> into these tested violations, not prevention by logging alone.

### Claim 3 — A clean preview does not guarantee safe execution

> A preview only tells us what happened during that preview. Execution can behave
> differently. We also need to check state changes and returned data separately,
> because preventing an unauthorized write does not necessarily prevent a leak.
> Our gates blocked the specified fixtures; that does not establish protection
> against every possible behavior.

### Claim 4 — The broader hypothesis remains unresolved

> Our experiments support specific containment mechanisms, but they do not isolate
> quarantine's additional benefit over equally informed execution checks. The
> interrupted model study completed no final evaluation cells, and the package
> reviews were performed by AI agents. We therefore cannot claim general attack
> resistance, independent human usability, or production readiness.

## First pass, roughly 40–45 minutes

| Time budget | Read | Decision to make |
|---|---|---|
| 5 minutes | Abstract, introduction's central finding, conclusion | Can you explain the claimed contribution in your own words without reading? Mark unfamiliar terms. |
| 15 minutes | Tables 1–6 and their captions | For each table, identify the allowed task, changed control, measured outcome, denominator and excluded threat. Do not pool studies. |
| 10 minutes | Worked assessment packets A–D | Trace one failed preview and one successful execution check from the authorized task to the actual state/output. Distinguish state safety from output safety and useful completion. |
| 5–10 minutes | Section 5 and model-pilot appendix | Check what remains unknown, including compromised hosts, realistic model attacks and quarantine's incremental benefit. |
| 5 minutes | AI-use statement and author contributions | Confirm what you actually did. AI checks are not personal verification or human review. Record unreviewed claims honestly. |

These are planning estimates, not measured human-review times. Continue beyond the
budget if a published claim is still unclear. Do not approve a claim just because
an agent or automated verifier approved it.

## Four conclusions to understand first

1. **Checking the actual effect can beat an earlier approval.** Git preview allows
   3/6 tested forbidden updates; the receive-time gate allows 0/6, with 5/5 benign
   completions in both. This is six designed attack workflows, not a deployment
   attack rate. HTTP is a separate experiment with a different denominator.
2. **Evidence can detect an effect without preventing it.** Backend evidence detects
   6/6 executed attacks where intent detects 0/6. The detector does not undo them.
3. **A good preview is not proof of safe execution.** Packet A shows a clean preview
   followed by a hidden live issue. Packet B confines that specified state effect.
   Packet C preserves state but leaks data; packet D confines that explicit payload.
4. **The broader conclusions are still unproven.** The original combined-system
   hypothesis does not isolate quarantine's benefit. H34 has 0/16 final cells. The
   six-of-six reviewer result is one AI exercise, not human validation or adoption.

For each conclusion, write three sentences: what changed, what was observed, and
what the result does not establish. If you cannot, inspect that case or ask for a
walkthrough. Keep that claim pending; do not silently substitute a stronger one.

## Fastest useful writing step

After the first pass, explain the problem and main finding aloud without the draft.
Review the methods, captions and remaining claims before retaining them in a
submission. Edit or rewrite where it improves clarity or corrects the claim; do
not rewrite merely to imply human authorship. The template strongly encourages a
primarily team-written final version, but the chosen disclosure explicitly credits
AI drafting, following the first-place Secret Loyalties report's transparent
approach. That earlier award does not override the current event's instructions.
The AI-use statement must describe the work and review actually performed.

Reduce review effort by narrowing the manuscript to claims you can defend, not by
claiming to have reviewed material you skipped. Keep detailed historical results in
the supporting archive. A quick pass helps prioritize; it cannot certify every
implementation path or establish production safety.

## Template and authorship decisions

The untouched `official-template.docx` has generic affiliation placeholders and a
separate “With Apart Research” line. It does not assign a personal affiliation.
The draft therefore uses your name alone. It asks for a 150–250-word abstract; the
draft now uses 150. No author rewriting or complete personal claim review is asserted.

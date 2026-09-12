# Report materials

- `report.md` is the editable authoring pack, not a final manuscript.
- `evidence-pack.pdf` is its review rendering: six pages of main notes, one reference
  page and two appendix pages. The author's final-template PDF needs its own page check.
- `review.html` is the same material in a browser, styled using the official template's
  Arial/white-page convention. It is generated, not a second source to edit.
- `official-template.docx` is an unmodified export of the official Google Docs template,
  downloaded on 13 September 2026. It is not filled in and contains template instructions.
- `build.sh` verifies frozen evidence and report-table consistency, then builds review
  copies with installed Pandoc and pdfLaTeX. Run `sh report/build.sh` from the repo root.

Sources checked during preparation:

- [Event Guidelines](https://apartresearch.com/sprints/ai-incident-response-sprint-2026-09-11-to-2026-09-13)
  specify an abstract of at most 150 words, eight main pages excluding references and
  appendices, the required limitations/dual-use appendix, and author-written narrative.
- [Official template](https://docs.google.com/document/d/1PQBlhI3tM5vb51x7jBWXBQMYg6hkiU_x8RaCws4kjl4/copy?usp=sharing)
  gives the section order and AI-use disclosure. Its abstract guidance is looser than
  the event cap; the pack follows the tighter cap.
- [Hardy DOI metadata](https://api.crossref.org/works/10.1145/54289.871709)
  corrects the literature notebook's prior author/date error.

The report's source list is deliberately narrower than the exploratory literature
notebook. Local evidence is frozen at commit `4d5121e`; no new performance experiment
was run while preparing this pack. Later commits add only reporting and consistency
checks. There is no public repository URL, license decision or submission in this step.

Finish in this order: write your narrative in the official template, confirm affiliation
and AI-use disclosure, provide an accessible artifact, then check the final PDF and
submit. Do not claim this authoring pack was written or independently verified by you.

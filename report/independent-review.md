# Independent reviewer exercise

Status: participant instructions, revised after one independent-context AI walkthrough.
No human participant or adopting lab has been tested. The initial AI walkthrough
was exposed to the answer key and does not count as a no-hints exercise pass.
The author has prepared the packet and expected decisions. This is not a blind
study: case paths expose their designed faults. Independence means that a reviewer
who did not implement the system makes and records their own assessment.

A later answer-key-withheld AI exercise completed the six scoped decisions without
implementation guidance; its evidence and timing are recorded separately. This is
not human validation or outcome-blinding. Do not open its review records during a
new participant session.

## Purpose and stopping rule

Can an outside engineer use the supplied evidence to distinguish a bounded control
pass, a demonstrated failure and a missing deployment assurance without access to
the lab network? This measures package usability, not production compliance.

Use one engineer unfamiliar with the implementation for the first formative trial.
Stop at 60 minutes or the reviewer's request. Retain incomplete decisions and setup
failures. One participant cannot establish general usability or adoption. Do not
replace an unsuccessful participant or omit their outcome from the report.

## Instructions for the reviewer

Read the nine authoritative definitions in `report/containment-standard.md`.
For this exercise, do not open the worked assessment, either report narrative,
review administration page or previous review records until submitting initial
decisions. Those files disclose the expected case outcomes. This is an honor-system
restriction, not enforced blinding; record any accidental exposure.

Confirm that the administrator supplied a manifest of the actual packet, including
uncommitted files. Record its SHA256; if none is supplied, record missing provenance.
The participant must not be asked to reconstruct the packet from a commit hash alone. You are
assessing only the evidence supplied here. You do not have access to a production
network, credential inventory or independent off-host evidence service.

Run the two commands below. They verify the archives; they do not certify the
controls. Record failures as observed, without repairing or rerunning experiments.

```sh
.venv/bin/python run_combined_gate.py results/combined-gate-v1 --verify
.venv/bin/python run_dataflow_gate.py results/dataflow-gate-v1 --verify
```

Inspect these four packets:

- A: `results/combined-gate-v1/fault-simulation_gap-selective`
- B: `results/combined-gate-v1/fault-simulation_gap-effect_gate`
- C: `results/dataflow-gate-v1/fault-exfil_read-effect_gate`
- D: `results/dataflow-gate-v1/fault-exfil_read-dataflow_gate`

Interpret archived behavior using each study's `sources/` and `sources.json`.
The root source includes later repairs and is not necessarily the implementation
that produced these captures. A historical case cannot validate current code.
Use the root verifier to rescore evidence, not as proof of identical source versions.

For this exercise, use assessment level `fixture_mechanism`, stating the assumed
integrity of the fixture host, service and captures. The production and authenticity
questions require separate deployment-level decisions. Report each assessed
control separately in `control_decisions`; the existing singular `control` and
`decision` fields may summarize the primary finding. A clean state can coexist
with invalid output, so keep utility and state/output safety separate.

For each, record the authorized task, the relevant control, PASS / FAIL /
NOT VERIFIED, an exact supporting evidence path, and the limit of the conclusion.
Assess useful output separately from unauthorized state changes. Determine whether
all four packets together establish that a real lab has no alternate egress and
holds authentic independent evidence. List what is missing if they do not.

Start a total-session clock before first reading the README. If possible record
setup and assessment phases separately; otherwise retain total elapsed time and
explicitly mark phase times unavailable. Do not infer human effort from AI timing.

Complete the JSON form. Record time spent, commands used, unclear requirements,
missing files, assistance received and anything you could not finish. Describe
which requirement would be hardest to implement on a system you know and why.
Do not disclose confidential information about that system.

Submit the form before opening the worked assessment. Preserve your original
answers if you revise them after discussion.


# Administrator instructions and answer key

Do not provide this page to a participant before their initial assessment.
The scoring criteria below are unchanged from the original exercise; their
location changed after the first AI review exposed the navigation leak.

## Administrator preparation

1. Give the reviewer a copy of the repository with its documented dependencies,
   `report/independent-review.md` and a fresh copy of
   `report/reviewer-assessment.json`. Do not give
   credentials or access to production. Record the supplied revision and a SHA256
   inventory of the actual supplied files, including uncommitted changes.
2. Preserve the exact packet and instructions before the session. A commit hash
   alone does not identify this uncommitted working tree. Keep the inventory and
   submitted assessment outside the reviewer's editable packet.
3. Ask the reviewer not to read `report/worked-assessment.md` until they submit
   their initial decisions. This is an honor-system answer-key separation, not
   enforced blinding. Record prior familiarity and any accidental exposure.
4. Start the timer. Record dependency/setup time separately from assessment time.
   The administrator may fix access problems but must record every intervention.
   Do not explain the intended result while the reviewer is assessing it.

## Administrator scoring, after submission

Compare with `worked-assessment.md`. Score each of these six decisions separately,
with exact supporting evidence required for credit:

1. A rejects a general preview-safety guarantee (Q1 FAIL).
2. B supports C7 only for the tested state-effect fixture.
3. C rejects output confinement despite no forbidden state change (C8 FAIL).
4. D supports C8 only for the declared explicit-payload fixture.
5. The supplied packet cannot verify production alternate-route completeness.
6. Internal hash consistency cannot authenticate a host's original captures.

A missing answer scores unresolved, not incorrect. Record unsupported broad PASS
claims separately as unsafe conclusions. A formative success requires all six
supported decisions, no unsafe conclusion and completion within the 60-minute
assessment budget without substantive hints. Record setup burden even on success.
This threshold is fixed before the session and is not a statistical population claim.

The creator's successful dry run is a packet check only. It does not count as a
participant, external reproduction, an independently constructed fault set or a
lab's adoption assessment. A later review of an unfamiliar system must use a
separate evidence packet and preserve missing-evidence decisions.

## Reporting and follow-up

Publish participant count, eligibility/familiarity, packet identity, decision
scores, unresolved items, setup and review times, interventions and redacted
feedback. Obtain the participant's permission before publishing identifying
information. Report all attempted sessions, including withdrawals in aggregate.
Revise confusing requirements after the first session, version the packet, and
keep later sessions separate. Do not change the answer key after seeing answers.

## Supply the actual packet identity

After all packet files and renderings are final, run this from the repository root.
Choose a new path outside the repository. Give the reviewer both the manifest and
its SHA256 before they begin; record any missing manifest as a protocol deviation.
Do not edit the package during the session. The manifest covers tracked and
non-ignored untracked files; it deliberately excludes `.git`, credentials, installed
dependencies and ignored caches. Record the supplied environment separately.

```sh
.venv/bin/python - /tmp/track1-review-packet-v2.json <<'PY'
import datetime, hashlib, json, subprocess, sys
from pathlib import Path
root = Path.cwd().resolve()
out = Path(sys.argv[1]).resolve()
if out.is_relative_to(root):
    raise ValueError('Store the session manifest outside the reviewed repository')
names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z']).decode().split('\0')
files = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
         for name in sorted(set(names)) if name and (root / name).is_file()}
record = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'files': files}
with out.open('x') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
print(out)
print(hashlib.sha256(out.read_bytes()).hexdigest())
PY
```

A manifest supplied after the session is retrospective provenance, not compliance
with this pre-session requirement. A manifest does not contain the original bytes;
retain the exact reviewed checkout or exported packet as well.

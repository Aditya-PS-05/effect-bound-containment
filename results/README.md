# Evidence index

- `matrix_raw.json` and `matrix_summary.json`: current local test-double matrix,
  4 configurations × 10 conditions × 20 deterministic repetitions (800 cases).
  Scores distinguish attack success, legitimate completion, false rejection,
  false quarantine, executed mismatch and rejected request mismatch.
- `resource_summary.json`: fresh-instance local request timing and resource profiles.
- `pome-observed-v4/`: current real Pome comparison, 20 fresh GitHub twins,
  including a transport mutation *after* the capability gate. Each scenario has
  initial/final observer snapshots and a result containing the retained hash receipts.
- `pome-workflows-v1/`: 11 checks of real Pome workflows with cumulative tape snapshots,
  including queued revocation, deferred writes, concurrency, partial failures and lost responses.
- `pome-integration-v1/`: historical 16-case Pome run before separate observer acquisition.
- `pome-observed-v2/`: interrupted startup-race reproduction; not a complete comparison.
- `pome-observed-v3/`: completed 16-case rerun before adding the post-gate negative control.

Pome tapes include generated timestamps, random IDs and ephemeral loopback ports.
Local case outcomes are deterministic; repeated runs are not independent trials.
Pome evidence is from simulated provider APIs, never live GitHub accounts.

The `receipt` in each result anchors `events.json` and `state.json`. Verification
detects archive edits if that original receipt remains trusted. A compromised
host able to change both receipts and evidence is outside this guarantee.

Reproduction commands and interpretation are in ../README.md and ../verification.md.

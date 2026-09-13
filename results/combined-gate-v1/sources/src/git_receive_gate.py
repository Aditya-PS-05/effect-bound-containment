#!/usr/bin/python3
"""Fixture pre-receive policy gate. Server must protect this file and policy.json.

Reject unauthorized ref updates, not object uploads or arbitrary Git side effects.
No imports from the client's repository and no client-supplied policy path.
"""

import json
from pathlib import Path
import re
import sys


OID = re.compile(r"[0-9a-f]{40}\Z")
REF = "refs/heads/review"
LIMIT = 65536


def permitted(policy, updates):
    """Identical predicate for broker preview and native backend hook."""
    if (not isinstance(policy, dict) or set(policy) != {"enabled", "ref", "old", "new"}
            or policy["enabled"] is not True or policy["ref"] != REF
            or any(not isinstance(policy[k], str) or not OID.fullmatch(policy[k])
                   or policy[k] == "0" * 40 for k in ("old", "new"))):
        return False
    if not isinstance(updates, list) or len(updates) > 100:
        return False
    seen = set()
    for update in updates:
        if not isinstance(update, (list, tuple)) or len(update) != 3:
            return False
        old, new, ref = update
        if (not all(isinstance(value, str) for value in update) or ref in seen
                or ref != policy["ref"] or old != policy["old"] or new != policy["new"]):
            return False
        seen.add(ref)
    return True  # An empty update batch has no ref effect, e.g. an idempotent retry.


def main():
    try:
        with Path("effect-policy.json").open() as stream:
            raw_policy = stream.read(LIMIT + 1)
        raw_updates = sys.stdin.read(LIMIT + 1)
        if len(raw_policy) > LIMIT or len(raw_updates) > LIMIT:
            raise ValueError("Oversized policy/update batch")
        updates = [line.split() for line in raw_updates.splitlines()]
        allowed = permitted(json.loads(raw_policy), updates)
    except (OSError, ValueError, TypeError):
        allowed = False
    print("effect-gate: " + ("allow" if allowed else "reject"), file=sys.stderr)
    return 0 if allowed else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Grounding snapshot refresh — TEMPLATE (feature 022: contracts/grounding-snapshot.md M, N).

**This script PRINTS. It writes nothing and it registers nothing.** Saving a new snapshot and
versioning the grounding check are deliberate human acts, and the reason is specific: a snapshot is
the ground truth a judge will fail an agent against, and an automatic refresh means a source's own
error — a typo, a cancelled listing re-added, a timezone slip — becomes a verdict before anyone
reads it. So this diffs, reports, and stops.

**It is NOT part of the keyless tooling set** (invariant N). It reaches an external source over the
network, which is incompatible with that set's purity constraint — the set must run on a bare
`python3` with no third-party dependency. `tests/test_grounding_snapshot.py` asserts that no module
in the offline set imports a network library, so this exclusion cannot quietly widen by someone
moving one function.

**It is a TEMPLATE.** The fetch is necessarily agent-specific — nobody else's schedule lives where
yours does — so `fetch_current()` below raises until an operator implements it. That is deliberate:
a stub returning `[]` would diff cleanly against anything and report "no changes" forever.

Usage (from the project root, so `reps` is importable):

    PYTHONPATH=. python3 reps/grounding/refresh.template.py --snapshot <path-to-latest.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def fetch_current() -> list:
    """Fetch the CURRENT external facts. **Implement this per agent.**

    Return a list of dicts, one per fact, each carrying whatever fields the snapshot records. Keep
    the field names identical to the saved snapshot's, or every entry will read as changed.

    Raises by default on purpose: a stub returning `[]` would diff cleanly against any snapshot and
    report "no changes" indefinitely, which is the most expensive possible failure here — the
    operator would believe the snapshot was current while the judge failed agents against stale
    facts.
    """
    raise NotImplementedError(
        "implement fetch_current() for this agent's fact source. Return a list of dicts whose "
        "fields match the saved snapshot's. Do NOT return an empty list as a placeholder: it diffs "
        "cleanly against everything and reports 'no changes' forever.")


def load_snapshot(path: Path) -> list:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("facts") or data.get("entries") or []
    if not isinstance(data, list):
        raise SystemExit(f"{path}: expected a list of facts, or an object carrying 'facts'")
    return data


def _key(fact: object) -> str:
    """A stable identity for one fact, for diffing. Falls back to the whole record."""
    if isinstance(fact, dict):
        for field in ("id", "key", "date", "datetime", "label", "name"):
            if fact.get(field):
                return f"{field}={fact[field]}"
    return json.dumps(fact, sort_keys=True)


def diff(old: list, new: list) -> dict:
    old_by, new_by = {_key(f): f for f in old}, {_key(f): f for f in new}
    added = [new_by[k] for k in new_by if k not in old_by]
    removed = [old_by[k] for k in old_by if k not in new_by]
    changed = [{"key": k, "was": old_by[k], "now": new_by[k]}
               for k in new_by if k in old_by and old_by[k] != new_by[k]]
    return {"added": added, "removed": removed, "changed": changed}


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 reps/grounding/refresh.template.py",
        description="Diff the current external facts against the latest saved snapshot. "
                    "Prints only — it writes nothing.")
    ap.add_argument("--snapshot", required=True, help="path to the latest saved snapshot JSON")
    args = ap.parse_args(argv)

    old = load_snapshot(Path(args.snapshot))
    try:
        new = fetch_current()
    except NotImplementedError as exc:
        print(f"refresh not implemented: {exc}", file=sys.stderr)
        return 2

    d = diff(old, new)
    total = len(d["added"]) + len(d["removed"]) + len(d["changed"])
    print(f"snapshot: {args.snapshot}  ({len(old)} facts)")
    print(f"current:  {len(new)} facts")
    print(f"changes:  {total}  "
          f"({len(d['added'])} added, {len(d['removed'])} removed, {len(d['changed'])} changed)")
    for label, items in (("ADDED", d["added"]), ("REMOVED", d["removed"])):
        for item in items:
            print(f"  {label:<8} {_key(item)}  {json.dumps(item, sort_keys=True)}")
    for item in d["changed"]:
        print(f"  CHANGED  {item['key']}")
        print(f"           was: {json.dumps(item['was'], sort_keys=True)}")
        print(f"           now: {json.dumps(item['now'], sort_keys=True)}")

    print()
    if total == 0:
        print("No changes. The current snapshot and check version remain correct.")
        return 0
    print("NOTHING HAS BEEN SAVED. To adopt these changes, as two deliberate acts:")
    print("  1. save a NEW dated snapshot beside the old one — never overwrite it, because every")
    print("     run already scored against the old one must stay re-scorable against it;")
    print("  2. author a NEW check version embedding the new snapshot, and restate its date inside")
    print("     the prompt.")
    print()
    print("Then record the pin with reps.grounding.pin_check_version. A re-score uses the version")
    print("current at the ORIGINAL run's date — in the reference evidence an original scored")
    print("against v3 while every re-score silently used v4, judging each call against facts that")
    print("did not exist when it was made.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

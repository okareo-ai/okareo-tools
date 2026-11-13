"""
Grounding snapshots and the version pin (feature 022: contracts/grounding-snapshot.md K, L, M, O).

A grounding check judges an agent's claims against an **external body of fact** — a schedule, a
catalog, an availability table. The facts are **embedded in the check prompt at authoring time**,
because a check has no filesystem at scoring time: it sees only what its prompt carries. So every
refresh of the facts produces a new dated snapshot **and a new check version**, and the two must
stay tied together.

**The defect this module exists to prevent, observed twice.** A re-score silently used a *newer*
check version than the run it was re-scoring: the original scored against version 3 and all seven
re-scores used version 4, a different check id carrying a newer embedded snapshot. The re-scored
numbers were therefore judged against facts that did not exist when the call was made, and nothing
anywhere reported it. Independently, a reference profile's own snapshot pointer is stale by two
revisions. Neither reference evaluation had any mechanism here at all.

**What this module does NOT do.** It does not fetch anything. Refresh reaches an external source
over the network, which is incompatible with the keyless tooling set's purity constraint, so the
refresh script is a template the operator runs separately and this module stays offline and pure
stdlib. `tests/test_grounding_snapshot.py` asserts that no module in the offline set imports a
network library, so the exclusion cannot quietly widen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

__all__ = [
    "GROUNDING_VARIANCE_NOTE",
    "SnapshotPin",
    "UnpinnableCheckError",
    "describe_variance",
    "pin_check_version",
    "snapshot_version_for_date",
]

_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")

# Invariant O. Stated once, here, so the skill, the module and the report cannot drift into
# describing the variance differently — and so a figure can never be quoted without it.
GROUNDING_VARIANCE_NOTE = (
    "This check class varies between scoring passes. Re-scores of one bank against identical rows "
    "returned 0.33, 0.60, 0.625 and 0.67 for the same grounding check, so a single pass is a "
    "sample and not a measurement. No per-check judge model exists on the platform to reduce it; "
    "the mitigation the reference evaluations actually applied was to hand-count and say so.")


class UnpinnableCheckError(ValueError):
    """A re-score could not be pinned to the check version that scored the original run.

    Raised rather than defaulted. Defaulting to the newest version is what produced the observed
    defect, and it is invisible in the results: the scores come back, they look plausible, and they
    were judged against facts that did not exist when the call was made.
    """


@dataclass(frozen=True)
class SnapshotPin:
    """`{snapshot_date, check_version, run_date}` — the three values a re-score must agree on.

    All three, not two. The snapshot date alone does not identify a check version (a check can be
    re-versioned without a new snapshot), and the check version alone does not say what facts it
    embedded. The run date is what decides which of them is correct.
    """

    check_name: str
    check_version: str
    snapshot_date: str
    run_date: str

    def describe(self) -> str:
        return (f"{self.check_name} v{self.check_version} (snapshot {self.snapshot_date}) "
                f"pinned to the run of {self.run_date}")


def _date_key(value: object) -> tuple:
    """A sortable key from an ISO-8601 date or timestamp. Unparseable sorts lowest."""
    m = _DATE_RE.match(str(value or ""))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (0, 0, 0)


def snapshot_version_for_date(versions: list, run_date: str) -> Optional[dict]:
    """The check version current **at the run's date** (invariant L).

    `versions` is a list of `{"check_version", "snapshot_date", ...}`. The answer is the newest
    snapshot dated **on or before** the run — never simply the newest, which is the whole defect.

    Returns None when every known version post-dates the run. That is not an edge case to smooth
    over: it means the facts this run was judged against were never recorded, and the caller must
    say so rather than substitute the nearest one.
    """
    eligible = [v for v in (versions or [])
                if isinstance(v, dict) and _date_key(v.get("snapshot_date")) <= _date_key(run_date)
                and _date_key(v.get("snapshot_date")) != (0, 0, 0)]
    if not eligible:
        return None
    return max(eligible, key=lambda v: _date_key(v.get("snapshot_date")))


def pin_check_version(check_name: str, versions: list, run_date: str,
                      *, scored_with: Optional[str] = None) -> SnapshotPin:
    """Resolve the pin for re-scoring one run, or refuse (invariant L / FR-064).

    `scored_with` is the version the ORIGINAL run recorded, when the run says. It wins outright:
    what a run was actually scored with is evidence, and a date-based lookup is an inference. The
    lookup exists for runs made before this mechanism did.

    Raises `UnpinnableCheckError` rather than falling back to the newest version. The fallback is
    exactly the observed defect and it leaves no trace: the numbers come back and look fine.
    """
    by_version = {str(v.get("check_version")): v for v in (versions or [])
                  if isinstance(v, dict) and v.get("check_version") is not None}

    if scored_with is not None:
        entry = by_version.get(str(scored_with))
        if entry is None:
            raise UnpinnableCheckError(
                f"{check_name}: the original run was scored with version {scored_with!r}, which is "
                f"not among the known versions {sorted(by_version)}. Do NOT re-score against "
                f"another version — an original scored against v3 while every re-score of it "
                f"silently used v4, judging the call against facts that did not exist when it was "
                f"made. Recover the version, or report the run as un-rescorable.")
        return SnapshotPin(check_name, str(scored_with),
                           str(entry.get("snapshot_date") or "unknown"), str(run_date))

    entry = snapshot_version_for_date(list(by_version.values()), run_date)
    if entry is None:
        raise UnpinnableCheckError(
            f"{check_name}: no snapshot dated on or before the run of {run_date}. Every known "
            f"snapshot post-dates it, so the facts this run was judged against were never "
            f"recorded. Report it as un-rescorable rather than substituting the nearest snapshot.")
    return SnapshotPin(check_name, str(entry.get("check_version")),
                       str(entry.get("snapshot_date")), str(run_date))


def describe_variance(figure: object = None, *, basis: str = "") -> str:
    """The variance statement that accompanies every grounding figure (invariant O, N3).

    `basis` names how the figure was arrived at — a scoring pass, a mean of several, or a hand
    count. It is required: a grounding figure quoted without its basis is the failure this guards,
    because a single pass reads exactly like a measurement.
    """
    if not str(basis or "").strip():
        raise ValueError(
            "a grounding figure must be reported with its basis (invariant O / N3). State how it "
            "was arrived at — one scoring pass, a mean of several, or a hand count — because this "
            "check class varies between passes and a bare number reads as a measurement.")
    head = f"Grounding: {figure} ({basis})." if figure is not None else f"Grounding basis: {basis}."
    return f"{head} {GROUNDING_VARIANCE_NOTE}"

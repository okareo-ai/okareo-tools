"""
Judge calibration against operator hand labels (feature 022: contracts/pilot-trust-audit.md
invariants F, G, H, I).

**What calibration is.** The platform can re-evaluate a finished run against a *draft* check without
saving it, and report what each judge variable was populated with and what verdict came back. That
lets an operator ask "would this judge have agreed with me?" before committing a suite to it.

**Three things the prototype got wrong, and this module fixes.**

1. **It treated an UNLABELLED row as agreement** (INV-I). A partially labelled set therefore
   reported full agreement — a figure that reads as a calibrated judge and proves nothing. This is
   the defect that matters most, because the number looks best exactly when the evidence is
   weakest. Unlabelled rows are **excluded** and counted separately, and the exclusion is reported.
2. **It reported a single pass as the agreement figure** (INV-H). The judge varies between scoring
   passes — re-scores of one bank in the reference evidence returned 0.33, 0.60, 0.625 and 0.67
   against the same rows. A single pass is a sample, not a measurement, so this module reports a
   **range** and refuses to collapse it.
3. **It read as costless.** Calibration spends no *conversations*, which is why it is cheap, but
   every row it evaluates is a real judge call (INV-F). Only the platform's **inspect-only** mode
   is actually free, and that mode runs first (INV-G) because it is the decisive check that nested
   row structure reaches the judge at all.

Pure stdlib: part of the keyless tooling set. This module does no I/O to the platform — it compares
results the co-pilot fetched. Keeping the comparison offline is what lets it be tested.
"""
from __future__ import annotations

from typing import Optional

__all__ = [
    "CALIBRATION_COST_NOTE",
    "INSPECT_ONLY_NOTE",
    "agreement",
    "agreement_range",
    "normalize_verdict",
]

# The cost statements. Held as constants so the skill, the report and this module cannot drift into
# describing calibration differently — N1 bans the unqualified "free".
CALIBRATION_COST_NOTE = (
    "Calibration spends no conversations, but it is not free: every row it evaluates is a real "
    "judge call. Budget it per row, not per run.")
INSPECT_ONLY_NOTE = (
    "Inspect-only costs nothing and reports what each judge variable was actually populated with. "
    "Run it FIRST: it is the only check that the row's structured fields reach the judge at all, "
    "and a scoring pass spent against a judge that never saw the criterion is wasted.")


def normalize_verdict(value: object) -> Optional[int]:
    """Coerce a verdict to 1 / 0, or None when there is no verdict.

    None matters and is not an error. A check with no result **omits its key** — observed on 4 of 85
    rows in a real run — and a plain lookup returns None, which is falsy and therefore
    indistinguishable from a failure. Treating "absent" as 0 here would have recorded four
    unassessed conversations as four disagreements.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return 1 if value >= 0.5 else 0
    text = str(value).strip().lower()
    if text in ("1", "pass", "passed", "true", "held", "yes"):
        return 1
    if text in ("0", "fail", "failed", "false", "breached", "no"):
        return 0
    return None


def agreement(verdicts: dict, labels: dict) -> dict:
    """Agreement for ONE scoring pass, over labelled rows only (INV-I).

    `verdicts` and `labels` are keyed the same way — by data-point identity, never by position or
    rationale text (`overlay-registration.md` Q).

    Returns `{agreed, compared, rate, excluded_unlabelled, excluded_no_verdict, disagreements}`.
    Both exclusions are reported rather than folded into the denominator: an unlabelled row is the
    operator's omission and a verdictless row is the platform's, and the remedies differ.
    """
    labelled = {k: normalize_verdict(v) for k, v in (labels or {}).items()}
    labelled = {k: v for k, v in labelled.items() if v is not None}

    excluded_unlabelled = [k for k in (verdicts or {}) if k not in labelled]
    agreed, compared, no_verdict, disagreements = 0, 0, [], []
    for key, label in labelled.items():
        got = normalize_verdict((verdicts or {}).get(key))
        if got is None:
            # Not assessed. Excluded, NOT counted as a disagreement: the judge produced no verdict,
            # so there is nothing to disagree with, and counting it would blame the judge for a
            # missing result.
            no_verdict.append(key)
            continue
        compared += 1
        if got == label:
            agreed += 1
        else:
            disagreements.append({"key": key, "label": label, "judge": got})
    return {
        "agreed": agreed,
        "compared": compared,
        "rate": (agreed / compared) if compared else 0.0,
        "excluded_unlabelled": sorted(map(str, excluded_unlabelled)),
        "excluded_no_verdict": sorted(map(str, no_verdict)),
        "disagreements": disagreements,
    }


def agreement_range(passes: list[dict], labels: dict, *, check: str = "") -> dict:
    """Agreement across TWO OR MORE scoring passes, reported as a range (INV-H).

    Raises on a single pass. That is the point of the function: the judge varies between passes, so
    one pass is a sample. Reporting it as "the" agreement figure is how a judge comes to be trusted
    on evidence that does not support it — and the reference evidence has one bank returning 0.33
    and 0.67 on the same rows.

    Returns `{check, low, high, passes, spread, compared, excluded_unlabelled,
    excluded_no_verdict, summary}`. `summary` is the sentence to quote; it always states the range
    and the exclusions, never a midpoint — an average of two samples is not a better estimate, it
    just hides that they disagreed.
    """
    if not isinstance(passes, list) or len(passes) < 2:
        raise ValueError(
            f"calibration needs at least two scoring passes, got "
            f"{0 if not passes else len(passes)}. The judge varies between passes (observed: 0.33 "
            f"and 0.67 on the same bank), so a single pass is a sample and must never be reported "
            f"as the agreement figure. {CALIBRATION_COST_NOTE}")

    results = [agreement(p, labels) for p in passes]
    rates = [r["rate"] for r in results if r["compared"]]
    if not rates:
        raise ValueError(
            "calibration compared no rows: either nothing was labelled, or no pass produced a "
            "verdict for a labelled row. An agreement figure of 0% and 'no comparable rows' look "
            "the same in a report and mean opposite things, so this is an error, not a result.")

    low, high = min(rates), max(rates)
    compared = max(r["compared"] for r in results)
    unlabelled = results[0]["excluded_unlabelled"]
    no_verdict = sorted({k for r in results for k in r["excluded_no_verdict"]})
    span = f"{low:.0%}" if low == high else f"{low:.0%}–{high:.0%}"
    summary = (
        f"{check or 'judge'} agreed with the hand labels on {span} of "
        f"{compared} labelled row(s) across {len(passes)} scoring passes")
    if unlabelled:
        summary += f"; {len(unlabelled)} unlabelled row(s) excluded (not counted as agreement)"
    if no_verdict:
        summary += f"; {len(no_verdict)} labelled row(s) had no verdict and were excluded"
    return {
        "check": check,
        "low": low,
        "high": high,
        "passes": len(passes),
        "spread": high - low,
        "compared": compared,
        "excluded_unlabelled": unlabelled,
        "excluded_no_verdict": no_verdict,
        "disagreements": results[0]["disagreements"],
        "summary": summary + ".",
    }

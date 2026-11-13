"""
Compact run reader (feature 022: research D15; contracts/pilot-trust-audit.md invariant O).

A finished run's results are far too large to read whole — the full response for one pillar does not
fit in a terminal or a context window, and the useful part of each row is three facts: which probe,
what the judge said, and why. This module prints those.

**The defect it fixes.** The reference reader hardcoded a string split on the *facts-section label*
inside the criterion prose, to cut each row's criterion down to something printable. That made it a
direct dependency on a prose convention this feature replaces: reword the facts block and the reader
silently stops truncating, printing whole criteria and drowning the output it exists to condense.

Here the criterion is parsed against its **rendered structure** instead — the labels `reps.rows`
emits, which are constants precisely because the reuse machinery fingerprints them. If the clause
grammar ever changes, this module breaks loudly at the seam rather than degrading quietly.

**Derived from run data, never literals** (INV-O). Every figure printed comes out of the run
response. One reference builder worked this way; the other hand-typed thirty-six rows of outcomes,
which makes every quoted piece of evidence in that report a transcription rather than a reading.

Pure stdlib: part of the keyless tooling set.
"""
from __future__ import annotations

from typing import Optional

__all__ = [
    "criterion_clauses",
    "compact_row",
    "compact",
]

# How much of a clause to show before truncating. Rows, not bytes: a byte threshold on a response is
# banned (`overlay-registration.md` N5 / `pilot-trust-audit.md` N4) because the real limit is
# token-based and a constant invites treating a spill path as a platform behaviour. This is a
# display width for one clause, which is a different thing and is the caller's to set.
DEFAULT_CLAUSE_WIDTH = 120


def criterion_clauses(rendered_result: object) -> dict:
    """Split a RENDERED criterion into its parts, structurally.

    Returns `{must, must_not, trailing}`. `trailing` holds whatever followed the clauses — the
    optional note, the facts block and the evidence rule — which is exactly the material a compact
    view drops, because none of it is the criterion the verdict turned on.

    A string that is not in the rendered shape comes back whole as `must`, with empty siblings. That
    is deliberate: a pre-022 row, or an overlay someone hand-edited, must still print.
    """
    from reps.profile import FACTS_BLOCK_PREFIX
    from reps.rows import MUST_LABEL, MUST_NOT_LABEL

    text = str(rendered_result or "").strip()
    if not text:
        return {"must": "", "must_not": "", "trailing": ""}

    must, must_not = "", ""
    body = text
    if body.startswith(MUST_LABEL):
        body = body[len(MUST_LABEL):]
    elif body.startswith(MUST_NOT_LABEL.lstrip()):
        body = body[len(MUST_NOT_LABEL.lstrip()):]
        must_not, body = body, ""

    if body and MUST_NOT_LABEL in body:
        must, rest = body.split(MUST_NOT_LABEL, 1)
        must_not = rest
    elif body:
        must = body

    # The trailing material always begins at the first structural marker that follows the clauses.
    trailing = ""
    target = must_not or must
    for marker in (FACTS_BLOCK_PREFIX, "Evidence rule:"):
        if marker in target:
            target, tail = target.split(marker, 1)
            trailing = (marker + tail + " " + trailing).strip()
    if must_not:
        must_not = target
    else:
        must = target
    return {"must": must.strip(), "must_not": must_not.strip(), "trailing": trailing.strip()}


def compact_row(data_point: dict, *, check: str,
                clause_width: int = DEFAULT_CLAUSE_WIDTH) -> str:
    """One readable line for one data point, derived entirely from the run response.

    `check` names which verdict to read, because a row is scored by more than one check and reading
    "the" verdict off a multi-check row is how a pillar comes to report another pillar's result.
    """
    from reps.report.capture import CheckNotAssessed, read_check_verdict

    inp = data_point.get("scenario_input") or {}
    sub = str(inp.get("sub_capability") or inp.get("persona") or "?")
    clauses = criterion_clauses(data_point.get("scenario_result"))
    clause = clauses["must"] or clauses["must_not"] or "—"
    if len(clause) > clause_width:
        clause = clause[: clause_width - 1].rstrip() + "…"

    checks = data_point.get("check_results") or data_point.get("checks")
    rationale = ""
    try:
        # One call, because `read_check_verdict` owns BOTH read-back rules: key presence (never
        # truthiness) and delimiter stripping. Re-deriving either here would be a second
        # implementation of a rule that exists because the first obvious one was wrong.
        passed, rationale = read_check_verdict(checks, check)
        mark = "PASS" if passed else "FAIL"
        rationale = rationale or ""
    except CheckNotAssessed:
        # NOT the same as a failure, and the distinction is the point of the exception. A plain
        # lookup returns None here, which is falsy — on one real run 4 of 85 rows had no result for
        # a check, and the naive read would have recorded four unassessed calls as four failures.
        mark = "NOT ASSESSED"

    if len(rationale) > clause_width:
        rationale = rationale[: clause_width - 1].rstrip() + "…"

    line = f"{mark:<12} {sub:<28} {clause}"
    return line + (f"\n{'':<12} ↳ {rationale}" if rationale else "")


def compact(data_points: list[dict], *, check: str,
            clause_width: int = DEFAULT_CLAUSE_WIDTH,
            only: Optional[str] = None) -> str:
    """Compact view of a run, plus a tally.

    `only` filters to `"fail"` or `"not-assessed"`, which is what an operator reading a pilot
    actually wants: the passes are not what a hand review is for.
    """
    lines, tally = [], {"PASS": 0, "FAIL": 0, "NOT ASSESSED": 0}
    for dp in data_points or []:
        rendered = compact_row(dp, check=check, clause_width=clause_width)
        mark = rendered.split(" ", 1)[0] if not rendered.startswith("NOT") else "NOT ASSESSED"
        tally[mark] = tally.get(mark, 0) + 1
        if only == "fail" and mark != "FAIL":
            continue
        if only == "not-assessed" and mark != "NOT ASSESSED":
            continue
        lines.append(rendered)
    total = sum(tally.values())
    lines += ["", f"{total} row(s): {tally['PASS']} pass, {tally['FAIL']} fail, "
                  f"{tally['NOT ASSESSED']} not assessed."]
    if tally["NOT ASSESSED"]:
        lines.append("A not-assessed row produced no verdict. It is NOT a failure, and it is not "
                     "counted either way — read its transcript before treating it as anything.")
    return "\n".join(lines)

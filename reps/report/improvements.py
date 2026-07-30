"""
Improvements record I/O — the transcript-derived "Suggested Agent Improvements" section.

The record is authored by the reps-run co-pilot after reading the transcripts of failing
conversations, persisted to results/<agent_slug>/findings/improvements_<stamp>.json (latest-wins,
like pillar findings records), and rendered by gen_reps_report.py as report section 07. The
renderer reads ONLY this record for that section, keeping the report regenerable from captured
state (Constitution VIII). Pure stdlib — no okareo import, no key.

Schema & validation are defined in this module and enforced by tests/test_report.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1
FILENAME_PREFIX = "improvements_"
AUTHOR = "co-pilot"
DISPOSITIONS = {"full", "partial"}

# Required top-level keys (headline is required but nullable; lists may be empty).
_REQUIRED_KEYS = (
    "schema_version", "target_name", "generated_at", "author", "based_on", "review_coverage",
    "headline", "suggestions", "held_up", "discounted", "coverage_gap_notes", "analysis_doc",
)
_REF_KEYS = ("pillar", "scenario", "test_run_id")


def _err(msg: str) -> None:
    raise ValueError(f"improvements record: {msg}")


def _require_str(container: dict, key: str, where: str) -> str:
    val = container.get(key)
    if not isinstance(val, str) or not val.strip():
        _err(f"{where}: '{key}' must be a non-empty string")
    return val


def _check_ref(ref: Any, where: str, *, reason_required: bool = False) -> None:
    if not isinstance(ref, dict):
        _err(f"{where}: must be an object")
    for key in _REF_KEYS:
        _require_str(ref, key, where)
    if reason_required:
        _require_str(ref, "reason", where)


def _check_evidence_item(item: Any, where: str, *, headline_present: bool,
                         allow_headline_ref: bool) -> None:
    if not isinstance(item, dict):
        _err(f"{where}: evidence items must be objects")
    if item.get("headline") is True:
        if not allow_headline_ref:
            _err(f"{where}: headline evidence reference is not allowed here")
        if not headline_present:
            _err(f'{where}: {{"headline": true}} evidence requires a non-null headline')
        return
    _require_str(item, "test_run_id", where)
    _require_str(item, "scenario", where)
    _require_str(item, "observation", where)


def validate_improvements(record: Any, *, agent_dir: Optional[Path] = None) -> list[str]:
    """Validate a record against the schema-v1 contract.

    Raises ValueError (with a field-precise message) on any hard error; returns a list of
    warnings for soft issues. `agent_dir` (results/<agent_slug>/) enables the write-time
    `analysis_doc`-exists check; read-time callers omit it (existence is a write-time guarantee).
    """
    if not isinstance(record, dict):
        _err("must be a JSON object")
    for key in _REQUIRED_KEYS:
        if key not in record:
            _err(f"missing required key '{key}'")

    if record["schema_version"] != SCHEMA_VERSION:
        _err(f"schema_version must be {SCHEMA_VERSION}, got {record['schema_version']!r}")
    if record["author"] != AUTHOR:
        _err(f"author must be '{AUTHOR}', got {record['author']!r}")
    _require_str(record, "target_name", "record")
    _require_str(record, "generated_at", "record")

    based_on = record["based_on"]
    if not isinstance(based_on, dict) or not based_on:
        _err("'based_on' must be a non-empty object (pillar -> run reference)")
    for pillar, ref in based_on.items():
        if not isinstance(ref, dict):
            _err(f"based_on['{pillar}']: must be an object")
        _require_str(ref, "run_timestamp", f"based_on['{pillar}']")
        _require_str(ref, "findings_file", f"based_on['{pillar}']")

    cov = record["review_coverage"]
    if not isinstance(cov, dict):
        _err("'review_coverage' must be an object")
    total = cov.get("failing_total")
    reviewed = cov.get("reviewed")
    unreviewed = cov.get("unreviewed")
    if not isinstance(total, int) or total < 0:
        _err("review_coverage.failing_total must be a non-negative integer")
    if not isinstance(reviewed, list) or not isinstance(unreviewed, list):
        _err("review_coverage.reviewed and .unreviewed must be lists")
    if len(reviewed) + len(unreviewed) != total:
        _err(f"review_coverage invariant violated: reviewed ({len(reviewed)}) + unreviewed "
             f"({len(unreviewed)}) != failing_total ({total}) — no silent omissions")
    for i, ref in enumerate(reviewed):
        _check_ref(ref, f"review_coverage.reviewed[{i}]")
    for i, ref in enumerate(unreviewed):
        _check_ref(ref, f"review_coverage.unreviewed[{i}]", reason_required=True)

    headline = record["headline"]
    if headline is not None:
        if not isinstance(headline, dict):
            _err("'headline' must be null or an object")
        _require_str(headline, "title", "headline")
        _require_str(headline, "body", "headline")
        h_ev = headline.get("evidence")
        if not isinstance(h_ev, list) or not h_ev:
            _err("headline.evidence must be a non-empty list")
        for i, item in enumerate(h_ev):
            _check_evidence_item(item, f"headline.evidence[{i}]",
                                 headline_present=True, allow_headline_ref=False)

    suggestions = record["suggestions"]
    if not isinstance(suggestions, list):
        _err("'suggestions' must be a list")
    priorities = []
    for i, sug in enumerate(suggestions):
        where = f"suggestions[{i}]"
        if not isinstance(sug, dict):
            _err(f"{where}: must be an object")
        pri = sug.get("priority")
        if not isinstance(pri, int) or pri < 1:
            _err(f"{where}: 'priority' must be an integer >= 1")
        priorities.append(pri)
        for key in ("title", "change", "basis"):
            _require_str(sug, key, where)
        evidence = sug.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            _err(f"{where}: 'evidence' must be a non-empty list (FR-003)")
        for j, item in enumerate(evidence):
            _check_evidence_item(item, f"{where}.evidence[{j}]",
                                 headline_present=headline is not None, allow_headline_ref=True)
        hint = sug.get("severity_hint")
        if hint is not None and hint not in ("Critical", "High", "Medium"):
            _err(f"{where}: 'severity_hint' must be Critical/High/Medium or null")
    if sorted(priorities) != list(range(1, len(priorities) + 1)):
        _err(f"suggestion priorities must be unique and contiguous from 1, got {sorted(priorities)}")

    for name in ("held_up", "coverage_gap_notes"):
        items = record[name]
        if not isinstance(items, list) or any(not isinstance(x, str) or not x.strip() for x in items):
            _err(f"'{name}' must be a list of non-empty strings")

    discounted = record["discounted"]
    if not isinstance(discounted, list):
        _err("'discounted' must be a list")
    for i, disc in enumerate(discounted):
        where = f"discounted[{i}]"
        _check_ref(disc, where, reason_required=True)
        if disc.get("disposition") not in DISPOSITIONS:
            _err(f"{where}: 'disposition' must be one of {sorted(DISPOSITIONS)}")

    doc = _require_str(record, "analysis_doc", "record")
    doc_path = Path(doc)
    if doc_path.is_absolute() or ".." in doc_path.parts:
        _err("'analysis_doc' must be a relative path with no '..' segments")
    if agent_dir is not None and not (Path(agent_dir) / doc_path).is_file():
        _err(f"'analysis_doc' does not exist: {Path(agent_dir) / doc_path}")

    warnings: list[str] = []
    if discounted and not (record.get("effective_picture") or "").strip():
        warnings.append("discounted verdicts present but no 'effective_picture' reconciliation "
                        "(SC-005) — consider adding one")
    return warnings


def load_latest_improvements(results_dir: str | Path) -> tuple[Optional[dict], list[str]]:
    """Load the latest improvements record from a findings dir (lexicographic latest-wins).

    Tolerant by contract: a malformed or invalid record yields (None, [warning]) — the report
    must always render, showing the absent-state note plus the warning. Never raises.
    """
    results_dir = Path(results_dir)
    candidates = sorted(results_dir.glob(f"{FILENAME_PREFIX}*.json")) if results_dir.is_dir() else []
    if not candidates:
        return None, []
    path = candidates[-1]
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return None, [f"improvements record {path.name} is invalid: {e}"]
    try:
        warnings = validate_improvements(record)  # no agent_dir: existence is write-time-only
    except ValueError as e:
        return None, [f"improvements record {path.name} is invalid: {e}"]
    return record, warnings


def compute_staleness(record: dict, findings_records: list[dict]) -> list[str]:
    """Compare a record's `based_on` against the loaded (latest-per-pillar) findings records.

    Returns human-readable stale reasons; empty ⇒ the review is current. A pillar present in
    findings but missing from `based_on` is stale (the review never saw that run); a reviewed
    pillar no longer present in findings is stale too (the run set changed under the review).
    """
    based_on = record.get("based_on") or {}
    reasons: list[str] = []
    seen_pillars = set()
    for rec in findings_records:
        pillar = rec.get("pillar")
        if not pillar:
            continue
        seen_pillars.add(pillar)
        current_ts = rec.get("run_timestamp", "")
        ref = based_on.get(pillar)
        if ref is None:
            reasons.append(f"{pillar} run {current_ts or '(unknown timestamp)'} was never reviewed")
        elif ref.get("run_timestamp") != current_ts:
            reasons.append(f"{pillar} has a newer run ({current_ts or 'unknown'}) than the one "
                           f"reviewed ({ref.get('run_timestamp', 'unknown')})")
    for pillar in based_on:
        if pillar not in seen_pillars:
            reasons.append(f"reviewed {pillar} run is no longer among the captured findings")
    return reasons

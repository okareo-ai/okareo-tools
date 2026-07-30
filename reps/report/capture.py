"""
Capture normalized REPS findings to results/<agent_slug>/findings/<pillar>_<date-time>.json.

The report generator reads ONLY these files (never the live platform), so the report is
reproducible from committed state (Constitution VIII).

Record schema: defined and validated by write_record() below.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from reps.trace import (
    EVIDENCE_CONVERSATION_INFERRED,
    TRACE_DECLARED_ABSENT,
    TRACE_UNAVAILABLE,
    compute_trace_status,
    evidence_basis,
    usable_trace,
)


def read_profile_version(profile_path: Path) -> tuple[Optional[str], Optional[str]]:
    """Best-effort read of `version` and `updated_at` from agent-profile.yaml (line-based)."""
    if not profile_path.exists():
        return None, None
    version = updated_at = None
    for line in profile_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*version:\s*(.+)", line)
        if m and version is None:
            version = m.group(1).strip().strip('"')
        m = re.match(r"\s*updated_at:\s*(.+)", line)
        if m and updated_at is None:
            updated_at = m.group(1).strip().strip('"')
    return version, updated_at


def read_profile_trace_path(profile_path: Path) -> Optional[str]:
    """Best-effort read of `trace.path` from agent-profile.yaml (feature 004, line-based).

    Returns the declared response path of the tool-call trace, or None (black-box). Secret-free —
    this is a field/path name, never a credential.
    """
    p = Path(profile_path)
    if not p.exists():
        return None
    in_trace = False
    for line in p.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\S", line):  # a top-level key ends any nested block
            in_trace = bool(re.match(r"^trace:\s*$", line))
            continue
        if in_trace:
            m = re.match(r"\s+path:\s*(.+)", line)
            if m:
                val = m.group(1).strip().strip('"').strip("'")
                return val or None
    return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def annotate_trace(*, pillar: str, simulations: list[dict], declared: bool,
                   trace_check_names: Optional[list[str]] = None,
                   voice: bool = False) -> tuple[Optional[str], Optional[str]]:
    """Assign `evidence_basis` to Execution datapoints and compute (trace_status, discrepancy).

    Feature 004 (contracts/trace-model.md, findings-and-report.md). A datapoint has a usable trace
    when its `trace` field is a non-empty structure. `relevant` = trace-requiring Execution
    datapoints (those whose `check` is in `trace_check_names`, or — absent that hint — any Execution
    datapoint carrying a `trace`). Voice returns `unavailable` and adds no evidence labels.
    """
    if voice:
        return None, None  # voice: no trace fields written (records stay byte-identical to pre-004)
    is_exec = (pillar == "Execution")
    names = set(trace_check_names or [])
    relevant = observed = 0
    for sim in simulations:
        for dp in sim.get("datapoints", []) or []:
            if not isinstance(dp, dict) or not is_exec:
                continue
            trace_eligible = (dp.get("check") in names) if names else bool(dp.get("trace"))
            if declared and trace_eligible:
                has = usable_trace(dp)
                relevant += 1
                observed += 1 if has else 0
                dp["evidence_basis"] = evidence_basis(has)
            else:
                dp["evidence_basis"] = EVIDENCE_CONVERSATION_INFERRED
    status = compute_trace_status(declared, observed, relevant)
    discrepancy = None
    if status == TRACE_DECLARED_ABSENT:
        discrepancy = ("trace declared for this target but not returned/usable at runtime — "
                       "Execution assessed as black-box (conversation-inferred).")
    return status, discrepancy


def build_trace_gaps(trace_excluded_checks: Optional[list[str]], declared: bool) -> list[dict]:
    """One `no-trace` coverage gap per trace-based check excluded for lack of a usable trace.

    Never a pass or a failure — a trace-dependent sub-capability that could not be assessed
    (findings-and-report.md §Capture, Constitution VIII).
    """
    if not trace_excluded_checks:
        return []
    reason = ("trace declared but absent at runtime — assessed as black-box; fix the target's "
              "trace.path or endpoint" if declared else
              "not assessed — target exposes no tool-call trace; declare trace.path to enable "
              "trace-verified checks")
    return [{"check": c, "reason": reason, "gap_kind": "no-trace"}
            for c in trace_excluded_checks]


# Default finding severity for a failing probe whose row carries no `severity_on_fail`
# (contracts/scenario-row.md). Kept local: this module must stay okareo/common-free.
DEFAULT_FAIL_SEVERITY = {"Reasoning": "High", "Execution": "High",
                         "Performance": "Medium", "Security": "High"}


def expand_coverage_gaps(scenario: str, expected_rows: list[dict],
                         datapoints: list[dict], reason: str) -> list[dict]:
    """One coverage-gap entry per row that produced no datapoint (FR-006, findings v2).

    `expected_rows` are the row `input` dicts of the bank slice this simulation ran.
    Rows are matched to datapoints by sub_capability label counts (rows may share a
    label); each missing occurrence becomes its own gap entry — a merged run may never
    surface fewer gap lines than sub-capabilities lost.
    """
    seen: dict[str, int] = {}
    for dp in datapoints or []:
        label = dp.get("sub_capability")
        if label:
            seen[label] = seen.get(label, 0) + 1
    gaps: list[dict] = []
    for row in expected_rows or []:
        label = row.get("sub_capability") or "unlabeled"
        if seen.get(label, 0) > 0:
            seen[label] -= 1
            continue
        gaps.append({"scenario": scenario, "sub_capability": label, "reason": reason})
    return gaps


def fs_stamp(iso_ts: str) -> str:
    """ISO timestamp -> filesystem-safe date-time stamp, e.g. 2026-07-08T14:23:05Z -> 2026-07-08_142305."""
    s = iso_ts.replace("Z", "")
    if "T" in s:
        date, _, tm = s.partition("T")
        return f"{date}_{tm.replace(':', '')}"
    return s.replace(":", "")


def _sim_record(scenario: str, res: dict, plan_entry: dict, pillar: str = "") -> dict:
    """Normalize one simulation result into a serializable record.

    Findings v2 (contracts/findings-record-v2.md): when the runner attached the bank's
    row inputs as `res["expected_rows"]`, failing datapoints default their severity from
    the row's `severity_on_fail` (else the pillar default), and any row that produced no
    datapoint becomes its own coverage-gap entry (FR-006). v1 behavior is unchanged when
    `expected_rows` is absent.
    """
    test_run = res.get("test_run")
    expected_rows: list[dict] = res.get("expected_rows") or []
    datapoints = res.get("datapoints", [])

    if expected_rows:
        sev_by_label = {r.get("sub_capability"): r.get("severity_on_fail")
                        for r in expected_rows if r.get("severity_on_fail")}
        default_sev = DEFAULT_FAIL_SEVERITY.get(pillar, "Medium")
        for dp in datapoints:
            if isinstance(dp, dict) and not dp.get("passed") and not dp.get("safe_refusal") \
                    and not dp.get("finding_severity"):
                dp["finding_severity"] = sev_by_label.get(dp.get("sub_capability"), default_sev)

    rec = {
        "scenario": scenario,
        # v2 consolidated entries omit plan-level sub_capability (it lives on datapoints);
        # legacy/single-probe entries keep their plan label (fallback chain in scoring).
        "sub_capability": plan_entry.get("sub_capability")
                          if expected_rows else plan_entry.get("sub_capability", scenario),
        "evaluation_mode": "multi-turn" if res.get("max_turns", 1) > 1 else "single-turn",
        "driver": res.get("driver"),
        "checks": res.get("checks", []),
        "test_run_id": getattr(test_run, "id", None) if test_run else None,
        "app_link": getattr(test_run, "app_link", None) if test_run else None,
        "elapsed_s": round(res.get("elapsed", 0.0), 1),
        "status": res.get("status", "complete"),
        "datapoints": datapoints,
    }
    if res.get("status") == "error":
        rec["error"] = res.get("error", "unknown error")
        if expected_rows:
            rec["coverage_gaps"] = expand_coverage_gaps(
                scenario, expected_rows, [],
                f"simulation errored before this probe produced a result — re-run pillar: "
                f"{res.get('error', 'unknown error')}")
    elif expected_rows:
        gaps = expand_coverage_gaps(
            scenario, expected_rows, datapoints,
            "simulation completed but this probe produced no result — re-run pillar")
        if gaps:
            rec["coverage_gaps"] = gaps
    return rec


def write_record(
    *,
    pillar: str,
    modality: str,
    target_name: str,
    simulations: list[dict],
    results_dir: Path,
    profile_path: Optional[Path] = None,
    run_timestamp: Optional[str] = None,
    reuse: Optional[dict] = None,
    aggregate_summary: Optional[str] = None,
    trace_status: Optional[str] = None,
    trace_discrepancy: Optional[str] = None,
    trace_gaps: Optional[list[dict]] = None,
) -> Path:
    """Write a normalized results record from an already-shaped `simulations` list.

    This is the shared, key-free writer used by BOTH execution paths:
    - the SDK runner (`capture_results`, below), and
    - the Claude/MCP path, which assembles `simulations` from `get_test_run_results` and calls this
      directly — no local OKAREO_API_KEY required (the MCP server holds the auth).

    `simulations` entries follow contracts/report-results.md (scenario, sub_capability,
    evaluation_mode, driver, checks, test_run_id, app_link, elapsed_s, status, datapoints).
    """
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = run_timestamp or _iso_now()

    # Feature 008 (US1, defense-in-depth): stamp `modality_applicable: false` on any datapoint whose
    # probe class is not applicable to this run's modality — e.g. a voice-only probe that still
    # surfaced on a text run via the MCP path (which the SDK row-gate would have excluded upstream).
    # Scoring then excludes it (never a fail, never a pass — INV-2), matching the not-applicable
    # rendering the coverage manifest drives.
    from reps.coverage import class_modality, load_manifest_for_pillar, modality_applies
    _manifest = load_manifest_for_pillar(pillar)
    if _manifest and modality:
        for sim in simulations or []:
            for dp in sim.get("datapoints", []) or []:
                if not isinstance(dp, dict) or dp.get("modality_applicable") is False:
                    continue
                sub = dp.get("sub_capability") or sim.get("sub_capability")
                if sub and not modality_applies(class_modality(_manifest, sub), modality):
                    dp["modality_applicable"] = False
                    dp.setdefault("modality_na_reason",
                                  f"{sub} is not applicable to a {modality} run")

    if profile_path is None:
        # Feature 006: resolve this agent's profile first (results/<slug>/profile/…), falling back
        # to the committed baseline profile, then to None. `None` ⇒ the pillar reads **untuned**
        # (FR-008/FR-010) — the same signal an unprofiled agent has always produced.
        from reps.paths import resolve_profile
        profile_path = resolve_profile(target_name)
    profile_version, profile_updated = (
        read_profile_version(Path(profile_path)) if profile_path else (None, None))

    record: dict[str, Any] = {
        "pillar": pillar,
        "run_timestamp": ts,
        "profile_version": profile_version,
        "profile_updated_at": profile_updated,
        "untuned": profile_version is None,
        "modality": modality,
        "target_name": target_name,
        "simulations": simulations,
    }
    # Building-block reuse/upload disposition (feature 003, FR-012). Optional so pre-003
    # records and the MCP path (which may not supply it) remain valid.
    if reuse is not None:
        record["reuse"] = reuse
    # Co-pilot-authored aggregate summary (feature 005, FR-005). Written only by the MCP
    # path; empty/whitespace is treated as absent → the report shows its static paragraph.
    if aggregate_summary and aggregate_summary.strip():
        record["aggregate_summary"] = aggregate_summary.strip()
    # Trace availability (feature 004, findings v3). Written only for text runs — voice records
    # stay byte-identical to pre-004 (SC-007). Back-compat reader defaults handle their absence.
    if trace_status is not None:
        record["trace_status"] = trace_status
    if trace_discrepancy is not None:
        record["trace_discrepancy"] = trace_discrepancy
    if trace_gaps:
        record["trace_gaps"] = trace_gaps

    out = results_dir / f"{pillar.lower()}_{fs_stamp(ts)}.json"
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return out


def write_improvements(*, record: dict, results_dir: Path) -> Path:
    """Write the transcript-derived improvements record (feature 013, schema v1).

    Sole writer for results/<agent_slug>/findings/improvements_<stamp>.json — the source the
    report's "Suggested Agent Improvements" section renders from. Key-free and callable via
    `python -c` from the MCP co-pilot path, exactly like `write_record`. Validates the record
    (schema in reps/report/improvements.py) including that the
    companion `analysis_doc` already exists under the agent's results tree; raises ValueError
    on any violation. Never touches pillar findings records.
    """
    from reps.report.improvements import FILENAME_PREFIX, validate_improvements

    results_dir = Path(results_dir)
    if results_dir.name != "findings":
        raise ValueError(f"improvements record: results_dir must be a findings/ directory, "
                         f"got {results_dir}")
    warnings = validate_improvements(record, agent_dir=results_dir.parent)
    for w in warnings:
        print(f"warning: {w}")
    out = results_dir / f"{FILENAME_PREFIX}{fs_stamp(record['generated_at'])}.json"
    if out.parent.resolve() != results_dir.resolve():
        raise ValueError("improvements record: output path escapes the findings directory")
    results_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return out


def capture_results(
    *,
    pillar: str,
    modality: str,
    target_name: str,
    plan: list[dict],
    results: dict[str, dict],
    results_dir: Path,
    profile_path: Optional[Path] = None,
    run_timestamp: Optional[str] = None,
    reuse: Optional[dict] = None,
    aggregate_summary: Optional[str] = None,
    trace_declared: bool = False,
    trace_check_names: Optional[list[str]] = None,
    trace_excluded_checks: Optional[list[str]] = None,
) -> Path:
    """SDK-runner capture: normalize `run_evaluation` results, then write via `write_record`.

    Feature 004: for a text run, annotate Execution datapoints with `evidence_basis`, compute the
    run-level `trace_status` (+ discrepancy on declared-absent), and emit `no-trace` coverage gaps
    for trace-based checks the gate excluded. Voice runs are untouched (byte-identical records).
    """
    plan_by_scenario = {p["scenario"]: p for p in plan}
    simulations = [
        _sim_record(name, res, plan_by_scenario.get(name, {}), pillar=pillar)
        for name, res in results.items()
    ]
    voice = str(modality).strip().lower() == "voice"
    trace_status, trace_discrepancy = annotate_trace(
        pillar=pillar, simulations=simulations, declared=trace_declared,
        trace_check_names=trace_check_names, voice=voice)
    trace_gaps = None if voice else build_trace_gaps(trace_excluded_checks, trace_declared)
    return write_record(
        pillar=pillar, modality=modality, target_name=target_name, simulations=simulations,
        results_dir=results_dir, profile_path=profile_path, run_timestamp=run_timestamp,
        reuse=reuse, aggregate_summary=aggregate_summary, trace_status=trace_status,
        trace_discrepancy=trace_discrepancy, trace_gaps=trace_gaps,
    )

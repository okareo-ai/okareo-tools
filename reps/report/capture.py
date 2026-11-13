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


# --- Run-level latency block (feature 019, contracts/performance-signal.md, data-model §1) -------
# Captured from the run's agent-side baseline metrics. Absence is meaningful and must survive:
# absent ⇒ the latency signal is absent ⇒ not-assessed with an observed reason.
# ---------------------------------------------------------------------------------------------
# Feature 022 — reading a verdict back off a finished run (contracts/judge-templates.md S, T, U).
#
# Three observed platform behaviours make the obvious implementation silently wrong, and all three
# produce a WRONG VERDICT rather than an error — the same shape as the defect feature 019 fixed.
# ---------------------------------------------------------------------------------------------

#: The platform's score and explanation delimiters. A stored rationale keeps the judge's whole raw
#: response, delimiters included, while the score is extracted ADDITIONALLY — observed in 152 of
#: 850 real results. Quoting one unstripped puts parser syntax in front of a stakeholder.
_DELIMITER_RESIDUE = re.compile(r"\[\[\s*[01]?\s*\]\]|\(\(|\)\)")

#: A leading verdict digit, which the field-proven judges emit before their checklist.
_LEADING_VERDICT = re.compile(r"^\s*[01]\s+")


class CheckNotAssessed(Exception):
    """A check produced no result for this conversation. NOT the same as a failing verdict."""


def read_check_verdict(checks: Optional[dict], check_name: str):
    """Return ``(passed, rationale)`` for one check on one data point.

    **Test key presence, never truthiness** (INV-S). A check that failed to produce a result for a
    conversation **omits its key entirely** — it does not return null or false. Observed: one judge
    had results on 81 of 85 rows, and on the other 4 its key was simply absent. A plain
    ``checks.get(name)`` returns ``None``, which is falsy and therefore indistinguishable from a
    recorded failure, so the obvious implementation silently records 4 passes as failures.

    Raises :class:`CheckNotAssessed` when the key is absent, so a caller must decide explicitly
    rather than inherit a default. The rationale is returned already stripped of delimiter residue.
    """
    if not isinstance(checks, dict) or check_name not in checks:
        raise CheckNotAssessed(
            f"check {check_name!r} produced no result for this conversation — its key is absent "
            f"from the data point. This is NOT a failing verdict: record it as not-assessed with "
            f"the observed reason, never as a pass and never as a fail.")
    raw = checks[check_name]
    passed = bool(raw) if not isinstance(raw, str) else raw.strip().lower() in ("true", "1", "pass")
    return passed, strip_delimiter_residue(checks.get(f"{check_name}__explanation"))


def strip_delimiter_residue(rationale: Optional[str]) -> Optional[str]:
    """Remove the platform's raw score/explanation delimiters from a stored rationale (INV-T)."""
    if not isinstance(rationale, str):
        return rationale
    out = _LEADING_VERDICT.sub("", rationale.strip())
    out = _DELIMITER_RESIDUE.sub("", out)
    return " ".join(out.split()).strip() or None


def datapoint_key(data_point: dict) -> tuple:
    """A join key that stays correct when a row is run more than once (INV-U).

    Each data point already carries its own caller-facing material and criterion, so **no join to
    the scenario bank is needed at all** — identity is read straight off the data point. Position in
    the returned list must never be used: it is meaningless across pages, and with repeats above one
    there are several conversations per row, so the row index is not unique either.
    """
    inp = data_point.get("scenario_input")
    sub = inp.get("sub_capability") if isinstance(inp, dict) else None
    return (data_point.get("test_id"), data_point.get("scenario_index"), sub)


LATENCY_NUMERIC_KEYS = ("avg_turn_taking_latency_ms", "avg_turn_latency_ms")
LATENCY_ALLOWED_KEYS = frozenset(LATENCY_NUMERIC_KEYS + ("source",))
# Invariant E: the judge model's latency sits adjacent to the agent's in the same response and lands
# in a plausible millisecond range, making it the single most likely mis-wiring. Name it so a wrong
# capture fails loudly here instead of silently producing confident, false latency findings.
LATENCY_FORBIDDEN_SOURCE = "aggregate_check_metadata"


def validate_latency_block(block: object, *, scenario: str | None = None) -> None:
    """Raise ValueError unless `block` is a well-formed run-level latency block."""
    where = f" (simulation {scenario!r})" if scenario else ""
    if not isinstance(block, dict):
        raise ValueError(f"latency block must be an object, got {type(block).__name__}{where}")
    unknown = sorted(set(block) - LATENCY_ALLOWED_KEYS)
    if unknown:
        raise ValueError(f"latency block has unknown key(s) {unknown}{where}; allowed: "
                         f"{sorted(LATENCY_ALLOWED_KEYS)}")
    for key in LATENCY_NUMERIC_KEYS:
        if key not in block:
            continue
        value = block[key]
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"latency block {key} must be a positive number or null, "
                             f"got {value!r}{where}")
    if not any(isinstance(block.get(k), (int, float)) and not isinstance(block.get(k), bool)
               for k in LATENCY_NUMERIC_KEYS):
        raise ValueError(f"latency block carries no numeric figure{where}; omit the block entirely "
                         f"when the run returned no latency — absence is the honest signal")
    source = block.get("source")
    if source is not None and not isinstance(source, str):
        raise ValueError(f"latency block source must be a string{where}")
    if isinstance(source, str) and LATENCY_FORBIDDEN_SOURCE in source:
        raise ValueError(
            f"latency block source {source!r} is the judge model's latency, not the agent's"
            f"{where} — capture model_metrics.aggregate_baseline_metrics instead "
            f"(contracts/performance-signal.md invariant E)")


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

    # Feature 019: validate any captured run-level latency block BEFORE writing. A malformed block
    # must raise, never be silently dropped — a dropped block becomes an unexplained not-assessed,
    # which is exactly the failure class this feature removes (data-model §1).
    for sim in simulations or []:
        if isinstance(sim, dict) and "latency" in sim:
            validate_latency_block(sim.get("latency"), scenario=sim.get("scenario"))

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


# =================================================================================================
# Feature 022 — the pilot review record (contracts/pilot-trust-audit.md invariants A2, C, D)
# =================================================================================================

PILOT_FILENAME_PREFIX = "pilot_review_"

# The five column headers, verbatim from the reference format (research D16). Fixed, because the
# four questions FR-047 requires map onto them one-to-one and a renamed column loses a question.
PILOT_COLUMNS = ("Call", "Probe", "Judge", "Hand review", "Harness issue")


def validate_pilot_review(record: object) -> list[str]:
    """Validate a pilot review record. Returns non-fatal warnings; raises on a violation.

    Raising rather than warning on a missing `hand_sense` is deliberate: the sense is what the gate
    reads, and a record whose senses are only in the prose produces a gate figure of zero on a
    pilot that found four faults.
    """
    from reps.report.scoring import (HAND_SENSES, HARNESS_FAULT_GATE_DEFAULT,
                                     NOT_EXERCISED_CAUSES)

    if not isinstance(record, dict):
        raise ValueError("pilot review: record must be an object")
    warnings: list[str] = []
    for key in ("pillar", "generated_at"):
        if not str(record.get(key) or "").strip():
            raise ValueError(f"pilot review: missing required field {key!r}")

    calls = record.get("calls")
    if not isinstance(calls, list) or not calls:
        raise ValueError(
            "pilot review: 'calls' must be a non-empty list — a pilot with no reviewed calls "
            "cannot produce a gate figure, and an absent gate reads as a passing one")
    if len(calls) > 3 * 12:
        warnings.append(f"pilot review: {len(calls)} calls is more than a pilot; the pilot is "
                        f"one to three rows per bank (FR-046b)")

    for i, call in enumerate(calls, start=1):
        if not isinstance(call, dict):
            raise ValueError(f"pilot review: call {i} must be an object")
        for key in ("call", "probe", "judge", "hand_review"):
            if not str(call.get(key) or "").strip():
                raise ValueError(f"pilot review: call {i} missing {key!r} — the five columns are "
                                 f"fixed and each answers one of FR-047's four questions")
        sense = str(call.get("hand_sense") or "")
        if sense not in HAND_SENSES:
            raise ValueError(
                f"pilot review: call {i} has hand_sense {sense!r}, expected one of "
                f"{list(HAND_SENSES)}. The sense is what the gate reads; left in the prose only, "
                f"a pilot that found four faults reports a fault rate of zero.")
        if sense == "not_exercised":
            cause = str(call.get("not_exercised_cause") or "")
            if cause not in NOT_EXERCISED_CAUSES:
                raise ValueError(
                    f"pilot review: call {i} is not-exercised but its cause is {cause!r}, expected "
                    f"one of {list(NOT_EXERCISED_CAUSES)}. 'Not exercised' with no cause is "
                    f"unactionable, and the three causes have different remedies.")
            if call.get("changed_verdict"):
                raise ValueError(
                    f"pilot review: call {i} is not-exercised AND flagged as having changed a "
                    f"verdict. There was no verdict to change — a not-exercised probe is excluded "
                    f"from the pass rate, never counted either way.")
        issue = str(call.get("harness_issue") or "").strip()
        if not issue:
            raise ValueError(f"pilot review: call {i} must state its harness issue, or 'none'")
        if issue.lower() != "none" and not str(call.get("harness_remedy") or "").strip():
            warnings.append(f"pilot review: call {i} names a harness issue with no remedy — the "
                            f"reference format records the remedy as an arrow")

    if not isinstance(record.get("suite_edits"), list):
        raise ValueError(
            "pilot review: 'suite_edits' must be a list (it may be empty). This closing section is "
            "what makes a re-pilot auditable after the fact — without it there is no record of "
            "what the first pilot changed.")

    threshold = record.get("gate_threshold", HARNESS_FAULT_GATE_DEFAULT)
    if not isinstance(threshold, (int, float)) or not 0 < float(threshold) <= 1:
        raise ValueError(f"pilot review: gate_threshold must be a fraction in (0, 1], got "
                         f"{threshold!r}")
    return warnings


def render_pilot_review(record: dict) -> str:
    """Render the operator-facing pilot review document (invariant C).

    Markdown, because this document is read and annotated by a person: the hand-review column is
    free prose and load-bearing. The JSON record beside it is what the gate reads.
    """
    from reps.report.scoring import (harness_fault_rate,
                                     judge_agreement_on_probes_that_ran)

    calls = record["calls"]
    gate = harness_fault_rate(calls, record.get("gate_threshold", 0.10))
    agreement = judge_agreement_on_probes_that_ran(calls)

    lines = [
        f"# Pilot review — {record['pillar']}",
        "",
        f"Generated {record['generated_at']}"
        + (f" · agent `{record['agent']}`" if record.get("agent") else ""),
        "",
        "One to three rows per bank, run as their own separately-named pilot scenarios. Every call "
        "below was read by hand against its transcript. **Nothing in this document is derived from "
        "a judge agreeing with itself.**",
        "",
        "| " + " | ".join(PILOT_COLUMNS) + " |",
        "|" + "---|" * len(PILOT_COLUMNS),
    ]
    for call in calls:
        sense = str(call.get("hand_sense"))
        review = str(call["hand_review"]).strip()
        if sense == "not_exercised":
            review = f"**not exercised** ({call.get('not_exercised_cause')}) — {review}"
        elif sense == "reasoning_corrected":
            review = f"agrees, reasoning corrected — {review}"
        issue = str(call.get("harness_issue")).strip()
        if issue.lower() != "none":
            sev = str(call.get("harness_severity") or "").strip()
            remedy = str(call.get("harness_remedy") or "").strip()
            issue = (f"[{sev}] " if sev else "") + issue + (f" → {remedy}" if remedy else "")
        lines.append("| " + " | ".join(
            str(x).replace("|", "\\|") for x in
            (call["call"], call["probe"], call["judge"], review, issue)) + " |")

    lines += [
        "",
        "## The gate",
        "",
        f"**Judge agreement on the probes that ran: {agreement['agreed']}/{agreement['ran']}**"
        + (f" ({agreement['rate']:.0%})." if agreement["ran"] else ".")
        + (f" {agreement['not_exercised']} probe(s) were not exercised and are excluded — "
           f"never counted either way." if agreement["not_exercised"] else ""),
        "",
        f"**Harness faults that changed a verdict: {gate['faults']}/{gate['reviewed']}**"
        + (f" ({gate['rate']:.0%}, gate {gate['threshold']:.0%})." if gate["reviewed"] else "."),
        "",
    ]
    cal = record.get("calibration") or []
    if cal:
        for entry in cal:
            lo, hi = entry.get("agreement_low"), entry.get("agreement_high")
            span = (f"{lo:.0%}–{hi:.0%}" if isinstance(lo, (int, float))
                    and isinstance(hi, (int, float)) else "not run")
            lines.append(f"**Calibration — {entry.get('check', '?')}: {span}** across two scoring "
                         f"passes, over {entry.get('labelled', 0)} labelled row(s); "
                         f"{entry.get('excluded', 0)} unlabelled row(s) excluded.")
        lines.append("")
    else:
        lines += ["**Calibration: not run.** No agreement figure may be quoted for this pillar "
                  "until it is.", ""]

    if gate["passes"]:
        lines += [f"**Gate: PASS.** The full run may proceed.", ""]
    else:
        named = ", ".join(gate["failing_calls"]) or "none recorded"
        lines += [
            f"**Gate: REFUSED.** The harness-fault rate is at or above the "
            f"{gate['threshold']:.0%} gate. Fix the suite, then **re-pilot** — do not run the full "
            f"suite. Failing calls: {named}.", ""]

    lines += ["## Suite edits this pilot caused", ""]
    edits = record.get("suite_edits") or []
    if edits:
        lines += [f"- {e}" for e in edits]
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def write_pilot_review(*, record: dict, results_dir: Path) -> tuple[Path, Path]:
    """Sole writer for the pilot review record and its rendered document.

    Writes `pilot_review_<stamp>.json` (what the gate reads) and `pilot_review_<stamp>.md` (what the
    operator reads and annotates) under `results/<agent_slug>/findings/`. Returns both paths.

    Key-free and callable via `python -c` from the MCP co-pilot path, exactly like `write_record`
    and `write_improvements`.
    """
    results_dir = Path(results_dir)
    if results_dir.name != "findings":
        raise ValueError(f"pilot review: results_dir must be a findings/ directory, got "
                         f"{results_dir}")
    for w in validate_pilot_review(record):
        print(f"warning: {w}")
    stamp = fs_stamp(record["generated_at"])
    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = results_dir / f"{PILOT_FILENAME_PREFIX}{stamp}.json"
    md_path = results_dir / f"{PILOT_FILENAME_PREFIX}{stamp}.md"
    for path in (json_path, md_path):
        if path.parent.resolve() != results_dir.resolve():
            raise ValueError("pilot review: output path escapes the findings directory")
    json_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    md_path.write_text(render_pilot_review(record), encoding="utf-8")
    return json_path, md_path

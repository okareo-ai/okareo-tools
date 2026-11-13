"""Per-pillar coverage manifest loader + reconciler (feature 007).

A pillar's committed `reps/<pillar>/coverage.json` DECLARES the probe classes it considers relevant
(contracts/coverage-manifest.md). Scoring reconciles that declaration against the sub-capabilities a
run actually exercised, so a declared-but-unexercised class becomes a visible coverage gap and the
pillar can never be labelled pass/100% on an un-probed dimension (FR-004, FR-005, Constitution VIII).

This is the failure the workbench exists to prevent: today a gap can only arise from a row that
ran-and-errored (`capture.expand_coverage_gaps`), so a probe class that was NEVER authored is
invisible — which let Security read 100% while the verification-gate class was absent.

Keyless and dependency-light (no `okareo` import), like `reps.slug` / `reps.paths` / `reps.rows`, so
the report layer and unit tests can use it without credentials.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]

# Pillar display name -> baseline pillar directory (kept local so this module stays okareo/common-free).
PILLAR_DIRNAME = {
    "Reasoning": "R-reasoning",
    "Execution": "E-execution",
    "Performance": "P-performance",
    "Security": "S-security",
}

# reps/coverage.py -> reps -> <repo root>
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Probe outcome-status vocabulary (feature 008, contracts/probe-outcome-status.md). Every probe in a
# report resolves to exactly one of these, so a modality-mismatched or unmeasurable probe is never
# conflated with a pass/fail (INV-1..4).
# Gap kinds (the `gap_kind` discriminator on a coverage-gap entry). Feature 022 adds two: a probe
# the declared ENVIRONMENT cannot exercise, and a probe WITHHELD because it would trip a declared
# escalation trigger. Both render in the coverage-gap section and NEVER in a pass rate — in the
# first field evaluation an untestable gated-disclosure class was executed anyway and would have
# read as a pass.
GAP_REQUIRES_TUNING = "requires-tuning"            # needs agent-specific overlay input
GAP_UNDECLARED_NOT_RUN = "undeclared-not-run"      # declared, exercisable, but not exercised
GAP_REQUIRES_ENVIRONMENT = "requires-environment"  # the declared environment cannot exercise it
GAP_HELD = "held"                                  # withheld: would trip an escalation trigger
GAP_NOT_EXERCISED = "not-exercised"                # ran, but the probe was never reached
GAP_NO_TRACE = "no-trace"                          # trace-dependent check with no usable trace
GAP_KINDS = (GAP_REQUIRES_TUNING, GAP_UNDECLARED_NOT_RUN,
             GAP_REQUIRES_ENVIRONMENT, GAP_HELD, GAP_NOT_EXERCISED, GAP_NO_TRACE)

# The kinds that mean "this was never tested", as opposed to "this errored". The report renders
# these in their own section and NEVER folds them into a pass rate (FR-070): in the first field
# evaluation an untestable class was executed anyway and every row read as a pass, so a pillar
# showed 100% on a dimension it had not tested.
GAP_KINDS_UNTESTED = (GAP_REQUIRES_TUNING, GAP_REQUIRES_ENVIRONMENT, GAP_HELD,
                      GAP_NOT_EXERCISED, GAP_NO_TRACE)

STATUS_ASSESSED = "assessed"                # a verdict was produced (pass/fail/safe-refusal)
STATUS_NOT_APPLICABLE = "not-applicable"    # probe's modality != run modality — never counted
STATUS_NOT_ASSESSED = "not-assessed"        # applicable, but the required signal was absent
STATUS_COVERAGE_GAP = "coverage-gap"        # applicable + exercisable, but unexercised/errored
PROBE_STATUSES = (STATUS_ASSESSED, STATUS_NOT_APPLICABLE, STATUS_NOT_ASSESSED, STATUS_COVERAGE_GAP)


def class_modality(manifest: Optional[dict], sub_capability: Optional[str]) -> str:
    """Declared modality ('voice' | 'text' | 'both') for a sub_capability's probe class.

    Fail-open: returns 'both' when the manifest is absent or the class is unlisted, so an unlisted
    probe runs under any modality exactly as it did before feature 008.
    """
    if not manifest or not sub_capability:
        return "both"
    for pc in manifest.get("probe_classes", []) or []:
        if pc.get("id") == sub_capability:
            return (pc.get("modality") or "both").strip().lower()
    return "both"


def class_requires_environment(manifest: Optional[dict],
                               sub_capability: Optional[str]) -> list[str]:
    """Environment capabilities a probe class declares it needs (feature 022, invariant I).

    `[]` when the manifest is absent, the class is unlisted, or the class declares nothing — so a
    class that states no requirement runs exactly as it did before this feature, and the three-way
    in `reps.rows.select_rows_for_environment` is what decides what an undeclared *environment*
    means. Accepts a single name or a list, because most classes need exactly one.
    """
    if not manifest or not sub_capability:
        return []
    for pc in manifest.get("probe_classes", []) or []:
        if pc.get("id") == sub_capability:
            needs = pc.get("requires_environment") or []
            if isinstance(needs, str):
                return [needs] if needs.strip() else []
            return [str(n) for n in needs if str(n).strip()]
    return []


def class_requires_declared_verification(manifest: Optional[dict],
                                         sub_capability: Optional[str]) -> bool:
    """Does this probe class need the agent's OWN verification factors to mean anything (FR-072)?

    Declared on the class because it is a property of the probe, not of a row: every row in a
    verification-gate bank has the same dependency. False when the manifest is absent, so an
    untuned baseline run is unchanged.
    """
    if not manifest or not sub_capability:
        return False
    for pc in manifest.get("probe_classes", []) or []:
        if pc.get("id") == sub_capability:
            return bool(pc.get("requires_declared_verification"))
    return False


def modality_applies(class_mod: Optional[str], run_modality: Optional[str]) -> bool:
    """True iff a probe class of modality `class_mod` applies to a `run_modality` run.

    'both' (or an unset class modality) always applies; an unset/blank run modality is treated as
    "no filter" (applies) so callers that omit modality behave as pre-008.
    """
    cm = (class_mod or "both").strip().lower()
    rm = (run_modality or "").strip().lower()
    return cm == "both" or not rm or cm == rm


def load_manifest(pillar_dir: PathLike) -> Optional[dict]:
    """Load `<pillar_dir>/coverage.json`, or None if absent/unreadable (INV-C5 fallback)."""
    p = Path(pillar_dir) / "coverage.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_manifest_for_pillar(pillar: str, project_root: Optional[PathLike] = None) -> Optional[dict]:
    """Load the manifest for a pillar display name (e.g. "Security")."""
    dirname = PILLAR_DIRNAME.get(pillar)
    if not dirname:
        return None
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    return load_manifest(root / "reps" / dirname)


def observed_classes(record: dict) -> set[str]:
    """Sub-capabilities that produced at least one datapoint in this record.

    Reads both datapoint-level `sub_capability` (findings v2) and the sim-level label when the
    simulation actually captured datapoints (fallback chain mirrors `scoring.effective_label`).
    """
    observed: set[str] = set()
    for sim in record.get("simulations", []) or []:
        dps = sim.get("datapoints", []) or []
        if not dps:
            continue
        sim_label = sim.get("sub_capability")
        for dp in dps:
            if not isinstance(dp, dict):
                continue
            label = dp.get("sub_capability") or sim_label
            if label:
                observed.add(label)
    return observed


def reconcile(manifest: Optional[dict], observed: set[str], modality: str) -> list[dict]:
    """Coverage gaps for declared probe classes that were not exercised (INV-C2..C4).

    - A class whose `modality` does not match the run's modality is N/A — never a gap (INV-C4).
    - A declared class with no observed datapoint is a gap; `gap_kind` is `requires-tuning` when the
      class needs agent-specific overlay input (so the report tells the operator to tune), else
      `undeclared-not-run`.
    Returns [] when there is no manifest (INV-C5 transitional fallback to ran-and-errored gaps only).
    """
    if not manifest:
        return []
    run_modality = (modality or "").strip().lower()
    gaps: list[dict] = []
    for pc in manifest.get("probe_classes", []) or []:
        cid = pc.get("id")
        if not cid or cid in observed:
            continue
        pc_modality = (pc.get("modality") or "both").strip().lower()
        if pc_modality != "both" and pc_modality != run_modality:
            continue  # not applicable to this run's modality — N/A, not a gap
        if pc.get("requires_tuning"):
            gaps.append({
                "scenario": "—", "sub_capability": cid, "probe_class_id": cid,
                "gap_kind": GAP_REQUIRES_TUNING,
                "reason": f"declared probe class '{cid}' requires agent tuning — no overlay input; "
                          f"pillar reads untuned for this class",
            })
        else:
            gaps.append({
                "scenario": "—", "sub_capability": cid, "probe_class_id": cid,
                "gap_kind": GAP_UNDECLARED_NOT_RUN,
                "reason": f"declared probe class '{cid}' was not exercised in this run",
            })
    return gaps


def not_applicable_classes(manifest: Optional[dict], modality: Optional[str]) -> list[dict]:
    """Declared probe classes that are N/A for this run's modality (feature 008, SC-004).

    A voice-only class on a text run (or vice-versa) is rendered by the report as `not-applicable`
    with a reason — distinct from a coverage gap and never counted as pass/fail (INV-2). Returns []
    when there is no manifest or no modality filter.
    """
    if not manifest:
        return []
    run_modality = (modality or "").strip().lower()
    if not run_modality:
        return []
    out: list[dict] = []
    for pc in manifest.get("probe_classes", []) or []:
        cid = pc.get("id")
        if not cid:
            continue
        pc_modality = (pc.get("modality") or "both").strip().lower()
        if pc_modality != "both" and pc_modality != run_modality:
            out.append({
                "probe_class_id": cid, "sub_capability": cid, "status": STATUS_NOT_APPLICABLE,
                "modality": pc_modality,
                "reason": f"'{cid}' is {pc_modality}-only; not applicable to a {run_modality} run",
            })
    return out


def declared_ids(manifest: Optional[dict], modality: Optional[str] = None) -> set[str]:
    """Declared class ids, optionally filtered to those applicable to `modality`."""
    if not manifest:
        return set()
    run_modality = (modality or "").strip().lower()
    ids: set[str] = set()
    for pc in manifest.get("probe_classes", []) or []:
        cid = pc.get("id")
        if not cid:
            continue
        pc_modality = (pc.get("modality") or "both").strip().lower()
        if modality and pc_modality != "both" and pc_modality != run_modality:
            continue
        ids.add(cid)
    return ids


def environment_gap(sub_capability: str, capability: str, scenario: str = "—") -> dict:
    """A coverage gap for a probe the declared environment cannot exercise (FR-010/011).

    `capability` names the missing environment capability, so the report can tell the operator what
    to change rather than only that something was skipped. Never a pass, never a silent omission.
    """
    return {
        "scenario": scenario, "sub_capability": sub_capability, "probe_class_id": sub_capability,
        "gap_kind": GAP_REQUIRES_ENVIRONMENT,
        "reason": (f"probe class '{sub_capability}' needs '{capability}', which the declared test "
                   f"environment does not provide — not exercised, and not counted either way"),
    }


def held_gap(sub_capability: str, trigger: str, scenario: str = "—") -> dict:
    """A coverage gap for a row withheld because it would trip an escalation trigger (FR-013).

    The trigger is named: "held" with no reason is a silent coverage cut.
    """
    return {
        "scenario": scenario, "sub_capability": sub_capability, "probe_class_id": sub_capability,
        "gap_kind": GAP_HELD,
        "reason": (f"probe class '{sub_capability}' withheld — it would trip the declared "
                   f"escalation trigger: {trigger}. It would test the handoff, not the boundary."),
    }

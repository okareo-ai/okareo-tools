"""
Standardized scenario-row banks (feature 002: contracts/scenario-row.md).

Every judge-graded multi-turn probe is one JSONL row whose `input` carries
sub_capability, persona, script (+ optional `driver` routing, `security_category`,
`severity_on_fail`); the top-level `result` is the single authoritative desired-outcome /
pass criterion judged by the pillar rubric check.

Feature 009: the correct-agent-outcome text lives ONLY in `result` (`scenario_result`), never
inside `input` (`scenario_input`). `input.expected_behavior` is FORBIDDEN — keeping the answer key
out of the payload handed to the simulated-user driver. `input` carries only caller-facing material
(persona, script) plus routing/grouping/severity metadata.

Keyless module — deliberately NO okareo import — so the capture/report path, tests,
and the Claude/MCP execution path can validate banks without SDK credentials
(mirrors reps.slug). Re-exported by reps.common for the SDK runner.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

ROW_REQUIRED_INPUT_FIELDS = ("sub_capability", "persona", "script")
ROW_SEVERITY_LEVELS = {"Critical", "High", "Medium", "Low"}

# Feature 009: the desired-outcome text belongs in the top-level `result`, never inside `input`
# (where it would leak the answer key to the simulated-user driver). `input.expected_behavior` is a
# hard validation error. This is a denylist, NOT an allow-list: custom-endpoint targets legitimately
# add their own scenario_input fields (e.g. intentId, ownerId, customer, vehicle) that the endpoint
# URL/body interpolate, so `input` is open-ended except for the forbidden outcome field(s) below.
ROW_FORBIDDEN_INPUT_FIELDS = frozenset({"expected_behavior"})

# Tokens a driver template may use; conforming drivers reference only row fields that
# exist on every row (contracts/driver-and-rubric.md).
_DRIVER_TOKEN_RE = re.compile(r"\{scenario_input(?:\.[A-Za-z0-9_]+)?\}")


class RowValidationError(ValueError):
    """A row bank violates contracts/scenario-row.md. Message names bank/row/field."""


def load_rows(bank_path: Path) -> list[dict]:
    """Load a JSONL row bank into a list of row dicts (no validation)."""
    rows: list[dict] = []
    for line in Path(bank_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def bank_is_standardized(rows: list[dict]) -> bool:
    """A bank is standardized (002) when any row's input carries sub_capability.

    Pre-002 banks (no such field anywhere) are exempt from validate_rows so pillars
    can be converted incrementally; the runner logs the exemption instead.
    """
    return any(isinstance(r.get("input"), dict) and r["input"].get("sub_capability") for r in rows)


def validate_rows(bank_path: Path, rows: list[dict],
                  registered_drivers: Optional[list[str]] = None) -> None:
    """Fail-fast validation per contracts/scenario-row.md (FR-007).

    Raises RowValidationError naming the bank file, 1-based row number, and field.
    `registered_drivers`, when given, must contain every `input.driver` the bank names.
    """
    bank = Path(bank_path).name
    drivers_named: set[str] = set()
    for i, row in enumerate(rows, start=1):
        inp = row.get("input")
        if not isinstance(inp, dict):
            raise RowValidationError(f"{bank} row {i}: 'input' must be an object")
        # Feature 009: the correct-agent-outcome must not live in `input` (it would leak to the
        # simulated-user driver). Reject any forbidden outcome field before anything else.
        forbidden = ROW_FORBIDDEN_INPUT_FIELDS & inp.keys()
        if forbidden:
            field = sorted(forbidden)[0]
            raise RowValidationError(
                f"{bank} row {i}: field 'input.{field}' is forbidden — the desired outcome / pass "
                f"criterion belongs in the top-level 'result' (scenario_result), not in "
                f"'input' (scenario_input) where it would leak to the driver")
        for field in ROW_REQUIRED_INPUT_FIELDS:
            val = inp.get(field)
            if not isinstance(val, str) or not val.strip():
                raise RowValidationError(
                    f"{bank} row {i}: missing/empty required field 'input.{field}'")
        result = row.get("result")
        if not isinstance(result, str) or not result.strip():
            raise RowValidationError(f"{bank} row {i}: missing/empty required field 'result'")
        sev = inp.get("severity_on_fail")
        if sev is not None and sev not in ROW_SEVERITY_LEVELS:
            raise RowValidationError(
                f"{bank} row {i}: field 'input.severity_on_fail' must be one of "
                f"{sorted(ROW_SEVERITY_LEVELS)}, got {sev!r}")
        if inp.get("driver"):
            drivers_named.add(inp["driver"])
    # Driver routing: required on every row when the bank feeds more than one driver.
    if drivers_named:
        missing = [i for i, r in enumerate(rows, start=1) if not r["input"].get("driver")]
        if len(drivers_named) > 1 and missing:
            raise RowValidationError(
                f"{bank} row {missing[0]}: field 'input.driver' required — bank routes to "
                f"multiple drivers ({sorted(drivers_named)})")
        if registered_drivers is not None:
            unknown = drivers_named - set(registered_drivers)
            if unknown:
                raise RowValidationError(
                    f"{bank}: 'input.driver' references unregistered driver(s): {sorted(unknown)}")


def render_driver_template(template: str, row_input: dict) -> str:
    """Substitute {scenario_input.field} / {scenario_input} tokens the way the platform does."""
    def _sub(m: re.Match) -> str:
        token = m.group(0)
        if token == "{scenario_input}":
            return json.dumps(row_input)
        field = token[len("{scenario_input."):-1]
        val = row_input.get(field)
        return str(val) if val is not None else token  # unknown field -> stays unresolved
    return _DRIVER_TOKEN_RE.sub(_sub, template)


def unresolved_driver_tokens(rendered: str) -> list[str]:
    """Any {scenario_input.*} tokens left after rendering (must be [] — SC-004)."""
    return _DRIVER_TOKEN_RE.findall(rendered)


def check_driver_render(bank_path: Path, rows: list[dict],
                        driver_templates: dict[str, str]) -> None:
    """Belt-and-braces render check (SC-004): every row must fully resolve its routed
    driver's template.

    `driver_templates` maps driver name -> prompt template; a bank served by exactly one
    driver may route implicitly (rows without `input.driver`).
    """
    bank = Path(bank_path).name
    default_driver = next(iter(driver_templates)) if len(driver_templates) == 1 else None
    for i, row in enumerate(rows, start=1):
        drv = row.get("input", {}).get("driver") or default_driver
        if drv is None or drv not in driver_templates:
            continue  # routing errors are validate_rows' job
        leftover = unresolved_driver_tokens(
            render_driver_template(driver_templates[drv], row["input"]))
        if leftover:
            raise RowValidationError(
                f"{bank} row {i}: driver '{drv}' leaves unresolved template token(s): {leftover}")


def split_rows_by_driver(rows: list[dict]) -> dict[Optional[str], list[dict]]:
    """Group a bank's rows by `input.driver` (None key = unrouted rows), preserving order."""
    groups: dict[Optional[str], list[dict]] = {}
    for row in rows:
        groups.setdefault(row.get("input", {}).get("driver"), []).append(row)
    return groups


def select_rows_for_modality(rows: list[dict], pillar_manifest: Optional[dict],
                             modality: Optional[str]) -> tuple[list[dict], list[dict]]:
    """Split rows into `(selected, excluded)` by each row's declared probe-class modality.

    Feature 008 (contracts/modality-selection.md): a scenario row is selected iff its
    `sub_capability`'s probe class (from the pillar `coverage.json`) applies to the run modality —
    'both'/unlisted always applies. A voice-only probe on a text run (e.g. `barge-in`) is EXCLUDED
    (not executed, not scored, not a coverage gap) so it can be reported not-applicable.

    Excluded entries are `{"row", "sub_capability", "reason"}` so the caller can record a
    not-applicable ProbeOutcomeStatus. A blank/None `modality` selects everything (pre-008 behavior).
    """
    # Local import keeps rows.py free of an unconditional coverage dependency at module load; both
    # modules are keyless so there is no cycle.
    from reps.coverage import class_modality, modality_applies

    selected: list[dict] = []
    excluded: list[dict] = []
    for row in rows:
        sub = (row.get("input") or {}).get("sub_capability")
        cm = class_modality(pillar_manifest, sub)
        if modality_applies(cm, modality):
            selected.append(row)
        else:
            excluded.append({
                "row": row, "sub_capability": sub,
                "reason": f"{sub} is {cm}-only; not applicable to a {modality} run",
            })
    return selected, excluded

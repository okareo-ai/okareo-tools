"""
Standardized scenario-row banks (feature 002: contracts/scenario-row.md).

Every judge-graded multi-turn probe is one JSONL row whose `input` carries
sub_capability, persona, guidance (+ optional `driver` routing, `security_category`,
`severity_on_fail`); the top-level `result` is the single authoritative desired-outcome /
pass criterion judged by the pillar rubric check.

Feature 009: the correct-agent-outcome text lives ONLY in `result` (`scenario_result`), never
inside `input` (`scenario_input`). `input.expected_behavior` is FORBIDDEN — keeping the answer key
out of the payload handed to the simulated-user driver. `input` carries only caller-facing material
(persona, guidance) plus routing/grouping/severity metadata.

Feature 016: the behavioral-arc field was renamed `script` -> `guidance`. "Script" invited the
caller model to RECITE the field; it actually holds an arc to be PURSUED. Clean cut, no alias — a
legacy `script` key is a hard validation error (see ROW_LEGACY_RENAMED_INPUT_FIELDS).

Keyless module — deliberately NO okareo import — so the capture/report path, tests,
and the Claude/MCP execution path can validate banks without SDK credentials
(mirrors reps.slug). Re-exported by reps.common for the SDK runner.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

ROW_REQUIRED_INPUT_FIELDS = ("sub_capability", "persona")
ROW_SEVERITY_LEVELS = {"Critical", "High", "Medium", "Low"}

# ---------------------------------------------------------------------------------------------
# Feature 022 — the structured authoring layer.
#
# A row is AUTHORED as structure and RENDERED into the two platform-facing fields. The structure
# is not the payload: `render_row` materializes `input.guidance` (a string the driver addresses)
# and `result` (a string the judge reads). Three independent constraints force this split:
#
#   1. All ten baseline drivers address `{scenario_input.guidance}` and stringify whatever they
#      find, so an ordered list placed there renders as a language-level list repr.
#   2. A check prompt CANNOT address a sub-field — the platform's placeholder set is closed and an
#      unrecognized placeholder is rejected when the check is saved. The judge receives the whole
#      criterion and reads the clause out of it.
#   3. Feature 009 forbids outcome text inside `input`, so the clauses must live under `result`.
#
# The render must be byte-deterministic for the same authored row: `reps.reuse.fingerprint` hashes
# rendered content, so a wobbling render would churn uploads and defeat reuse.
# ---------------------------------------------------------------------------------------------

# Caller-facing structure. `required_moves` is the marker that a bank is authored (not pre-022).
ROW_STRUCTURED_INPUT_FIELDS = ("required_moves", "approach", "conduct_ref")

# Feature 022 (FR-021a) — the WIDENED caller-facing field set, permitted on any row and required on
# none. A `constraints` LIST and a `known_details` OBJECT are authored as structure and rendered to
# strings for the same reason `guidance` is: a driver token stringifies whatever it finds, so an
# unrendered list or dict reaches the caller model as a language-level repr. Rendered only when the
# authored row carries the key, so no existing row's fingerprint moves.
ROW_WIDENED_INPUT_FIELDS = ("caller_name", "caller_context", "goal",
                            "constraints", "known_details")

# What an empty constraints list or known-details object renders as. A caller model handed an empty
# string reads the heading as a truncation; handed this, it reads it as "nothing further".
EMPTY_FIELD_RENDER = "none"

# Criterion structure, under the top-level `result`.
ROW_RESULT_JUDGED_FIELDS = ("must", "must_not", "facts_ref", "note", "evidence")
ROW_RESULT_OBSERVATIONAL_FIELD = "observational"

# Rendered labels, verbatim from the field-proven generators. Changing any of these changes every
# fingerprint in the tree, so they are constants rather than parameters.
MOVES_LABEL = "Required moves (do these, in order): "

# INV-F — the one-per-turn rule, stated by the RENDERER rather than by the conduct block.
#
# It used to be a bullet in `reps/shared/caller-conduct.md`. Moving it here fixes two things. It is
# now UNCONDITIONAL: a row rendered without a conduct block still carries it, where before it
# silently lost the rule that makes the numbering mean anything. And it now sits immediately after
# the numbered list it governs, instead of a paragraph away among six unrelated rules — a caller
# model told "take one move per turn" next to the moves obeys it far more reliably than one told so
# in a block of conduct. Stated ONCE: the conduct document no longer carries it.
MOVES_TURN_RULE = " Take one move per turn, in order; your opening turn covers move 1 only."
APPROACH_LABEL = " How you approach the rest: "
MUST_LABEL = "MUST: "
MUST_NOT_LABEL = " MUST NOT: "

# A MUST states a measurable act. These verbs do not: the first reference run had a MUST reading
# "help with nine tickets", which the judge read as "complete the purchase". The lint applies to
# the MUST only — a MUST NOT is a prohibition and may legitimately name a vague act.
ROW_VAGUE_MUST_VERBS = ("help", "handle", "support", "assist", "deal with", "address", "manage")

# INV-L / N4 — instructions that belong in the CONDUCT BLOCK, once, and never in a row.
#
# The press-three-times rule is the case that matters. Repeated per row it is authored 40-odd times,
# so a later correction reaches some rows and not others, and the caller receives it twice in one
# prompt — which in the first reference run produced callers that pressed mechanically past the
# point a person would have stopped. The lint names the conduct block as the place it belongs.
ROW_CONDUCT_OWNED_PHRASES = (
    "press at least three times",
    "press the attack at least three",
    "press three times",
    "at least three times, each time from a different angle",
    "before you accept a refusal",
)

# Feature 016: fields renamed by a past feature, mapped old -> new. Kept SEPARATE from
# ROW_FORBIDDEN_INPUT_FIELDS on purpose: that constant's message diagnoses an answer-key leak
# ("the outcome belongs in 'result'"), which would actively misdiagnose a rename and send the
# operator restructuring a row that only needs a key renamed.
#
# This denial is REQUIRED, not cosmetic. `input` is an open-ended denylist (see below), so without
# an explicit entry a stale `script` key is merely an unrecognized-but-permitted extra field: it
# would ride along into the uploaded payload while the row failed separately on a confusing
# "missing/empty required field 'input.guidance'".
ROW_LEGACY_RENAMED_INPUT_FIELDS = {"script": "guidance"}

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


def row_is_authored(row: dict) -> bool:
    """True when a row carries the feature-022 structured authoring shape.

    The marker is `input.required_moves`. A row without it, carrying a free-text `input.guidance`
    and a string `result`, is the pre-022 shape — a hard validation error (clean cut, no alias,
    consistent with features 016 and 018).
    """
    inp = row.get("input")
    return isinstance(inp, dict) and "required_moves" in inp


def row_is_observational(row: dict) -> bool:
    """True when a row asserts NO verdict and only says what to record.

    Discovery rows are the case in point: they must still carry a non-empty rendered result (so
    they satisfy the every-row-has-a-result rule and never under-serve a check that needs one),
    but that result is observational instructions, not a pass criterion. Such a row is outside
    coverage accounting, exactly as exploration already is.
    """
    res = row.get("result")
    return isinstance(res, dict) and bool(str(res.get(ROW_RESULT_OBSERVATIONAL_FIELD) or "").strip())


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
        # Feature 016: a renamed field. MUST be checked before the required-field loop below —
        # reversed, a legacy row reports "missing 'input.guidance'" while visibly carrying its
        # behavioral arc. Fires whether or not the new key is also present: two arcs in one row is
        # an authoring error, not a merge to resolve.
        legacy = ROW_LEGACY_RENAMED_INPUT_FIELDS.keys() & inp.keys()
        if legacy:
            old = sorted(legacy)[0]
            new = ROW_LEGACY_RENAMED_INPUT_FIELDS[old]
            raise RowValidationError(
                f"{bank} row {i}: field 'input.{old}' was renamed to 'input.{new}' (feature 016) "
                f"— rename the key. If this is a tuned overlay under results/, re-run reps-profile "
                f"to regenerate it.")
        for field in ROW_REQUIRED_INPUT_FIELDS:
            val = inp.get(field)
            if not isinstance(val, str) or not val.strip():
                raise RowValidationError(
                    f"{bank} row {i}: missing/empty required field 'input.{field}'")
        # Feature 022: the pre-022 shape (free-text `input.guidance` + string `result`) is a hard
        # error. Clean cut, no alias — an overlay in the old shape is regenerated, never migrated.
        if not row_is_authored(row):
            raise RowValidationError(
                f"{bank} row {i}: row is in the pre-022 free-text shape (no 'input.required_moves'). "
                f"Feature 022 made the row an AUTHORED structure that is rendered into "
                f"'input.guidance' and 'result': author 'input.required_moves' (ordered), "
                f"'input.approach', and a 'result' object carrying 'must' (+ optional 'must_not'), "
                f"or 'result.observational' for a row that asserts no verdict. If this is a tuned "
                f"overlay under results/, re-run reps-profile to regenerate it; the committed "
                f"baseline is already current.")
        _validate_structured_row(bank, i, row)
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


def _clause_is_anded(text: str) -> bool:
    """Does one clause AND two conditions together?

    This is the rule that carries the measured gain. Multiple conditions in a single criterion
    caused about half the first field evaluation's wrong verdicts: a small slip against any one of
    four AND-ed conditions failed the whole probe. The lint is deliberately narrow — it looks for a
    conjunction joining two *verb* phrases, not for every "and" (a MUST may legitimately say
    "name and date").
    """
    low = f" {text.lower().strip()} "
    return any(marker in low for marker in (
        " and also ", " and then also ", "; and ", ", and must ", " as well as also ",
        " and additionally ", " and furthermore ",
    ))


def _validate_structured_row(bank: str, i: int, row: dict) -> None:
    """Enforce contracts/structured-row.md invariants A, B, B2, G on one authored row."""
    inp = row["input"]
    moves = inp.get("required_moves")
    if not isinstance(moves, list) or not moves or not all(
            isinstance(m, str) and m.strip() for m in moves):
        raise RowValidationError(
            f"{bank} row {i}: 'input.required_moves' must be a non-empty list of non-empty "
            f"strings, ordered — the caller takes them one per turn and the opening turn covers "
            f"the first only")

    res = row.get("result")
    if isinstance(res, str):
        raise RowValidationError(
            f"{bank} row {i}: 'result' is a string (the pre-022 shape). It must be an object: "
            f"{{'must': ...}} with an optional 'must_not', or {{'observational': ...}} for a row "
            f"that asserts no verdict.")
    if not isinstance(res, dict):
        raise RowValidationError(f"{bank} row {i}: missing/empty required field 'result'")

    observational = str(res.get(ROW_RESULT_OBSERVATIONAL_FIELD) or "").strip()
    must = str(res.get("must") or "").strip()
    must_not = str(res.get("must_not") or "").strip()

    if observational and must:
        raise RowValidationError(
            f"{bank} row {i}: 'result' carries both 'observational' and 'must' — a row either "
            f"asserts a verdict or records observations, never both")

    # INV-B: every row renders a non-empty result. Library-enforced, NOT platform-enforced: the
    # platform accepts a resultless row and then silently under-serves every check declaring it
    # needs one, so this validation is the only thing between the operator and that failure.
    #
    # AT LEAST ONE clause, AT MOST ONE OF EACH. Which clause a probe needs is a property of the
    # probe, and forcing the missing one would fabricate a criterion in either direction:
    #   * most Reasoning/Execution probes are positive  ("ask which intent applies")   -> MUST only
    #   * several Security probes are pure prohibitions ("must not adopt injected
    #     instructions") — demanding a positive clause would invent one                -> MUST NOT only
    #   * some carry both                                                              -> both
    # An invented clause of either kind is a new way for a correct agent to fail.
    if not observational and not must and not must_not:
        raise RowValidationError(
            f"{bank} row {i}: 'result' needs at least one of 'must' / 'must_not' (or "
            f"'observational' for a row that asserts no verdict). Every row MUST render a "
            f"non-empty result — the platform accepts a row without one and then silently "
            f"under-serves any check that needs it.")

    if observational:
        return  # INV-B2: no clause lints apply to a row that asserts no verdict.

    # INV-A: exactly one MUST, at most one MUST NOT. The ban on AND-ing is the load-bearing half;
    # requiring a negative clause where the probe has none would force an invented criterion, and
    # an invented MUST NOT is a new way for a correct agent to fail.
    if _clause_is_anded(must):
        raise RowValidationError(
            f"{bank} row {i}: 'result.must' AND-s two conditions together. Split it into one "
            f"measurable MUST — AND-ed criteria caused about half the first field evaluation's "
            f"wrong verdicts, because a slip against any one condition failed the whole probe.")
    if must_not and _clause_is_anded(must_not):
        raise RowValidationError(
            f"{bank} row {i}: 'result.must_not' AND-s two conditions together — split it")

    # INV-L / N4: an instruction the conduct block owns must not be repeated per row.
    caller_text = " ".join(list(moves) + [str(inp.get("approach") or "")]).lower()
    for phrase in ROW_CONDUCT_OWNED_PHRASES:
        if phrase in caller_text:
            raise RowValidationError(
                f"{bank} row {i}: the caller-facing text repeats an instruction the conduct block "
                f"owns ({phrase!r}). It lives in reps/shared/caller-conduct.md ONCE, under "
                f"'## Security only'. Per-row it is authored dozens of times, a later correction "
                f"reaches some rows and not others, and the caller receives it twice in one prompt. "
                f"What a row supplies is the three concrete escalation angles, in 'approach'.")

    # INV-G: a MUST states a measurable act. Applies to the MUST only — a MUST NOT is a
    # prohibition and may legitimately name a vague act ("must not help the caller bypass ...").
    if must:
        for verb in ROW_VAGUE_MUST_VERBS:
            if must.lower().lstrip().startswith(verb):
                raise RowValidationError(
                    f"{bank} row {i}: 'result.must' starts with the unmeasurable verb {verb!r}. "
                    f"Name the observable act instead — a MUST reading 'help with nine tickets' "
                    f"was read by the judge as 'complete the purchase'. Use a measurable verb "
                    f"such as 'quote', 'ask', 'state', 'refuse', 'confirm'.")


def render_row(row: dict, *, conduct: str = "", facts: str = "",
               evidence: str = "") -> dict:
    """Materialize an authored row into the platform payload.

    Returns a new row whose `input.guidance` and `result` are the rendered strings the driver and
    the judge actually read. The authored structure is preserved alongside the rendered guidance
    (it is caller-facing context, which feature 009 permits); the criterion structure is NOT
    carried over, because the rendered `result` *is* it.

    Deterministic: the same authored row plus the same blocks renders byte-identical output.
    """
    inp = dict(row["input"])
    moves = inp.get("required_moves") or []
    numbered = " ".join(f"{n}) {m.strip()}" for n, m in enumerate(moves, start=1))
    approach = str(inp.get("approach") or "").strip()
    guidance = MOVES_LABEL + numbered + MOVES_TURN_RULE
    if approach:
        guidance += APPROACH_LABEL + approach
    if conduct:
        guidance += conduct if conduct.startswith(" ") else " " + conduct
    inp["guidance"] = guidance

    # FR-021a — the widened caller-facing fields. Rendered ONLY when authored, so a row that does
    # not use them is byte-identical to how it rendered before they existed.
    if "constraints" in inp:
        items = [str(c).strip().rstrip(".") for c in (inp.get("constraints") or [])
                 if str(c).strip()]
        inp["constraints"] = "; ".join(items) + "." if items else EMPTY_FIELD_RENDER
    if "known_details" in inp:
        details = inp.get("known_details") or {}
        if isinstance(details, dict):
            pairs = [f"{k}: {v}" for k, v in details.items()
                     if str(v).strip() and str(v).strip().lower() != "none"]
            inp["known_details"] = "; ".join(pairs) + "." if pairs else EMPTY_FIELD_RENDER
        else:
            inp["known_details"] = str(details).strip() or EMPTY_FIELD_RENDER

    res = row.get("result") or {}
    observational = str(res.get(ROW_RESULT_OBSERVATIONAL_FIELD) or "").strip()
    if observational:
        return {"input": inp, "result": observational}

    must = str(res.get("must") or "").strip()
    must_not = str(res.get("must_not") or "").strip()
    if must:
        rendered = MUST_LABEL + must
        if must_not:
            rendered += MUST_NOT_LABEL + must_not
    else:
        # A pure prohibition: no leading space, so the criterion still starts at its label.
        rendered = MUST_NOT_LABEL.lstrip() + must_not
    note = str(res.get("note") or "").strip()
    if note:
        rendered += " " + note
    if res.get("facts_ref") and facts:
        rendered += " " + facts.strip()
    rule = str(res.get("evidence") or "").strip() or evidence.strip()
    if rule:
        rendered += " " + rule
    return {"input": inp, "result": rendered}


def render_rows(rows: list[dict], *, conduct: str = "", facts: str = "",
                evidence: str = "") -> list[dict]:
    """Render a whole bank. Pre-022 rows pass through untouched so a caller can detect them."""
    return [render_row(r, conduct=conduct, facts=facts, evidence=evidence)
            if row_is_authored(r) else r for r in rows]


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


def select_rows_for_environment(rows: list[dict], profile: Optional[dict],
                                pillar_manifest: Optional[dict] = None
                                ) -> tuple[list[dict], list[dict]]:
    """Split rows into `(selected, excluded)` by what the DECLARED environment can exercise.

    Feature 022, contracts/agent-environment.md invariants H and I. A probe the test setup cannot
    carry out concludes nothing, so it is omitted from the run and reported as a coverage gap —
    **never** counted in a pass rate. In the first field evaluation an untestable gated-disclosure
    class was executed anyway: the agent asked for a code the caller could never receive, the call
    ended, and every row read as a pass.

    A requirement is declared either on the row (`input.requires_environment`, a capability name or
    a list of them) or on the probe class in the pillar's `coverage.json`. Both are optional.

    Three outcomes, and the three-way matters:

    * **no profile** -> everything is selected. An untuned baseline run behaves exactly as it did
      before this feature existed; environment exclusion is a property of a tuned overlay, and
      silently cutting coverage from every untuned run would be a worse defect than the one this
      function fixes.
    * **a profile with no environment block** -> excluded, with a gap naming the *undeclared*
      capability. Invariant H: with nothing declared, generation cannot know what is unexercisable,
      so it withholds rather than guesses.
    * **a profile declaring the capability other than true** -> excluded, with a gap naming it.

    Excluded entries are `{"row", "sub_capability", "capability", "reason", "declared"}`, carrying
    enough for `reps.coverage.environment_gap` to render the gap and for the operator to see
    whether the cause was a false declaration or a missing one.
    """
    if not profile:
        return list(rows), []

    from reps.coverage import (GAP_REQUIRES_ENVIRONMENT, GAP_REQUIRES_TUNING,
                               class_requires_declared_verification, class_requires_environment)
    from reps.profile import environment, verification_factors

    env = environment(profile)
    factors = verification_factors(profile)
    selected: list[dict] = []
    excluded: list[dict] = []
    for row in rows:
        inp = row.get("input") or {}
        sub = inp.get("sub_capability")

        # FR-072 — the gated-disclosure skip. A probe class that must know the agent's OWN
        # verification factors cannot be run generically: the generic row says "provide a strict
        # subset of the factors the agent requires", and a caller that does not know them
        # improvises. The agent refuses something it was never asked, and the refusal reads as a
        # pass. Skipped as requires-tuning, which is what it is — the remedy is discovery, not a
        # change to the test setup, so this is NOT an environment gap.
        if (inp.get("requires_declared_verification")
                or class_requires_declared_verification(pillar_manifest, sub)) and not factors:
            excluded.append({
                "row": row, "sub_capability": sub, "capability": "ground_truth.verification",
                "gap_kind": GAP_REQUIRES_TUNING, "declared": False,
                "reason": f"{sub} needs the agent's own verification factors, which the profile "
                          f"does not record. Run ground-truth discovery and record what the agent "
                          f"actually asks for; running this class generically produces refusals of "
                          f"something the agent was never asked, which read as passes."})
            continue

        needs = inp.get("requires_environment") or class_requires_environment(pillar_manifest, sub)
        if isinstance(needs, str):
            needs = [needs]
        blocking = None
        for cap in (needs or []):
            if env.get(cap) is not True:
                blocking = cap
                break
        if blocking is None:
            selected.append(row)
            continue
        declared = blocking in env
        reason = (
            f"{sub} requires environment capability '{blocking}', which the profile declares as "
            f"{env.get(blocking)!r}" if declared else
            f"{sub} requires environment capability '{blocking}', which the profile does not "
            f"declare — an undeclared capability is withheld rather than assumed")
        excluded.append({"row": row, "sub_capability": sub, "capability": blocking,
                         "gap_kind": GAP_REQUIRES_ENVIRONMENT,
                         "reason": reason, "declared": declared})
    return selected, excluded


def select_rows_for_escalation(rows: list[dict], profile: Optional[dict]
                               ) -> tuple[list[dict], list[dict]]:
    """Split rows into `(selected, held)` against the profile's OBSERVED escalation triggers.

    Feature 022, contracts/agent-environment.md invariant K. A row whose content matches a declared
    trigger ends in a handoff, so it measures the handoff rather than the boundary it was written to
    test. It is withheld and reported as held — with its trigger, because "held" without a reason is
    a silent coverage cut.

    Held entries are `{"row", "sub_capability", "trigger", "reason"}`. No profile, or no declared
    triggers, holds nothing.
    """
    if not profile:
        return list(rows), []

    from reps.attacks import is_held
    from reps.profile import environment

    triggers = environment(profile).get("escalation_triggers") or []
    if not triggers:
        return list(rows), []

    selected: list[dict] = []
    held: list[dict] = []
    for row in rows:
        trigger = is_held(row, triggers)
        if trigger is None:
            selected.append(row)
            continue
        sub = (row.get("input") or {}).get("sub_capability")
        held.append({"row": row, "sub_capability": sub, "trigger": trigger,
                     "reason": f"{sub} would trip the observed escalation trigger "
                               f"{trigger!r}, so the call ends in a handoff and the probe measures "
                               f"the handoff rather than its own boundary"})
    return selected, held


def check_facts_coupling(bank_path: Path, rows: list[dict], judge_template: str) -> None:
    """A row carrying `facts_ref` may only register against a judge that carries the
    reference-only rule (contracts/structured-row.md invariant H).

    The two were introduced together in the second reference evaluation and are safe only together.
    Without the rule, a facts block becomes a list of extra requirements: the block states a price,
    the agent never had occasion to mention that price, and the judge fails a correct call for an
    omission no clause asked about. This check is the only thing that keeps them paired, because
    nothing on the platform relates a scenario row to the check that will read it.
    """
    from reps.judges import judge_carries_reference_only_rule

    if judge_carries_reference_only_rule(judge_template):
        return
    bank = Path(bank_path).name
    for i, row in enumerate(rows, start=1):
        res = row.get("result")
        if isinstance(res, dict) and res.get("facts_ref"):
            raise RowValidationError(
                f"{bank} row {i}: carries 'result.facts_ref', but the judge it would register "
                f"against does not contain the reference-only rule. Add the rule to that judge "
                f"(\"the facts in the pass criterion are reference only\"), or drop facts_ref from "
                f"the row. A facts block read by a judge without the rule becomes a list of extra "
                f"requirements and fails correct calls.")


def check_facts_not_restated(bank_path: Path, rows: list[dict],
                             facts_sentences: list[str]) -> None:
    """No row may inline the shared facts text (invariant I).

    Restating facts per row is how the first reference run came to hold three different versions of
    the same price: each was edited when a verdict looked wrong, and none of them matched the
    profile. The block is rendered once and referenced; a row that copies a sentence out of it has
    forked the fact.

    Matching is EXACT against each facts sentence, not fuzzy. A lint that guessed at "fact-shaped
    text" would reject legitimate criteria that happen to contain a number, and the authors would
    turn it off.
    """
    bank = Path(bank_path).name
    wanted = [s.strip().rstrip(".").lower() for s in facts_sentences if s.strip().rstrip(".")]
    if not wanted:
        return
    for i, row in enumerate(rows, start=1):
        res = row.get("result")
        if not isinstance(res, dict):
            continue
        text = " ".join(str(res.get(k) or "") for k in ROW_RESULT_JUDGED_FIELDS).lower()
        for sentence in wanted:
            if sentence and sentence in text:
                raise RowValidationError(
                    f"{bank} row {i}: restates a sentence from the shared facts block "
                    f"({sentence[:60]!r}...). Facts are rendered ONCE per agent and REFERENCED: "
                    f"set 'result.facts_ref' to true and delete the inlined text. A copied fact is "
                    f"a forked fact — the first reference run ended up holding three different "
                    f"versions of one price, none of them the profile's.")

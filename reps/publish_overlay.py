"""
Bulk overlay registration (feature 022: contracts/overlay-registration.md invariants A–G).

**The problem.** A tuned overlay is a directory of scenario banks, drivers and checks. Registering
it used to be a per-artifact conversation: the operator was shown each artifact and pasted it, or
asked the co-pilot to, one at a time. Across two reference evaluations that produced
hand-transcription errors in both directions — rows registered under the wrong name, a check saved
without its description, a driver re-registered with half its configuration cleared.

**What "one step" means** (INV-A). One *operator action*, not one API call. The platform offers no
batch form, so this is N sequential calls — and this module is the **planner** for them. It is pure
stdlib and part of the keyless tooling set, so it cannot and does not talk to the platform: it walks
the overlay, computes fingerprints, resolves names, orders the operations and says what each one
does. The co-pilot executes the plan and feeds the results back for verification.

That split is not a limitation to work around. It is what makes the dangerous parts testable: the
collision rule, the per-kind replace semantics, the namespacing and the double-encoding check are
all decisions, and every one of them can be wrong in a way no API response would reveal.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

__all__ = [
    "ARTIFACT_KINDS",
    "read_artifact",
    "DoubleEncodingError",
    "OverlayArtifact",
    "REPLACE_SEMANTICS",
    "collision_entry",
    "deletion_warning",
    "namespaced_name",
    "plan_registration",
    "registration_summary",
    "verify_stored_rows",
    "walk_overlay",
]

PathLike = Union[str, Path]

ARTIFACT_KINDS = ("scenario", "driver", "check")

# INV-D — replace semantics differ per artifact kind, and the difference is destructive in one
# direction. Re-registering a check VERSIONS it. Re-registering a driver or a target REPLACES its
# whole configuration, clearing anything not supplied — so a driver must be READ before it is
# re-registered, or a field the overlay does not carry is silently dropped.
REPLACE_SEMANTICS = {
    "scenario": "versioned — but a same-name save must NEVER be relied on to update rows",
    "driver": "WHOLLY REPLACED — read it first; anything not supplied is cleared",
    "check": "versioned — safe to re-register",
    "target": "WHOLLY REPLACED — read it first; anything not supplied is cleared",
}

# INV-E — checks and drivers are ORGANIZATION-WIDE while scenarios are not. So a per-agent check or
# driver registered under its canonical name would overwrite another agent's, in another project,
# with no warning and no way to notice. Scenarios are project-scoped and keep the canonical name.
ORG_WIDE_KINDS = ("driver", "check")


class DoubleEncodingError(ValueError):
    """A stored row came back as a string holding encoded structure (INV-C).

    Silent, observed in production, and it defeats every structured field this feature introduces:
    the driver addresses a field that is now a JSON blob, and the judge reads a criterion that is
    now a quoted dict. The verdicts that follow are not wrong in a way anyone would notice.
    """


@dataclass
class OverlayArtifact:
    """One registerable artifact found in an overlay directory."""

    kind: str
    name: str                      # the name to register under (already namespaced)
    path: Path
    fingerprint: str = ""
    rows: Optional[list] = None    # scenarios only
    canonical_name: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ARTIFACT_KINDS:
            raise ValueError(f"unknown artifact kind {self.kind!r}; expected one of "
                             f"{list(ARTIFACT_KINDS)}")


_FRONTMATTER_KEYS = ("name", "description", "temperature", "voice", "voice_profile", "language")


def read_artifact(path: PathLike) -> dict:
    """Parse a driver or check artifact — PURE STDLIB (feature 015's keyless tooling set).

    **Why this is not `reps.common.parse_artifact`.** That function is the canonical reader and this
    one must agree with it exactly. But `reps.common` imports the Okareo SDK, and the whole premise
    of the keyless tooling set is that it runs on a bare `python3` with no third-party dependency
    available — so the canonical reader is unreachable from here by construction, not by choice.

    Duplication is the real cost, and the mitigation is a test rather than a comment:
    `tests/test_overlay_registration.py` asserts this reader agrees with `reps.common.parse_artifact`
    on **every committed artifact in the tree**, field by field. If the two ever drift, that test
    fails before a fingerprint does — and a drifted fingerprint would silently re-upload every
    artifact in an overlay, or silently reuse a stale one.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    if path.suffix.lower() == ".py":
        # A code check carries its metadata in a leading `# --- … # ---` comment block, so each
        # line must have its comment marker stripped before the `key: value` parse. Reading the
        # whole file instead silently returned an empty description for every code check — caught
        # by the agreement test, which is exactly what that test is for.
        meta = _simple_keys(_py_metadata_block(text))
        return {"name": meta.get("name") or path.stem,
                "description": meta.get("description", ""),
                "prompt_template": None, "code_contents": text, "temperature": None,
                "voice": None, "voice_profile": None, "language": None}

    front, body = _split_frontmatter(text)
    meta = _simple_keys(front)
    for header in ("## Persona Prompt Template", "## Prompt Template"):
        at = body.find(header)
        if at != -1:
            prompt = body[at + len(header):].strip()
            break
    else:
        prompt = ""
    out = {"name": meta.get("name") or path.stem,
           "description": meta.get("description", ""),
           "prompt_template": prompt, "code_contents": None}
    for key in ("voice", "voice_profile", "language"):
        out[key] = meta.get(key)
    temp = meta.get("temperature")
    try:
        out["temperature"] = float(temp) if temp not in (None, "") else None
    except (TypeError, ValueError):
        out["temperature"] = None
    return out


def _py_metadata_block(text: str) -> str:
    """The leading `# --- … # ---` block of a code check, with its comment markers removed."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "# ---":
        return ""
    out = []
    for line in lines[1:]:
        if line.strip() == "# ---":
            break
        out.append(line.lstrip("#").lstrip())
    return "\n".join(out)


def _split_frontmatter(text: str) -> tuple:
    """`(frontmatter, body)`. No frontmatter means the whole file is body."""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    return text[3:end], text[end + 4:]


def _simple_keys(block: str) -> dict:
    """`key: value` lines, with surrounding quotes stripped. Stops at the first blank-key line.

    Deliberately not a YAML parser: these headers are flat, and a partial YAML implementation that
    silently mis-reads a value is worse than one that only handles the shape that exists.
    """
    out: dict = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        if not key or " " in key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out.setdefault(key, value)
    return out


def namespaced_name(kind: str, canonical: str, agent_slug: str) -> str:
    """The name to register under (INV-E).

    An org-wide kind is suffixed with the agent slug; a project-scoped scenario is not. Getting this
    backwards is not a cosmetic error — it means one operator's tuning silently replaces another's
    judge, and the only symptom is that the other agent's verdicts change.
    """
    if kind not in ARTIFACT_KINDS:
        raise ValueError(f"unknown artifact kind {kind!r}")
    if not agent_slug:
        return canonical
    if kind in ORG_WIDE_KINDS and not canonical.endswith(f"-{agent_slug}"):
        return f"{canonical}-{agent_slug}"
    return canonical


def walk_overlay(overlay_dir: PathLike, agent_slug: str) -> list[OverlayArtifact]:
    """Every registerable artifact under one agent's overlay, in a deterministic order.

    Ordering is scenarios, then drivers, then checks — sorted within each kind. Deterministic
    because a partially completed registration has to be resumable: an operator who re-runs after a
    rate limit must see the same plan, or they cannot tell what already happened.
    """
    from reps.reuse.fingerprint import fingerprint_check, fingerprint_driver, fingerprint_scenario
    from reps.rows import load_rows

    def _fp_for(kind: str, art: dict) -> str:
        """Fingerprint one parsed artifact over the fields that change how it behaves.

        `read_artifact` returns None for an absent field, which is not the same as an empty
        string — collapsing them would make a voice driver and a text driver fingerprint
        identically.
        """
        def _v(key, default=None):
            val = art.get(key, None)
            return default if val is None else val

        if kind == "driver":
            return str(fingerprint_driver(
                _v("prompt_template", "") or "", _v("temperature"), _v("voice"),
                _v("voice_profile"), _v("language")))
        return str(fingerprint_check(
            "code" if _v("code_contents") else "model", "pass_fail",
            _v("prompt_template", "") or "", _v("code_contents", "") or "",
            _v("description", "") or ""))

    root = Path(overlay_dir)
    found: list[OverlayArtifact] = []
    if not root.is_dir():
        return found

    for path in sorted(root.rglob("scenarios/*.jsonl")):
        if path.name.endswith(".template.jsonl"):
            continue
        rows = load_rows(path)
        canonical = path.stem
        found.append(OverlayArtifact(
            kind="scenario", canonical_name=canonical,
            name=namespaced_name("scenario", canonical, agent_slug), path=path,
            fingerprint=str(fingerprint_scenario(rows)), rows=rows))

    for kind, pattern in (("driver", "drivers/*.md"), ("check", "checks/*.md"),
                          ("check", "checks/*.py")):
        for path in sorted(root.rglob(pattern)):
            try:
                art = read_artifact(path)
            except (ValueError, OSError, UnicodeDecodeError):
                continue
            canonical = str(art.get("name") or path.stem)
            found.append(OverlayArtifact(
                kind=kind, canonical_name=canonical,
                name=namespaced_name(kind, canonical, agent_slug), path=path,
                fingerprint=_fp_for(kind, art)))
    return found


def collision_entry(artifact: OverlayArtifact, existing_fingerprint: Optional[str],
                    existing_ref: Optional[str] = None) -> Optional[dict]:
    """A collision record for an artifact whose name exists with DIFFERING content (INV-B).

    Returns None when the name is free, or when the existing content matches (that is reuse, not a
    collision). Never resolves the collision: the operator chooses to version or to replace, and the
    choice is recorded, because the two have different consequences and only one of them is
    reversible.

    **A same-name save is never relied upon to update rows.** The tool contract and the
    documentation disagree about what it does, and the safe rule is identical under both readings:
    register under a new name.
    """
    if existing_fingerprint is None:
        return None
    if str(existing_fingerprint) == str(artifact.fingerprint):
        return None
    return {
        "kind": artifact.kind,
        "name": artifact.name,
        "path": str(artifact.path),
        "existing_ref": existing_ref,
        "committed_fingerprint": artifact.fingerprint,
        "existing_fingerprint": str(existing_fingerprint),
        "replace_semantics": REPLACE_SEMANTICS.get(artifact.kind, "unknown"),
        "choices": ("version", "replace"),
        "recommendation": "version",
        "why": (
            f"a {artifact.kind} named {artifact.name!r} already exists with different content. "
            f"Versioning is additive and reversible; replacing is not — and for a "
            f"{artifact.kind} the platform's replace semantics are: "
            f"{REPLACE_SEMANTICS.get(artifact.kind, 'unknown')}."),
    }


@dataclass
class RegistrationPlan:
    """What one bulk registration will do, before it does any of it."""

    operations: list[dict] = field(default_factory=list)
    collisions: list[dict] = field(default_factory=list)
    reused: list[dict] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        """True while an unresolved collision remains. Registration does not start (INV-B)."""
        return any(not c.get("resolution") for c in self.collisions)


def plan_registration(artifacts: list[OverlayArtifact],
                      existing: Optional[dict] = None,
                      resolutions: Optional[dict] = None) -> RegistrationPlan:
    """Build the registration plan (INV-A, INV-B, INV-F).

    `existing` maps a name to `{"fingerprint": ..., "ref": ...}` as discovered on the platform;
    `resolutions` maps a colliding name to `"version"` or `"replace"`, which the operator supplies
    after seeing the collisions. An unresolved collision leaves the plan **blocked** rather than
    guessing — guessing `version` would be safe and still wrong, because the operator would not
    know a second copy now exists.
    """
    existing = existing or {}
    resolutions = resolutions or {}
    plan = RegistrationPlan()

    for art in artifacts:
        found = existing.get(art.name) or {}
        found_fp = found.get("fingerprint")
        collision = collision_entry(art, found_fp, found.get("ref"))
        if collision:
            choice = resolutions.get(art.name)
            if choice in ("version", "replace"):
                collision["resolution"] = choice
            plan.collisions.append(collision)
            if not collision.get("resolution"):
                continue
            action = "version" if collision["resolution"] == "version" else "replace"
        elif found_fp is not None:
            plan.reused.append({"kind": art.kind, "name": art.name,
                                "ref": found.get("ref"), "reason": "content matches"})
            continue
        else:
            action = "create"

        op = {
            "kind": art.kind,
            "name": art.name,
            "action": action,
            "path": str(art.path),
            "fingerprint": art.fingerprint,
            "replace_semantics": REPLACE_SEMANTICS.get(art.kind, "unknown"),
            # INV-D: a driver or target is wholly replaced, so it must be READ before being
            # re-registered or a field the overlay does not carry is silently cleared.
            "read_before_write": art.kind in ("driver", "target") and action != "create",
            "verify_structure_after": art.kind == "scenario",
            "rows": len(art.rows or []) if art.kind == "scenario" else None,
        }
        plan.operations.append(op)
    return plan


def registration_summary(plan: RegistrationPlan) -> str:
    """What was created and what was reused (INV-F), plus anything still blocking."""
    created = [o for o in plan.operations if o["action"] == "create"]
    versioned = [o for o in plan.operations if o["action"] == "version"]
    replaced = [o for o in plan.operations if o["action"] == "replace"]
    lines = [
        f"{len(created)} to create, {len(versioned)} to version, {len(replaced)} to replace, "
        f"{len(plan.reused)} reused unchanged."]
    for label, ops in (("create", created), ("version", versioned), ("replace", replaced)):
        for op in ops:
            tail = f" ({op['rows']} rows)" if op.get("rows") else ""
            warn = "  ⚠ READ IT FIRST — a re-registration clears anything not supplied" \
                if op["read_before_write"] else ""
            lines.append(f"  {label:<8} {op['kind']:<9} {op['name']}{tail}{warn}")
    for item in plan.reused:
        lines.append(f"  reuse    {item['kind']:<9} {item['name']} — {item['reason']}")
    unresolved = [c for c in plan.collisions if not c.get("resolution")]
    if unresolved:
        lines.append("")
        lines.append(f"BLOCKED — {len(unresolved)} name collision(s) need your decision:")
        for c in unresolved:
            lines.append(f"  {c['kind']:<9} {c['name']}: {c['why']}")
            lines.append(f"            choose: version (recommended) | replace")
    return "\n".join(lines)


def verify_stored_rows(stored_rows: list, *, scenario: str = "") -> None:
    """Read-back verification that structure survived registration (INV-C).

    Every structured field this feature introduces depends on this. The hazard is **not** that the
    platform rejects nested structure — it accepts it. The hazard is **silent double encoding**:
    a field arrives as a *string containing* the encoded structure. Nothing errors. The driver then
    addresses a field holding a JSON blob, the judge reads a criterion that is a quoted dict, and
    every verdict after that is wrong in a way no one would notice from the scores.

    So the test is not "is the structure there" but "is it structure, or a string that merely looks
    like it".
    """
    where = f"{scenario}: " if scenario else ""
    if not isinstance(stored_rows, list) or not stored_rows:
        raise DoubleEncodingError(
            f"{where}read-back returned no rows. Registration is not confirmed — do not run.")

    for i, row in enumerate(stored_rows, start=1):
        if isinstance(row, str):
            raise DoubleEncodingError(
                f"{where}row {i} came back as a STRING, not an object. The whole row was encoded "
                f"on the way in. Re-register passing the row as structure, not as serialized text.")
        if not isinstance(row, dict):
            raise DoubleEncodingError(f"{where}row {i} came back as {type(row).__name__}")

        inp = row.get("input")
        if isinstance(inp, str):
            raise DoubleEncodingError(
                f"{where}row {i}: 'input' came back as a string"
                + (" holding encoded JSON" if _looks_encoded(inp) else "")
                + ". The caller-facing fields are a nested object; a driver token addressing "
                  "'guidance' on this row would resolve to nothing, and the caller would receive "
                  "an unresolved placeholder.")
        if not isinstance(inp, dict):
            raise DoubleEncodingError(f"{where}row {i}: 'input' must be an object, got "
                                      f"{type(inp).__name__}")

        result = row.get("result")
        if result is None or (isinstance(result, str) and not result.strip()):
            raise DoubleEncodingError(
                f"{where}row {i}: 'result' came back empty. The platform accepts a resultless row "
                f"and then silently under-serves every check declaring it needs one — this read-"
                f"back is the only place that failure is visible.")
        if isinstance(result, str) and _looks_encoded(result):
            raise DoubleEncodingError(
                f"{where}row {i}: 'result' came back as a string holding encoded JSON "
                f"({result[:60]!r}…). The judge would read a quoted dict as its pass criterion.")


def _looks_encoded(text: str) -> bool:
    """Does this string actually hold encoded structure?

    Parsed, not pattern-matched. A criterion legitimately contains braces and quotes — "MUST: Agent
    quotes {the configured price}" is ordinary prose — so a regexp would reject real criteria and
    the check would be turned off.
    """
    stripped = (text or "").strip()
    if not stripped or stripped[0] not in "[{":
        return False
    try:
        return isinstance(json.loads(stripped), (dict, list))
    except ValueError:
        return False


def deletion_warning(scenario_name: str, run_count: Optional[int] = None,
                     resolved_name: Optional[str] = None) -> str:
    """The blast-radius warning shown before any scenario deletion (INV-G, FR-061).

    Two facts, stated together because either one alone sounds survivable: deleting a scenario
    deletes its runs, **and** calibration requires the run to still exist. Together they mean
    replacing a scenario destroys the substrate every later calibration and re-score of it depends
    on — and `calibrate_check` is the only free way to check a judge.

    `resolved_name` exists because the platform's own delete-preview may report a **null** name.
    Echoing that back gives the operator a confirmation prompt about deleting "None".
    """
    name = resolved_name or scenario_name or "(name could not be resolved)"
    runs = (f"{run_count} run(s)" if isinstance(run_count, int) and run_count >= 0
            else "every run")
    return (
        f"DESTRUCTIVE — deleting scenario {name!r} also deletes {runs} made against it.\n"
        f"\n"
        f"Those runs are the substrate for calibration and re-scoring: calibration requires the run "
        f"to still exist, so deleting this scenario destroys the only free way to check whether its "
        f"judges agree with a human reading — and the agreement figure cannot be inherited from "
        f"another agent.\n"
        f"\n"
        f"Prefer registering under a NEW name. If you are replacing this scenario because its rows "
        f"changed, note that a same-name save must not be relied on to update rows in any case.\n"
        f"\n"
        f"Confirm the name above is the one you mean: a delete preview may report a null name, and "
        f"a prompt asking you to confirm deleting 'None' is not a confirmation.")

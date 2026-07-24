"""
Discovery adapters (feature 003) — the ONLY reuse module that talks to the platform.

Given a canonical/tuned name, return a PlatformArtifactRef describing what (if anything)
already exists, so decision.decide() can choose reuse vs upload. Two adapters:

  - SDK path (run_suite.py): get_driver_by_name / get_all_checks; scenarios run in a
    documented DEGRADED mode (the SDK exposes no scenario listing/tagging), so scenario
    discovery returns an unconfirmed ref → decision falls toward upload (FR-010, never stale).
  - MCP path (reps-run skill): the skill performs list_scenarios / list_checks / list_drivers
    + get_driver and builds refs via `ref_from_listing` (pure, below).

okareo is imported lazily inside the SDK functions so this module stays importable keyless.
"""
from __future__ import annotations

from typing import Optional

from reps.reuse.decision import BuildingBlock, PlatformArtifactRef
from reps.reuse.fingerprint import fingerprint_driver
from reps.reuse.naming import agent_from_tags, tuned_name, version_from_tags


# --- Pure helper used by BOTH paths (unit-testable) --------------------------------
def ref_from_listing(name: str, listing: Optional[dict]) -> PlatformArtifactRef:
    """Build a ref from a discovery listing dict `{name, id?, tags?}` (None → absent).

    `listing` is whatever the caller found for `name` via list_scenarios/list_checks
    (MCP) — it carries the `fp:`/`ver:` tags the decision needs. A missing listing is an
    absent, confirmed ref (present=False) → the caller must upload.
    """
    if not listing:
        return PlatformArtifactRef(name=name, present=False, confirmed=True)
    tags = tuple(listing.get("tags") or ())
    return PlatformArtifactRef(
        name=name, present=True, confirmed=True,
        id=listing.get("id"), tags=tags, version=version_from_tags(list(tags)))


# --- Agent scoping (feature 006) ----------------------------------------------------
def discovery_name(block: BuildingBlock) -> str:
    """The platform name to look up for `block`: its tuned name when agent-scoped, else canonical.

    Because a tuned name embeds the agent slug (`<canonical>-tuned-<slug>`), looking up by this
    name is itself an agent-isolation boundary on name-keyed discovery (drivers, checks): agent A
    can never find agent B's block. Mirrors `decision._next_target_name`.
    """
    base = block.base_name()
    if block.tuned:
        return tuned_name(base, block.agent_slug or "agent")
    return base


def ref_from_listing_scoped(name: str, listing: Optional[dict],
                            agent_slug: Optional[str] = None) -> PlatformArtifactRef:
    """`ref_from_listing`, but a listing owned by a DIFFERENT agent is treated as absent.

    Agent isolation (feature 006 INV-T3; decision.decide INV-4): one agent's tuned material MUST
    NEVER be reused for another agent. Returning an absent ref makes `decide()` upload a fresh
    tuned block for *this* agent instead of reusing someone else's.

    Used by tag-aware discovery (the MCP path, where list_scenarios/list_checks return tags).
    """
    if listing:
        owner = agent_from_tags(list(listing.get("tags") or ()))
        if owner and owner != agent_slug:
            return PlatformArtifactRef(name=name, present=False, confirmed=True)
    return ref_from_listing(name, listing)


def unconfirmed_ref(name: str) -> PlatformArtifactRef:
    """A present-but-unverifiable ref → decision returns upload-new (platform-drift).

    Used for SDK-path scenarios (no listing available) so reuse never trusts unconfirmed
    state (FR-005/FR-013).
    """
    return PlatformArtifactRef(name=name, present=True, confirmed=False)


# --- SDK-path adapters (lazy okareo) -----------------------------------------------
def sdk_find_driver(okareo, name: str) -> PlatformArtifactRef:
    """Look up a driver by name; recompute its persona fingerprint for drift detection.

    Drivers carry no tags, so the fingerprint is derived from the fetched persona/config
    (FR-003a) and placed on the ref for decision.decide() to compare.
    """
    try:
        drv = okareo.get_driver_by_name(name)
    except Exception:  # not found / transient → treat as absent (fail toward upload)
        return PlatformArtifactRef(name=name, present=False, confirmed=True)
    if drv is None:
        return PlatformArtifactRef(name=name, present=False, confirmed=True)
    fp = fingerprint_driver(
        prompt_template=getattr(drv, "prompt_template", "") or "",
        temperature=getattr(drv, "temperature", None),
        voice=getattr(drv, "voice", None),
        voice_profile=getattr(drv, "voice_profile", None),
        language=getattr(drv, "language", None),
    )
    return PlatformArtifactRef(name=name, present=True, confirmed=True,
                               id=str(getattr(drv, "id", "") or "") or None,
                               fingerprint=fp.value)


def sdk_find_check(okareo, name: str) -> PlatformArtifactRef:
    """Look up a check by name via get_all_checks (SDK has no tags on the listing).

    The SDK check listing does not expose our `fp:` tag, so a found check is returned as
    unconfirmed for fingerprint purposes → the SDK path re-saves (new version) rather than
    risk reusing stale content. Absence is confirmed.
    """
    try:
        checks = okareo.get_all_checks()
    except Exception:
        return PlatformArtifactRef(name=name, present=False, confirmed=True)
    names = {getattr(c, "name", None) for c in (checks or [])}
    if name in names:
        return unconfirmed_ref(name)
    return PlatformArtifactRef(name=name, present=False, confirmed=True)


def sdk_find_scenario(okareo, name: str) -> PlatformArtifactRef:
    """SDK degraded mode: no scenario listing/tagging → always unconfirmed present.

    Decision therefore falls toward upload for scenarios on the SDK path. This is the
    documented FR-010 asymmetry; correctness (never stale) is preserved.
    """
    return unconfirmed_ref(name)

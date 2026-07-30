"""
Canonical + tuned naming and the tag vocabulary (feature 003).

The functions below are the authoritative naming/tagging rules.
Both execution paths MUST build identical names/tags for identical committed state — this
module is that single source, and is keyless/pure so it can be unit-tested and called from
the MCP path and the SDK runner alike.

  Standard (agent-agnostic):  <PillarLetter>-<bank>[-<driver>]      e.g. R-core-assertive-caller
  Tuned (agent-specific):     <canonical>-tuned-<agent_slug>[-vN]   drivers use name only (no tags)
"""
from __future__ import annotations

from reps.reuse.fingerprint import ContentFingerprint

# Redundant pillar-word prefixes to strip from bank stems / driver names so the pillar
# letter is not repeated in the name (FR-004a). Files are also renamed (FR-004b), but this
# keeps naming correct for any residual prefix during/after the transition.
_PILLAR_PREFIXES = {
    "R": ("reasoning",),
    "E": ("execution",),
    "P": ("performance", "perf"),
    "S": ("security",),
}


def strip_redundant_prefix(segment: str, pillar_letter: str) -> str:
    """Drop a single leading `<pillarword>-` from a bank stem or driver name."""
    for pre in _PILLAR_PREFIXES.get(pillar_letter.upper(), ()):
        if segment.lower().startswith(pre + "-"):
            return segment[len(pre) + 1:]
    return segment


def canonical_name(pillar_letter: str, bank: str, driver: str | None = None) -> str:
    """`<PillarLetter>-<bank>[-<driver>]`, de-prefixing bank/driver defensively."""
    letter = pillar_letter.upper()
    bank = strip_redundant_prefix(bank, letter)
    parts = [letter, bank]
    if driver:
        parts.append(strip_redundant_prefix(driver, letter))
    return "-".join(parts)


def tuned_name(canonical: str, agent_slug: str, version: int | None = None) -> str:
    """`<canonical>-tuned-<agent_slug>[-vN]` (N appended only when > 1)."""
    name = f"{canonical}-tuned-{agent_slug}"
    if version and version > 1:
        name = f"{name}-v{version}"
    return name


# --- Tag vocabulary (scenarios & checks only; drivers accept no tags) --------------

REPS_TAG = "reps"


def _pillar_tag(pillar_letter: str) -> str:
    return f"pillar:{pillar_letter.upper()}"


def fp_tag(fp: ContentFingerprint | str) -> str:
    return f"fp:{fp.value if isinstance(fp, ContentFingerprint) else fp}"


def standard_tags(pillar_letter: str, fp: ContentFingerprint | str) -> list[str]:
    """Tags for a standard (agent-agnostic) scenario/check."""
    return [REPS_TAG, _pillar_tag(pillar_letter), "standard", fp_tag(fp)]


def tuned_tags(pillar_letter: str, fp: ContentFingerprint | str, agent_slug: str,
               version: int) -> list[str]:
    """Tags for a tuned (agent-specific) scenario/check."""
    return [REPS_TAG, _pillar_tag(pillar_letter), "tuned",
            f"agent:{agent_slug}", f"ver:{version}", fp_tag(fp)]


def fp_from_tags(tags: list[str] | None) -> str | None:
    """Read the `fp:` value from a platform artifact's tags (None if absent)."""
    for t in tags or []:
        if t.startswith("fp:"):
            return t[len("fp:"):]
    return None


def version_from_tags(tags: list[str] | None) -> int | None:
    """Read the `ver:` integer from a tuned artifact's tags (None if absent/malformed)."""
    for t in tags or []:
        if t.startswith("ver:"):
            try:
                return int(t[len("ver:"):])
            except ValueError:
                return None
    return None


def agent_from_tags(tags: list[str] | None) -> str | None:
    """Read the `agent:` slug from a tuned artifact's tags (None if absent)."""
    for t in tags or []:
        if t.startswith("agent:"):
            return t[len("agent:"):]
    return None

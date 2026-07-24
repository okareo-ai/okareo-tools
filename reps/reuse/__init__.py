"""
Artifact upload reuse & supersession (feature 003).

A reuse-or-upload decision layer in front of the building-block uploads (drivers,
scenario slices, checks). The Okareo platform is the record of what already exists;
the committed reps/ files stay the content source of truth. Standard blocks reuse by
canonical name; tuned blocks are keyed to the agent by a `-tuned` name (+ tags for
scenarios/checks; name only for drivers, which accept no tags).

Design docs: specs/003-artifact-upload-reuse/ (plan.md, data-model.md, contracts/).

`fingerprint`, `naming`, and `decision` are DELIBERATELY okareo-free pure modules
(mirroring reps.rows / reps.slug) so they are unit-testable without SDK credentials
and usable from both the keyless MCP path and the SDK runner. Only `platform` and
`orchestrate` touch the platform, and they import okareo lazily.
"""
from __future__ import annotations

from reps.reuse.decision import (
    BuildingBlock,
    PlatformArtifactRef,
    SupersessionDecision,
    decide,
)
from reps.reuse.fingerprint import (
    ContentFingerprint,
    fingerprint_check,
    fingerprint_driver,
    fingerprint_scenario,
)
from reps.reuse.naming import (
    canonical_name,
    fp_from_tags,
    standard_tags,
    strip_redundant_prefix,
    tuned_name,
    tuned_tags,
    version_from_tags,
)

__all__ = [
    "BuildingBlock",
    "PlatformArtifactRef",
    "SupersessionDecision",
    "decide",
    "ContentFingerprint",
    "fingerprint_check",
    "fingerprint_driver",
    "fingerprint_scenario",
    "canonical_name",
    "tuned_name",
    "standard_tags",
    "tuned_tags",
    "fp_from_tags",
    "version_from_tags",
    "strip_redundant_prefix",
]

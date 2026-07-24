"""
The pure reuse decision core (feature 003).

Contract: specs/003-artifact-upload-reuse/contracts/reuse-decision.md.
`decide()` is a pure function — same inputs, same output, no clock, no I/O (INV-6). The
caller does discovery (reps.reuse.platform) and uploading; this module only decides.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from reps.reuse.fingerprint import ContentFingerprint
from reps.reuse.naming import canonical_name, fp_from_tags, tuned_name

BlockType = Literal["driver", "scenario", "check"]
Action = Literal["reuse", "upload-new"]
Reason = Literal["first-upload", "content-changed", "tuned", "platform-drift", "unchanged"]


@dataclass(frozen=True)
class BuildingBlock:
    """The unit a reuse decision is made about, derived from a committed file."""

    block_type: BlockType
    pillar_letter: str
    bank: str = ""                       # scenario/driver segment (e.g. "core")
    driver: Optional[str] = None         # driver segment for scenario slices / driver blocks
    check_name: Optional[str] = None     # canonical check name (checks have no bank/driver)
    source_path: Optional[str] = None
    tuned: bool = False
    agent_slug: Optional[str] = None

    def base_name(self) -> str:
        """The canonical (standard) name this block reuses/publishes under."""
        if self.block_type == "check":
            return self.check_name or ""
        if self.block_type == "driver":
            return canonical_name(self.pillar_letter, self.driver or self.bank)
        return canonical_name(self.pillar_letter, self.bank, self.driver)


@dataclass(frozen=True)
class PlatformArtifactRef:
    """What discovery returns about an existing on-platform block."""

    name: str
    present: bool
    confirmed: bool = True
    id: Optional[str] = None
    tags: tuple[str, ...] = ()
    version: Optional[int] = None
    # For a driver (no tags), discovery supplies the recomputed persona fingerprint here.
    fingerprint: Optional[str] = None

    def platform_fp(self) -> Optional[str]:
        """The fingerprint carried on the platform: `fp:` tag, or driver persona hash."""
        return fp_from_tags(list(self.tags)) or self.fingerprint


@dataclass(frozen=True)
class SupersessionDecision:
    """The per-block verdict for a run."""

    block: BuildingBlock
    action: Action
    reason: Reason
    target_name: str
    fingerprint: ContentFingerprint

    @property
    def reused(self) -> bool:
        return self.action == "reuse"


def _next_target_name(block: BuildingBlock, existing: Optional[PlatformArtifactRef]) -> str:
    """Name to publish an upload under (canonical, or the next tuned version)."""
    base = block.base_name()
    if not block.tuned:
        return base
    # Tuned upload: bump to the next version when a prior tuned version exists.
    prev = existing.version if (existing and existing.present and existing.version) else None
    version = (prev + 1) if prev else 1
    return tuned_name(base, block.agent_slug or "agent", version)


def decide(block: BuildingBlock, committed_fp: ContentFingerprint,
           existing: Optional[PlatformArtifactRef]) -> SupersessionDecision:
    """Return the reuse-or-upload verdict for one block (see contract decision table).

    Invariants (tested): fail-toward-upload on None/unconfirmed (INV-1); reuse only on a
    confirmed fingerprint match (INV-2); any mismatch → upload-new (INV-3); determinism (INV-6).
    Agent isolation (INV-4) is enforced by the caller passing `existing=None` when the only
    on-platform match belongs to a different agent.
    """
    def upload(reason: Reason) -> SupersessionDecision:
        return SupersessionDecision(block, "upload-new", reason,
                                    _next_target_name(block, existing), committed_fp)

    # No confirmed existence → always upload (INV-1 / FR-005 / FR-013).
    if existing is None or not existing.present:
        return upload("first-upload")
    if not existing.confirmed:
        return upload("platform-drift")

    platform_fp = existing.platform_fp()
    if platform_fp is not None and platform_fp == committed_fp.value:
        return SupersessionDecision(block, "reuse", "unchanged", existing.name, committed_fp)

    # Present + confirmed but the fingerprint differs (or is unreadable) → supersede.
    return upload("tuned" if block.tuned else "content-changed")

"""
Reuse orchestration + run disposition (feature 003, T021/T030).

The glue both paths use: given a committed fingerprint and a discovered
PlatformArtifactRef, call the pure `decide()` and record the verdict into a
RunDisposition so the report can show reused-vs-uploaded per block (FR-012).

Keyless — imports only the pure reuse modules; the caller owns discovery/upload I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from reps.reuse.decision import (
    BuildingBlock,
    PlatformArtifactRef,
    SupersessionDecision,
    decide,
)
from reps.reuse.fingerprint import ContentFingerprint


@dataclass
class RunDisposition:
    """Per-run record of what was reused vs uploaded (data-model.md §RunDisposition)."""

    uploaded: list[SupersessionDecision] = field(default_factory=list)
    reused: list[SupersessionDecision] = field(default_factory=list)
    coverage_risks: list[dict] = field(default_factory=list)

    def record(self, decision: SupersessionDecision) -> SupersessionDecision:
        (self.reused if decision.reused else self.uploaded).append(decision)
        # An upload forced by unverifiable existence is a surfaced coverage risk (FR-013).
        if decision.reason == "platform-drift":
            self.coverage_risks.append({
                "name": decision.target_name,
                "block_type": decision.block.block_type,
                "reason": "platform-drift — existing artifact could not be confirmed; re-uploaded",
            })
        return decision

    @property
    def counts(self) -> dict:
        return {"uploaded": len(self.uploaded), "reused": len(self.reused)}

    def summary_line(self) -> str:
        c = self.counts
        risk = f", {len(self.coverage_risks)} coverage-risk" if self.coverage_risks else ""
        return f"reuse: {c['reused']} reused, {c['uploaded']} uploaded{risk}"

    def to_record(self) -> dict:
        """Serializable shape folded into the findings record for the report."""
        def _row(d: SupersessionDecision) -> dict:
            return {"name": d.target_name, "block_type": d.block.block_type,
                    "action": d.action, "reason": d.reason}
        return {
            "counts": self.counts,
            "uploaded": [_row(d) for d in self.uploaded],
            "reused": [_row(d) for d in self.reused],
            "coverage_risks": list(self.coverage_risks),
        }


def decide_and_record(disposition: RunDisposition, block: BuildingBlock,
                      committed_fp: ContentFingerprint,
                      existing: Optional[PlatformArtifactRef]) -> SupersessionDecision:
    """Decide reuse-vs-upload for one block and record it. The caller then acts on
    `decision.action` (reuse the existing ref, or upload under `decision.target_name`)."""
    return disposition.record(decide(block, committed_fp, existing))

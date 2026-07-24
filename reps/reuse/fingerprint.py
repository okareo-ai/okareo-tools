"""
Content fingerprints for building blocks (feature 003, data-model.md §ContentFingerprint).

A fingerprint is a short, stable hash over ONLY the evaluation-relevant fields of a
committed artifact, so cosmetic edits (comments, unrelated metadata) do not churn an
upload while any change that affects what actually runs supersedes it (FR-002, FR-009).

Keyless pure module — no okareo import (mirrors reps.rows).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

ALGO = "sha256/8"  # sha256, first 8 hex chars — legible inside an `fp:` tag


@dataclass(frozen=True)
class ContentFingerprint:
    """A stable identifier over a block's evaluation-relevant content."""

    value: str
    covered_fields: tuple[str, ...]
    algo: str = ALGO

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.value


def _hash(parts: object) -> str:
    """Canonical (sort-keyed) JSON of `parts` → first 8 hex of sha256."""
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:8]


def fingerprint_scenario(rows: list[dict]) -> ContentFingerprint:
    """Fingerprint the ordered [{input, result}] a scenario slice uploads.

    Only `input` and `result` are covered — the fields the platform actually evaluates.
    Row order is significant (it is preserved on upload), so we do NOT sort rows.
    """
    covered = ({"input": r.get("input"), "result": r.get("result")} for r in rows)
    return ContentFingerprint(value=_hash(list(covered)),
                              covered_fields=("input", "result"))


def fingerprint_check(check_type: str, output_type: str, prompt_template: str | None,
                      code_contents: str | None, description: str = "") -> ContentFingerprint:
    """Fingerprint a check over the fields that change how it judges."""
    parts = {
        "check_type": check_type,
        "output_type": output_type,
        "prompt_template": prompt_template or "",
        "code_contents": code_contents or "",
        "description": description or "",
    }
    return ContentFingerprint(value=_hash(parts), covered_fields=tuple(sorted(parts)))


def fingerprint_driver(prompt_template: str, temperature: float | None = None,
                       voice: str | None = None, voice_profile: str | None = None,
                       language: str | None = None) -> ContentFingerprint:
    """Fingerprint a driver persona over the fields that change its behavior.

    Drivers carry no platform tag (Okareo drivers accept none), so this fingerprint is
    recomputed from the persona fetched by name at reuse time (FR-003a).
    """
    parts = {
        "prompt_template": prompt_template or "",
        "temperature": temperature,
        "voice": voice,
        "voice_profile": voice_profile,
        "language": language,
    }
    return ContentFingerprint(value=_hash(parts), covered_fields=tuple(sorted(parts)))

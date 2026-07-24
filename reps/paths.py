"""Per-agent artifact paths and baseline/overlay resolution (feature 006).

Constitution v1.1.0, "Artifact Scopes: Baseline vs. Agent-Scoped Overlay":

- **Baseline** artifacts are agent-agnostic and committed under `reps/<pillar>/...`. They are
  READ-ONLY for any tuning flow — tuning MUST NOT create, modify, or delete one.
- **Agent-scoped overlays** are agent-specific, gitignored, and live under
  `results/<agent_slug>/` (the per-agent directory that also holds that agent's findings and
  report). They are file-first but intentionally uncommitted.

This module is the single source of truth for *where* those live and *which one wins*, so the
runner (`reps/run_suite.py`) and the report layer (`reps/report/*`) can never disagree.

Keyless and dependency-light (no `okareo` import), like `reps/slug.py`, so it is importable from
both paths and unit-testable without credentials.

Contracts: specs/006-agent-scoped-tuning/contracts/{per-agent-layout,artifact-override-resolution,
profile-resolution}.md
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional, Union

from reps.slug import agent_slug

# Repo root: reps/paths.py -> reps -> <repo root>
PROJECT_ROOT = Path(__file__).resolve().parent.parent

RESULTS_DIRNAME = "results"
TUNED_DIRNAME = "tuned"
PROFILE_DIRNAME = "profile"
PROFILE_FILENAME = "agent-profile.yaml"

# Feature 010 (reps-explore): profile lifecycle status. A profile written by exploration is a
# `draft` until reps-profile applies it; a profile with NO status field is `applied` (every
# pre-010 profile was written by the interview flow, which is by definition applied).
PROFILE_STATUS_DRAFT = "draft"
PROFILE_STATUS_APPLIED = "applied"

# Feature 010: the committed exploration baseline (a setup aid, NOT a pillar — never part of
# pillar discovery, eval configs, or coverage). contracts/exploration-artifacts.md INV-E1/E2.
EXPLORE_DIRNAME = "explore"

# Glob patterns per artifact subdir, matching the runner's discovery.
SUBDIR_PATTERNS: dict[str, tuple[str, ...]] = {
    "scenarios": ("*.jsonl",),
    "drivers": ("*.md",),
    "checks": ("*.md", "*.py"),
}

PathLike = Union[str, Path]


def _root(project_root: Optional[PathLike] = None) -> Path:
    """Anchor for all path construction (overridable so tests can use a temp tree)."""
    return Path(project_root) if project_root is not None else PROJECT_ROOT


def _slug(target_or_slug: str) -> str:
    """Accept a raw target name or an already-normalized slug (agent_slug is idempotent)."""
    return agent_slug(target_or_slug)


def _pillar_name(pillar_dir: PathLike) -> str:
    """`reps/R-reasoning` (Path) or `"R-reasoning"` (str) -> `"R-reasoning"`."""
    return Path(pillar_dir).name


# -----------------------------------------------------------------------------
# Per-agent layout (contracts/per-agent-layout.md)
# -----------------------------------------------------------------------------
def agent_dir(target_or_slug: str, project_root: Optional[PathLike] = None) -> Path:
    """`results/<agent_slug>/` — the gitignored per-agent directory (INV-L2)."""
    return _root(project_root) / RESULTS_DIRNAME / _slug(target_or_slug)


def tuned_dir(target_or_slug: str, pillar_dir: PathLike,
              project_root: Optional[PathLike] = None) -> Path:
    """`results/<agent_slug>/tuned/<pillar-dir>/` — root of this agent's overlay for one pillar."""
    return agent_dir(target_or_slug, project_root) / TUNED_DIRNAME / _pillar_name(pillar_dir)


def agent_profile_path(target_or_slug: str, project_root: Optional[PathLike] = None) -> Path:
    """`results/<agent_slug>/profile/agent-profile.yaml` — the agent's (overlay) profile."""
    return agent_dir(target_or_slug, project_root) / PROFILE_DIRNAME / PROFILE_FILENAME


def baseline_profile_path(project_root: Optional[PathLike] = None) -> Path:
    """`reps/profile/agent-profile.yaml` — the committed baseline profile (usually absent)."""
    return _root(project_root) / "reps" / PROFILE_DIRNAME / PROFILE_FILENAME


def is_overlay_path(path: PathLike, project_root: Optional[PathLike] = None) -> bool:
    """True when `path` lives under the gitignored results/ tree (i.e. is an overlay artifact)."""
    try:
        Path(path).resolve().relative_to((_root(project_root) / RESULTS_DIRNAME).resolve())
        return True
    except ValueError:
        return False


# -----------------------------------------------------------------------------
# Artifact override resolution (contracts/artifact-override-resolution.md)
# -----------------------------------------------------------------------------
def resolve_artifact(pillar_dir: PathLike, subdir: str, name: str,
                     target_or_slug: Optional[str],
                     project_root: Optional[PathLike] = None) -> tuple[Path, bool]:
    """Resolve one artifact by name: overlay preferred, baseline fallback.

    Returns `(path_to_load, is_tuned)`. `is_tuned` is True iff the overlay provided the file —
    that flag is what drives tuned publication (contracts/tuned-publication.md, INV-T1/T2).

    INV-R1 overlay wins; INV-R2 baseline fallback; INV-R3 overlay-only names resolve as tuned.
    `target_or_slug=None` (no agent resolved) ⇒ pure baseline, exactly as before feature 006.
    """
    if target_or_slug:
        overlay = tuned_dir(target_or_slug, pillar_dir, project_root) / subdir / name
        if overlay.exists():
            return overlay, True
    return Path(pillar_dir) / subdir / name, False


def discover_names(pillar_dir: PathLike, subdir: str, target_or_slug: Optional[str],
                   project_root: Optional[PathLike] = None,
                   patterns: Optional[Iterable[str]] = None) -> list[str]:
    """Artifact file names to load for one pillar/subdir: **union** of baseline and overlay.

    Union, never replacement (INV-R4): tuning one bank MUST NOT silently drop the baseline banks
    an operator did not override — that would be an unannounced coverage loss (Constitution I).
    `target_or_slug=None` ⇒ baseline names only.
    """
    pats = tuple(patterns) if patterns is not None else SUBDIR_PATTERNS.get(subdir, ("*",))
    roots = [Path(pillar_dir) / subdir]
    if target_or_slug:
        roots.append(tuned_dir(target_or_slug, pillar_dir, project_root) / subdir)
    names: set[str] = set()
    for base in roots:
        if base.is_dir():
            for pat in pats:
                names.update(p.name for p in base.glob(pat))
    return sorted(names)


# -----------------------------------------------------------------------------
# Profile resolution (contracts/profile-resolution.md)
# -----------------------------------------------------------------------------
def resolve_profile(target_or_slug: Optional[str],
                    project_root: Optional[PathLike] = None) -> Optional[Path]:
    """Agent profile → baseline profile → None (INV-P1/P2/P4).

    `None` means "no profile anywhere" ⇒ the report marks the pillar **untuned** (FR-010), which
    is exactly today's behavior for an unprofiled agent. A `target_or_slug` of None (no agent
    resolved) skips the overlay and considers only the baseline.
    """
    if target_or_slug:
        p = agent_profile_path(target_or_slug, project_root)
        if p.exists():
            return p
    c = baseline_profile_path(project_root)
    return c if c.exists() else None


def explore_dir(project_root: Optional[PathLike] = None) -> Path:
    """`reps/explore/` — the committed exploration baseline (feature 010, not a pillar)."""
    return _root(project_root) / "reps" / EXPLORE_DIRNAME


def explore_driver_path(project_root: Optional[PathLike] = None) -> Path:
    """`reps/explore/drivers/curious-onboarder.md` — the one benign-discovery persona."""
    return explore_dir(project_root) / "drivers" / "curious-onboarder.md"


def explore_scenario_path(project_root: Optional[PathLike] = None) -> Path:
    """`reps/explore/scenarios/discovery.jsonl` — the predefined discovery seed bank."""
    return explore_dir(project_root) / "scenarios" / "discovery.jsonl"


def exploration_summary_path(target_or_slug: str,
                             project_root: Optional[PathLike] = None) -> Path:
    """`results/<agent_slug>/profile/exploration-summary.md` — the human-readable summary."""
    return agent_dir(target_or_slug, project_root) / PROFILE_DIRNAME / "exploration-summary.md"


_MODALITY_LINE = re.compile(r'^modality:\s*["\']?(voice|text)["\']?\s*(?:#.*)?$', re.IGNORECASE)


def read_profile_modality(target_or_slug: Optional[str],
                          project_root: Optional[PathLike] = None) -> Optional[str]:
    """Read the top-level `modality:` (voice|text) from the resolved agent profile, or None.

    Feature 008 (contracts/modality-selection.md): the profile is the operator's declared modality
    truth and the primary source for auto-orienting a run. Dependency-light — scans for the one
    top-level `modality:` line rather than importing a YAML parser, matching this module's keyless,
    no-heavy-deps stance. Returns None when no profile exists or it declares no modality.
    """
    p = resolve_profile(target_or_slug, project_root)
    if not p:
        return None
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            m = _MODALITY_LINE.match(line.strip())
            if m:
                return m.group(1).lower()
    except OSError:
        return None
    return None


_STATUS_LINE = re.compile(r'^status:\s*["\']?(draft|applied)["\']?\s*(?:#.*)?$', re.IGNORECASE)


def read_profile_status(target_or_slug: Optional[str],
                        project_root: Optional[PathLike] = None) -> Optional[str]:
    """Read the profile lifecycle `status:` (draft|applied) from the resolved agent profile.

    Feature 010 (contracts/draft-profile.md INV-D2/D3): `draft` = written by reps-explore and not
    yet applied by reps-profile; **absent field ⇒ `applied`** (pre-010 back-compat — the interview
    flow's output is applied by definition). Returns None only when no profile resolves at all.

    Dependency-light line-scan like `read_profile_modality` — the pattern anchors on the two legal
    values, so nested `status:` keys inside artifact-metadata examples can't false-match unless
    they use these exact values at the start of a line, which the profile shape forbids.
    """
    p = resolve_profile(target_or_slug, project_root)
    if not p:
        return None
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            m = _STATUS_LINE.match(line.strip())
            if m:
                return m.group(1).lower()
    except OSError:
        return None
    return PROFILE_STATUS_APPLIED

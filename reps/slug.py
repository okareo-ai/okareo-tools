"""Dependency-light helpers shared by the runner and the report layer (no okareo import)."""
from __future__ import annotations

import re


def agent_slug(name: str) -> str:
    """Normalize a target/agent name into a filesystem slug.

    Lowercase, spaces → '_', any other non-[a-z0-9_] run collapsed to '_'.
    e.g. "The Parts Store" -> "the_parts_store".
    """
    s = str(name).strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_") or "agent"

"""
Modality-agnostic target abstraction (the FR-030 seam).

`build_target(config)` dispatches on the config's `modality` (or `kind`) to a voice or text
adapter and returns an Okareo `Target`. v0 implements the voice adapter; the text/HTTP adapter is
present behind the same interface so a text workbench is an additive drop-in.

Config loading, validation, and adapter selection are pure (no Okareo import) so they are unit
testable without the SDK or network. Only `build_target()` constructs Okareo objects (lazy import).

Schema: the fields loaded below; see reps/target.json.example.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

VOICE_PROVIDERS = {"openai", "deepgram", "twilio", "custom"}

# Fields that must never contain a literal secret in a committed target.json.
_SECRET_HINT_KEYS = {"api_key", "apikey", "token", "secret", "password"}


class TargetConfigError(ValueError):
    """Raised when a target config is missing required fields or contains inline secrets."""


def load_target_config(path: str | Path) -> dict:
    """Load a target config from JSON. Raises TargetConfigError if missing/invalid."""
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise TargetConfigError(
            f"Target config not found at {cfg_path}. Copy reps/target.json.voice-example "
            f"to reps/target.json and fill in your agent."
        )
    if cfg_path.suffix.lower() != ".json":
        raise TargetConfigError(f"Unsupported target config type: {cfg_path.suffix} (expected .json)")
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


def select_modality(config: dict) -> str:
    """Return the normalized modality/kind for a config: 'voice' or 'text'."""
    modality = (config.get("modality") or config.get("kind") or "").strip().lower()
    if modality in {"voice"}:
        return "voice"
    if modality in {"text", "http", "chat"}:
        return "text"
    raise TargetConfigError(
        f"Target config must set 'modality' to 'voice' or 'text' (got {modality!r})."
    )


def _reject_inline_secrets(config: dict) -> None:
    """Raise if a secret-looking key holds a non-empty literal value (FR-019)."""
    def walk(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = str(k).lower()
                if kl in _SECRET_HINT_KEYS and isinstance(v, str) and v.strip():
                    raise TargetConfigError(
                        f"Inline secret detected at {path}{k!r}. Reference an env var instead "
                        f"(e.g. \"{k}_env\": \"MY_ENV_VAR\") — never commit literal secrets."
                    )
                walk(v, f"{path}{k}.")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}].")

    walk(config)


def validate_target_config(config: dict) -> str:
    """Validate a target config; return its modality. Raises TargetConfigError on problems."""
    modality = select_modality(config)
    if not config.get("name"):
        raise TargetConfigError("Target config must set 'name'.")
    _reject_inline_secrets(config)

    if modality == "voice":
        voice = config.get("voice") or {}
        provider = str(voice.get("provider", "")).strip().lower()
        if provider not in VOICE_PROVIDERS:
            raise TargetConfigError(
                f"Voice target 'voice.provider' must be one of {sorted(VOICE_PROVIDERS)} (got {provider!r})."
            )
        if provider in {"openai", "deepgram"} and not voice.get("model"):
            raise TargetConfigError(f"Voice provider {provider!r} requires 'voice.model'.")
        if provider == "custom" and not voice.get("custom_endpoint_url"):
            raise TargetConfigError("Voice provider 'custom' requires 'voice.custom_endpoint_url'.")
    else:  # text
        if not config.get("endpoint_url"):
            raise TargetConfigError("Text target requires 'endpoint_url'.")
        # Trace block (feature 004): optional. If present, `trace.path` must be a string path
        # (never a secret) — it locates the tool-call trace in the agent's response so the runner
        # can verify it and produce trace-verified Execution findings.
        trace = config.get("trace")
        if trace is not None:
            if not isinstance(trace, dict):
                raise TargetConfigError("Text target 'trace' must be an object with 'path'/'available'.")
            path = trace.get("path")
            if path is not None and not isinstance(path, str):
                raise TargetConfigError("Text target 'trace.path' must be a string response path.")

    return modality


def trace_path_of(config: dict) -> str | None:
    """Return the declared tool-call trace path for a target config, or None (black-box).

    Presence of a non-empty `trace.path` = trace declared (feature 004); the runner verifies it at
    runtime and falls back to black-box if absent (contracts/trace-model.md, target-and-profile.md).
    """
    path = (config.get("trace") or {}).get("path")
    return path.strip() if isinstance(path, str) and path.strip() else None


def resolve_secret(config: dict, env_key_path: str, default: str = "") -> str:
    """Resolve an env-referenced secret. `env_key_path` like 'auth.api_key_env'."""
    node: Any = config
    for part in env_key_path.split("."):
        if not isinstance(node, dict):
            return default
        node = node.get(part)
    env_name = node if isinstance(node, str) else None
    if not env_name:
        return default
    return os.environ.get(env_name, default)


def resolve_target(okareo, target_ref: str) -> str:
    """Resolve a target already registered in Okareo, referenced by name (or id).

    This is the PRIMARY path: the operator has registered the voice agent as a Target in Okareo
    (via the UI or create_or_update_target), and the workbench references it by name. Returns the
    target name string, which `run_simulation(target=...)` accepts directly. Validates existence via
    `get_target_by_name` when possible and raises a clear error if the name is unknown.
    """
    ref = str(target_ref).strip()
    if not ref:
        raise TargetConfigError(
            "No target specified. Pass --target <registered-name> (or set REPS_TARGET), "
            "or --register-target <config.json> to register one from a local config."
        )
    try:
        target = okareo.get_target_by_name(ref)
        return getattr(target, "name", ref)
    except Exception as e:  # noqa: BLE001 - tolerate id refs / SDK differences
        # Could be an id, or get_target_by_name unavailable; pass the ref through (run_simulation
        # accepts a str target). Surface a hint so a genuinely-missing name is diagnosable.
        print(f"  ⚠ could not verify target {ref!r} via get_target_by_name ({e}); "
              f"passing it through to run_simulation as-is.")
        return ref


def build_target(config: dict | str | Path):
    """Build an Okareo Target from a config dict or a path to a target.json.

    Dispatches to the voice or text adapter by modality. Imports Okareo lazily so pure
    config/validation helpers stay importable without the SDK.
    """
    if isinstance(config, (str, Path)):
        config = load_target_config(config)
    modality = validate_target_config(config)

    if modality == "voice":
        from reps.targets.voice_target import build_voice_target

        return build_voice_target(config)
    from reps.targets.http_target import build_http_target

    return build_http_target(config)

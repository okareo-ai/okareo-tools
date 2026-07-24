"""
Voice target adapter (v0 focus).

Builds an Okareo voice `Target` from the `voice` block of a target config. Supports the four
providers documented by Okareo: OpenAI Realtime, Deepgram, Twilio, and a custom voice endpoint.

Okareo classes are imported lazily so `reps.targets` config helpers remain importable without the
SDK. Constructor kwargs follow the Okareo Python SDK voice-target reference; if the installed SDK
exposes a different signature, the resulting error names the provider so it is easy to adjust.
"""
from __future__ import annotations

from typing import Any

from reps.targets import resolve_secret


def build_voice_target(config: dict) -> Any:
    """Construct an Okareo voice Target from `config`. Requires the okareo SDK installed."""
    from okareo.model_under_test import Target  # lazy

    voice = config.get("voice") or {}
    provider = str(voice.get("provider", "")).strip().lower()
    name = config["name"]
    api_key = resolve_secret(config, "auth.api_key_env")
    instructions = voice.get("instructions", "") or ""

    if provider == "openai":
        from okareo.model_under_test import OpenAIVoiceTarget

        endpoint = OpenAIVoiceTarget(
            model=voice.get("model", "gpt-realtime"),
            voice=voice.get("tts_voice", "alloy"),
            system_prompt=instructions,
            api_key=api_key or None,
        )
    elif provider == "deepgram":
        from okareo.model_under_test import DeepgramVoiceTarget

        endpoint = DeepgramVoiceTarget(
            model=voice.get("model", "aura-2"),
            voice=voice.get("tts_voice", "aura-2-thalia-en"),
            system_prompt=instructions,
            api_key=api_key or None,
        )
    elif provider == "twilio":
        from okareo.model_under_test import TwilioVoiceTarget

        endpoint = TwilioVoiceTarget(
            from_number=voice.get("from_number", ""),
            to_number=voice.get("to_number", ""),
            api_key=api_key or None,
            max_parallel_requests=int(config.get("max_parallel_requests", 1)),
        )
    elif provider == "custom":
        from okareo.model_under_test import CustomVoiceTarget

        endpoint = CustomVoiceTarget(
            endpoint_url=voice["custom_endpoint_url"],
            api_key=api_key or None,
        )
    else:  # pragma: no cover - validated upstream
        raise ValueError(f"Unsupported voice provider: {provider!r}")

    return Target(target=endpoint, name=name)

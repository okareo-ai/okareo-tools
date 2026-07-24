"""
Text / HTTP target adapter (additive seam — reserved for the text workbench).

Ports the proven `CustomEndpointTarget` construction from `compliance-owasp` (start/next/end
session, auth, streaming, `{latest_message}`/`{session_id}` substitution). Present behind the same
interface as the voice adapter so a text workbench is a drop-in; not exercised in the v0 voice suite.
"""
from __future__ import annotations

import json
from typing import Any

from reps.targets import resolve_secret


def build_http_target(config: dict) -> Any:
    """Construct an Okareo text Target (CustomEndpointTarget) from `config`.

    Feature 004: an optional `config["trace"]["path"]` declares where the agent's structured
    tool-call trace appears in the response (sibling to `response_path`). It does not change how the
    target is built — the runner resolves trace availability (reps.trace.resolve_trace_available) and
    capture reads the trace per datapoint at that path to label Execution findings `trace-verified`
    vs `conversation-inferred`. Omit the block for a black-box text agent.
    """
    from okareo.model_under_test import (  # lazy
        AuthConfig,
        CustomEndpointTarget,
        EndSessionConfig,
        SessionConfig,
        StreamingConfig,
        StreamingSelectCondition,
        StreamingStopCondition,
        Target,
        TurnConfig,
    )

    name = config.get("name", "reps-text-target")
    endpoint_url = config.get("endpoint_url")
    if not endpoint_url:
        raise ValueError(f"endpoint_url not set for text target {name!r}.")
    method = config.get("method", "POST")
    max_parallel = int(config.get("max_parallel_requests", 1))
    response_path = config.get("response_path", "response")
    api_key = resolve_secret(config, "auth.api_key_env")

    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    headers_json = json.dumps(headers)

    # request_body: dict (JSON config) or string. Pass as string so Okareo performs
    # {latest_message}/{session_id} substitution.
    raw_body = config.get("request_body", {"message": "{latest_message}"})
    next_body = json.dumps(raw_body) if isinstance(raw_body, dict) else raw_body

    session = config.get("session", {}) or {}
    session_id_path = session.get("session_id_path", "")

    # Auth
    auth_section = config.get("auth", {}) or {}
    auth_config = None
    if auth_section.get("url"):
        body_raw = auth_section.get("body", {})
        auth_body = json.loads(body_raw) if isinstance(body_raw, str) and body_raw else body_raw
        auth_config = AuthConfig(
            url=auth_section["url"],
            method=auth_section.get("method", "POST"),
            headers=headers_json,
            body=auth_body if isinstance(auth_body, dict) else {},
            response_access_token_path=auth_section.get("response_access_token_path", ""),
        )

    # Streaming
    streaming_section = config.get("streaming", {}) or {}
    streaming_config = None
    if streaming_section.get("enabled"):
        headers["Accept"] = "text/event-stream"
        headers_json = json.dumps(headers)
        response_path = streaming_section.get("response_path", response_path)
        streaming_config = StreamingConfig(
            stop=[StreamingStopCondition(**c) for c in streaming_section.get("stop", [])],
            select=[StreamingSelectCondition(**c) for c in streaming_section.get("select", [])],
        )

    start_session = None
    if session.get("start_url"):
        sb_raw = session.get("start_body", {})
        start_body = json.loads(sb_raw) if isinstance(sb_raw, str) and sb_raw else sb_raw
        start_session = SessionConfig(
            url=session["start_url"],
            method="POST",
            headers=headers_json,
            response_session_id_path=session_id_path or "response.session_id",
            body=start_body if isinstance(start_body, dict) else {},
        )

    next_turn = TurnConfig(
        url=endpoint_url,
        method=method,
        headers=headers_json,
        body=next_body,
        response_message_path=response_path,
        response_session_id_path=session_id_path,
        streaming=streaming_config,
    )

    end_session = None
    if session.get("end_url"):
        eb_raw = session.get("end_body", {})
        end_body = json.loads(eb_raw) if isinstance(eb_raw, str) and eb_raw else eb_raw
        end_session = EndSessionConfig(
            url=session["end_url"],
            method="POST",
            headers=headers_json,
            body=end_body if isinstance(end_body, dict) else {},
        )

    endpoint = CustomEndpointTarget(
        start_session=start_session,
        next_turn=next_turn,
        end_session=end_session,
        auth=auth_config,
        max_parallel_requests=max_parallel,
    )
    return Target(target=endpoint, name=name)

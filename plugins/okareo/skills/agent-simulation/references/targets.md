# Configuring the target

This file is loaded when the simulation reaches target registration. It
covers how to register the two target types a text simulation uses — a
custom HTTP endpoint and a prompt — and how to get each one right.

The target is Okareo's *handle* on the agent under test. It does not hold
the agent's logic; it tells Okareo how to reach the agent and how to read
its replies. A target registered wrong produces a simulation that fails on
turn one for reasons that have nothing to do with the agent's quality.

## Which target type

- **`custom_endpoint`** — the agent is a deployed service with an HTTP API.
  This is the common case for a real agent or chatbot. Okareo calls the
  endpoint each turn.
- **`generation`** — the thing under test is a *prompt* run against a model,
  not a deployed service. Use it when the user wants to exercise a prompt or
  compare prompt versions, and there is no API to call.

If the user has a running agent behind an API, use `custom_endpoint`. If
they only have a prompt, use `generation`.

## Custom endpoint targets

A `custom_endpoint` target describes how Okareo turns a conversation turn
into an HTTP request and finds the agent's reply in the response.

### Start-session vs per-message

Some agents need a session opened before the conversation starts (to get a
conversation id, a token, or initial state); some are stateless and take
each message standalone. Configure:

- **Start-session call** — the request that opens a conversation, if the
  agent needs one. Capture whatever the response returns (a session id) for
  reuse on later turns.
- **Per-message call** — the request sent for each turn of the conversation.

A stateless agent needs only the per-message call.

### Finding the reply in the response

Okareo needs to know *where* in the HTTP response body the agent's reply
text is — the path to the message field. Point it at the right field. If
the response wraps the reply in a structure, give the path into that
structure, not the whole body.

### Streaming / SSE endpoints

If the endpoint streams its reply (server-sent events) rather than
returning one JSON body, configure the streaming behavior: how chunks are
delimited, which chunk field carries the text, and the condition that marks
the end of the message. Streaming configuration applies to `custom_endpoint`
targets only — a `generation` target is not a streaming endpoint.

### Authentication

If the endpoint needs auth — a bearer token, an API key header, Basic auth —
configure it on the target. Treat tokens and keys as **secrets**: do not
echo them back into the conversation or into a report. If the user has not
provided the credential, ask for it rather than guessing the scheme.

## Generation (prompt) targets

A `generation` target pairs a prompt with a model. Use it to exercise a
prompt directly:

- Provide the prompt — typically a system/instruction prompt with
  placeholders for the scenario input.
- Choose the model the prompt runs against. Discover the available models
  before picking one rather than assuming a name.
- Because there is no deployed service, a `generation` target is the right
  way to compare two prompt versions or two models on the same scenario set.

## Reusing or cloning an existing target

There is no dedicated clone-target tool, but `get_target` and
`create_or_update_target` are now aligned to support the workflow directly:
`get_target` returns a **flat envelope whose keys mirror
`create_or_update_target` kwargs**. Reading an envelope, modifying a field
or two, and feeding it back is the canonical clone path.

Three things to know:

- **`create_or_update_target` is a full replace.** Reusing an existing name
  fully overwrites the target's config; any kwarg you do not pass is
  dropped. Picking a new name has the same effect — the new target only
  contains what you pass. The clone-via-envelope pattern works because you
  pass back what you read.
- **Sensitive values come back as the redaction sentinel.** Fields listed
  under the target's `sensitive_fields` (e.g. `auth_params.headers.Authorization`,
  any OAuth `client_secret`) appear in the `get_target` response as the
  literal string `"***REDACTED***"`. The *shape* of `auth_params` — URL,
  method, header keys, body keys, response token path — is fully visible;
  the *values* of secret fields are not. `create_or_update_target` validates
  the payload and rejects any call still containing the sentinel before
  reaching the backend, with a named-path error.
- **`max_parallel_requests` is the web-UI "max concurrency" knob.** It now
  appears at the top level of the `get_target` envelope when set, matching
  the create kwarg name. The web UI labels the same setting "max concurrency";
  it's one knob with two names depending on which surface you're on.

### Canonical clone workflow

1. `get_target("prod-chatbot")` — pull the envelope. Note every key with
   the value `"***REDACTED***"`; these are the secrets the user must
   re-supply.
2. Modify what should change for the clone — `name` (always), URLs, any
   specific config tweak.
3. **Substitute every `"***REDACTED***"` value** with the real secret from
   the user. Don't try to bypass the check.
4. `create_or_update_target(**envelope)` — pass the modified envelope back
   as kwargs (drop read-only metadata like `target_id` and any `tags` you
   don't want to carry).
5. If the call returns an error like `"Redaction sentinel still present at:
   <paths>"`, you missed a substitution. Replace the named paths and
   retry; the MCP made zero network calls, so retry is cheap.

### Checklist before calling `create_or_update_target` on a clone

- [ ] `name` — change for a sibling clone; keep for an in-place edit.
- [ ] `next_message_params` (incl. nested `streaming` if applicable) — should
      come back fully from `get_target`; pass through.
- [ ] `start_session_params` / `end_session_params` (if the agent uses them) —
      same.
- [ ] `max_parallel_requests` — restate explicitly if you want it; it's
      visible in the envelope. ("Max concurrency" in the web UI.)
- [ ] `auth_params` — visible in shape; **substitute every `"***REDACTED***"`
      value** with real secrets from the user.
- [ ] `sensitive_fields` — comes back in the envelope; pass through so the
      new target preserves the same redaction list.

The mental model is "feed get_target back into create after substituting
the redacted bits", not "build a target from scratch using the original as
a reference". The old version of this skill said the latter because the
read and write shapes used to diverge; they no longer do.

### Streaming on read

`streaming` lives inside `next_message_params` (and optionally
`start_session_params`) on both read and write — there is no Target-level
`streaming` field. If a user references "the target's streaming setting"
they mean the per-endpoint config under those keys.

## Common mistakes

- Pointing the reply path at the wrong field, so every turn reads as empty —
  the simulation looks broken when the agent is fine.
- Forgetting the start-session call for an agent that needs one, so every
  turn starts a fresh stateless conversation.
- Configuring streaming on a non-streaming endpoint, or omitting it on one
  that streams — either way the reply never assembles.
- Hard-coding a secret into the target config in a way that surfaces it in
  output. Keep credentials out of transcripts and reports.
- Trying to clone by passing `get_target` output back to
  `create_or_update_target` without substituting the `"***REDACTED***"`
  values. The MCP rejects it pre-network with the offending paths named —
  fix those paths, don't try to bypass the check.
- Treating `auth_params` as write-only because an older version of this
  doc said so. The *shape* round-trips now; only the *values* of
  `sensitive_fields` are masked.

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

## Common mistakes

- Pointing the reply path at the wrong field, so every turn reads as empty —
  the simulation looks broken when the agent is fine.
- Forgetting the start-session call for an agent that needs one, so every
  turn starts a fresh stateless conversation.
- Configuring streaming on a non-streaming endpoint, or omitting it on one
  that streams — either way the reply never assembles.
- Hard-coding a secret into the target config in a way that surfaces it in
  output. Keep credentials out of transcripts and reports.

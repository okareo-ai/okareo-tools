# Running and polling a cycle

Loaded at the run and poll steps. Covers the run parameters that matter, how
to replay the *same* harness, and what the poll signal actually looks like.

## Replay the same harness from a prior run

Every cycle must run the identical Target / Driver / Scenario / checks, or the
before/after is meaningless. A prior test-run record carries the full harness
identity — read it off the last run and replay rather than re-specifying by
hand. The fields that define the harness:

- `mut_id` — the Target (the agent under test).
- `driver_id` — the Driver (the simulated caller / persona).
- `scenario_set_id` — the Scenario.
- `check_ids` — the exact checks, with versions.
- `simulation_params` — `max_turns`, `first_turn`, `repeats`, `silence_timeout_ms`.

Pass `based_on_run_id=<prior run id>` to `run_simulation` to replay that setup.
If you must respecify, copy these values exactly — a changed turn cap or a
different check set silently breaks comparability.

## run_simulation parameters that matter

- `target_name`, `driver_name`, `scenario_name` — the harness pieces.
- `first_turn` — `target` means the agent greets first (inbound); the caller
  opens otherwise. Match production and keep it fixed across cycles.
- `max_turns` — **always cap.** On a phone target an uncapped stuck agent is an
  endless billed call.
- `checks` — at least a completion check (see the check cookbook).
- Pacing knobs, all optional and held constant across cycles unless you are
  deliberately testing one: `turn_transition_time`, `silence_timeout_ms`,
  `checks_at_every_turn`, `stop_check`.

`run_simulation` returns promptly. For a short run it returns finished with
results; for a longer one it returns a *running* status plus a durable run id
and keeps executing on the backend after the client disconnects.

## The poll signal

Poll `get_test_run_results` with the run id. Read:

- **status** — a terminal `FINISHED` (uppercase) means done. Non-terminal
  values include `RUNNING`, `PENDING`, `STARTED`, `IN_PROGRESS`, `QUEUED`.
- **progress** — a number reaching `100.0` at completion. Poll on status and
  progress together, not on data-point count alone.
- **failure_message** — non-null means the run failed; report it and stop.

### Finalization lag is real

A run can sit near `progress: 99` / non-terminal for a noticeable stretch after
the call ends. **Audio checks finalize slowest** — the recording is processed
after the conversation, and results can appear in the app UI before the API
returns them. Keep polling; a slow finalize is not a failure.

### Do not double-submit

Because the run survives a disconnect, a submit that times out on the client
has very likely still started on the backend. Before re-submitting, call
`list_simulations` and look for the run — re-submitting blindly places a second
real, billed call.
</content>

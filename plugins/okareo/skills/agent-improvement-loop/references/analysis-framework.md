# Analysis framework

Loaded at the diagnose step. Counting pass rates is not diagnosis. The loop
needs, every cycle: an outcome verdict, a coverage matrix, and exactly one
named root cause — so the next change is attributable.

## Read the verdict from the text, not the score

An analysis check (`output_type: analysis`) returns both a numeric value and
an explanation. **They can disagree, and the explanation is the honest one.**
In a real run the analysis check scored `1.0` (a "pass") while its explanation
opened with "Outcome — Partially" and listed seven unmet objectives. Always
read the outcome verdict — Yes / Partially / No — from the explanation against
the written success definition, never from the bare score.

## Objective-coverage matrix

One row per objective from the success definition, scored with a quoted
example from the transcript:

| Objective | Status | Evidence |
| --- | --- | --- |
| <goal> | ✅ met / 🟡 partial / ⬜ untouched / ❌ wrong | "<quote from the call>" |

The matrix is what turns "Partially" into a list of specific things to fix,
and it is what the per-cycle trend tracks for "coverage went 3/6 → 6/6".

## Root-cause taxonomy — name exactly one per cycle

- **Agent / prompt failure** — the agent had the turns and the tool and still
  answered wrong, vaguely, or off-policy.
- **Tool / integration failure** — a tool errored or returned nothing.
- **Latency-bound coverage** — the agent was correct but too slow; per-turn
  latency burned the turn budget before objectives were reached. (In a real
  run, ~41s/turn capped coverage even after the content was right.)
- **Transcription noise (STT/TTS)** — the failure is in the transcript, not the
  agent (see below).
- **Caller / sim artifact** — the simulated caller behaved unrealistically, or
  a role was mis-attributed.
- **Platform artifact** — a known false metric or harness quirk (see the check
  cookbook's `response_efficiency` artifact).

Naming one primary cause forces a single targeted change. If two causes look
equal, pick the one that *gates* the others — fix latency before content if the
agent cannot reach the later objectives in the turn budget.

## Signal vs. noise — check before blaming the agent

Before counting a failure against the agent, rule out artifacts:

- **Mis-transcription.** In a real run the audio pronunciation check scored the
  spoken word correct ("Oh-Car-Ee-Oh in all instances") while the STT
  transcript read "Ocarreo / Ocario". The agent was right; the transcriber was
  wrong. For pronunciation, trust the audio check over the text.
- **Role attribution.** Confirm the failing turn was actually the agent's, not
  the caller's, before scoring it.
- **Unrealistic caller.** A driver that ignores the scenario or behaves
  implausibly produces failures that are the harness's fault, not the agent's —
  fix the harness, do not count the failure.

A failure that survives all three is a real agent failure worth a change.
</content>

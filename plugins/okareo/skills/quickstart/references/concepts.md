# The Okareo model — Target, Driver, Scenario, Checks

This file is loaded when the quickstart reaches the teaching step. It is the
material to explain the model from — keep the explanation short and grounded
in what the user is trying to test.

## The four pieces

Every Okareo run is built from the same four objects:

- **Target** — the thing under test. A text agent, a voice agent reachable
  by phone, or a generation model/endpoint. The target is Okareo's *handle*
  on the system; it does not contain the system's logic.
- **Driver** — the simulated user. A persona that decides what the user
  wants and how they behave across a multi-turn conversation. The driver is
  the *user*, never the agent. (Evaluations of fixed inputs do not need a
  driver — there is no conversation to drive.)
- **Scenario** — the test cases. A scenario set is rows; each row is one
  test, with an `input` and an expected `result`. The same set is re-run on
  every change, which is what makes results comparable over time.
- **Checks** — how each run is scored. A check reads an output or a finished
  conversation and returns a verdict. Without checks, a run produces text
  and no judgement.

## Simulation vs evaluation

Both score a target against a scenario set with checks. The difference is
where the conversation comes from:

- **Simulation** — Okareo *generates* the conversation. A driver (the
  simulated user) talks to the target turn by turn. Use it to probe how an
  agent behaves: multi-turn, many personas, before production.
- **Evaluation** — the inputs are *fixed*. Okareo sends each scenario
  input to the target and scores the output. Use it to score quality
  against known expected results and to catch regressions.

A new user with a running agent usually starts with a simulation; a user
with a set of inputs and expected answers starts with an evaluation.

## How a run flows

```
Scenario (the cases) ─┐
Driver (the user) ────┼─▶ run against ─▶ Target ─▶ scored by ─▶ Checks
                      ┘                                          │
                                                                 ▼
                                                    results: pass rate,
                                                    per-row verdicts,
                                                    transcripts
```

## Where the skills fit

- `scenario-design` / `scenario-from-traces` — build the scenario set.
- `agent-simulation` / `voice-simulation` — run simulations against an agent.
- `evaluation` — score a target against a scenario set.
- `monitoring` — run checks on live production traffic.

The quickstart's job is only to make these four pieces concrete and get the
user into the first run. Depth is the specialist skills' job.

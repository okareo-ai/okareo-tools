# Roadmap

Planned and candidate Okareo skills. The four shipping skills cover the core
lifecycle (simulation → monitoring → scenario-from-traces → evaluation); the
items below extend it. See [CONTRIBUTING.md](CONTRIBUTING.md) to pick one up.

## Shipping

| Skill                          | Status   |
| ------------------------------ | -------- |
| `okareo-agent-simulation`      | Shipping |
| `okareo-evaluation`            | Shipping |
| `okareo-monitoring`            | Shipping |
| `okareo-scenario-from-traces`  | Shipping |

## Candidate skills

### `okareo-behavior-probe` — explore an agent and build a testing regime

A discovery-first skill: point it at an unfamiliar agent, have it probe the
agent's surface (tools, prompts, scope, refusal boundaries), characterize
how it behaves, and from that propose a full testing regime — a scenario
set, the checks that matter, and a simulation plan. The bridge from "I have
an agent" to "I have a test suite", upstream of `okareo-evaluation`.

### `okareo-issue-to-scenario` — turn issue trackers into scenarios

Today `okareo-scenario-from-traces` accepts pasted issue text. A dedicated
skill would go further: pull issues directly from a tracker (GitHub Issues,
Linear, Jira), triage which ones describe a *behavioral* bug worth a test,
extract the input and the corrected expected behavior from the issue thread,
and persist them as a scenario set — closing the loop from bug report to
regression guard.

### `okareo-check-authoring` — design and tune custom checks

Custom checks (deterministic and model-graded) are currently a sub-step
inside `okareo-evaluation`. A focused skill would own the full check
lifecycle: drafting a check from a described property, iterating its rubric
or code against labelled examples, and measuring the check's own
reliability before it is trusted in an eval.

> Candidates are intentionally loosely specified. Tighten the scope when you
> pick one up, and confirm it earns its own skill rather than extending an
> existing one (see CONTRIBUTING.md, "How skills compose").

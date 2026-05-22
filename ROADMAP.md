# Roadmap

Shipping, planned, and candidate Okareo skills and commands. See
[CONTRIBUTING.md](CONTRIBUTING.md) to pick one up.

## Shipping (Phase 1)

The end-to-end loop: onboard, build a scenario set, simulate text and voice,
evaluate, and monitor.

| Skill                  | Status   |
| ---------------------- | -------- |
| `quickstart`           | Shipping |
| `scenario-design`      | Shipping |
| `scenario-from-traces` | Shipping |
| `agent-simulation`     | Shipping |
| `voice-simulation`     | Shipping |
| `evaluation`           | Shipping |
| `monitoring`           | Shipping |

| Command              | Status   |
| -------------------- | -------- |
| `/okareo:quickstart` | Shipping |
| `/okareo:scenario`   | Shipping |
| `/okareo:simulate`   | Shipping |
| `/okareo:monitor`    | Shipping |

## Planned (Phase 2) — depth and hardening

| Skill                | Notes                                                              |
| -------------------- | ------------------------------------------------------------------ |
| `rag-evaluation`     | End-to-end RAG evaluation — intent, retrieval, grounding.           |
| `agentic-evaluation` | Function-calling and multi-agent behavior.                          |
| `checks`             | Author code and model-graded checks. Cross-cutting.                 |
| `red-teaming`        | General adversarial probing and guardrail validation.               |
| `owasp`              | The OWASP LLM & Agentic Top 10 compliance program (20 categories).  |

| Command            | Notes                                          |
| ------------------ | ---------------------------------------------- |
| `/okareo:evaluate` | Branches generation / RAG / agentic.            |
| `/okareo:redteam`  | General adversarial / guardrail validation.     |
| `/okareo:owasp`    | Full Top 10 run or a specific category.         |
| `/okareo:check`    | Scaffold a code or model-graded check.          |
| `/okareo:results`  | Fetch and interpret results from a prior run.   |

## Candidate skills

Loosely specified — tighten the scope when you pick one up, and confirm it
earns its own skill rather than extending an existing one (see
CONTRIBUTING.md, "How skills compose").

### `behavior-probe` — explore an agent and build a testing regime

A discovery-first skill: point it at an unfamiliar agent, have it probe the
agent's surface (tools, prompts, scope, refusal boundaries), characterize
how it behaves, and from that propose a full testing regime — a scenario
set, the checks that matter, and a simulation plan. The bridge from "I have
an agent" to "I have a test suite".

### `issue-to-scenario` — turn issue trackers into scenarios

Today `scenario-from-traces` accepts pasted issue text. A dedicated skill
would go further: pull issues directly from a tracker (GitHub Issues,
Linear, Jira), triage which ones describe a *behavioral* bug worth a test,
extract the input and corrected expected behavior from the issue thread, and
persist them as a scenario set — closing the loop from bug report to
regression guard.

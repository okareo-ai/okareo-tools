---
name: discovery
description: "Predefined discovery seeds for reps-explore (feature 010). Each row is one benign discovery-conversation angle a first-time user might take: direct (what are you for?), task-first (is this the right assistant for my vague task?), and limits-first (what can't you do / what are the rules?). One row is used per conversation; follow-up conversations (max 3 total) use a DIFFERENT angle. NOT a REPS probe bank: no sub_capability, no pass criterion, nothing judged — the transcript is the product."
reps_pillar: none (exploration aid)
artifact_type: scenario
eval_mode: multi-turn
status: complete
version: 0.2.0
---

# Scenario bank: discovery (exploration aid)

## What is being run and why

The `reps-explore` skill runs ONE simulation from this bank (driver `curious-onboarder`, the
target's own modality) to learn what a target agent is *for* — its domain, role, supported and
declined intents, visible tools, and guardrails — before any REPS tuning exists. Conversation
mechanics match the modality (FR-019): a voice target speaks first (it answers the call and
greets, as a real callee does) with `max_turns` 20 (a 15–20-turn budget; natural close may end
earlier); a text target hears the persona first with `max_turns` 8. One lightweight
platform-required check is attached and its score ignored — nothing is judged. The recorded
transcript is reviewable by an onboarding user and is the evidence base for the draft agent
profile written to `results/<agent_slug>/profile/`.

## Row shape (NOT the standardized REPS row contract)

`input.persona` + `input.script` (consumed by the driver shell) + `input.driver` routing + a
neutral top-level `result` stating there is no pass criterion. Deliberately no `sub_capability`,
no `severity_on_fail`, no expected outcome anywhere — nothing here is scored, and this bank is
exempt from `reps.rows.validate_rows` (which governs pillar probe banks only). See
`specs/010-reps-explore/contracts/exploration-artifacts.md` (INV-E6).

## Interpreting "results"

There is no pass/fail. A useful conversation is one where the agent states or demonstrates its
purpose; a tight-lipped conversation triggers at most two follow-ups with a different angle, after
which reps-explore fills gaps with flagged assumptions and reports low confidence — never an
error, never a finding.

## Rules

- Baseline artifact: agent-agnostic, committed, read-only for tuning flows (Constitution IV/VII).
- Benign only (INV-E3): scripts must stay cooperative — no adversarial, deceptive, or
  policy-probing content. If the assistant declines anything, the persona accepts and moves on.
- Platform copies are one single-row scenario per angle — `explore-discovery-direct` /
  `explore-discovery-task-first` / `explore-discovery-limits-first` — tagged
  `reps, explore, standard, fp:<hash>` (fingerprint of that row), and reused by fingerprint on
  re-runs (never duplicated; superseded rows get a new version, not a new name).

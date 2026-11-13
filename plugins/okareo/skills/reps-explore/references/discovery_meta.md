---
name: discovery
description: "Predefined discovery seeds for reps-explore. Two kinds. CAPABILITY rows (feature 010) learn what an unknown agent is for: direct, task-first, limits-first. GROUND-TRUTH rows (feature 022) learn the facts a criterion will later be built from: offers and per-unit prices and how a quote scales; and external facts, the quantity limit, the verification method and out-of-scope topics in the agent's own referral wording. One row per conversation. NOT a REPS probe bank: no sub_capability, no pass criterion, nothing judged — the transcript is the product."
reps_pillar: none (exploration aid)
artifact_type: scenario
eval_mode: multi-turn
status: complete
version: 0.4.0
---

# Scenario bank: discovery (exploration aid)

## What is being run and why

The `reps-explore` skill runs discovery simulations (driver `curious-onboarder`, the target's own
modality) to learn things about a target agent that no profile can be trusted to supply. Nothing
here is judged. The recorded transcript is reviewable by an onboarding user and is the evidence base
for the draft agent profile written to `results/<agent_slug>/profile/`.

Conversation mechanics match the modality (FR-019): a voice target speaks first (it answers the
call and greets, as a real callee does) with `max_turns` 20 (a 15–20-turn budget; natural close may
end earlier); a text target hears the persona first with `max_turns` 8. One lightweight
platform-required check is attached and its score ignored — nothing is judged.

## Two kinds of row, selected by `input.discovery_kind`

**`capability`** — the three original angles (feature 010). What is this agent *for*: its domain,
role, supported and declined intents, visible tools and guardrails. Run when onboarding an unknown
agent. One row per conversation; follow-ups (max 3) use a DIFFERENT angle.

**`ground_truth`** — two rows (feature 022, `contracts/agent-environment.md` invariant C). These
exist because **row generation is blocked until `ground_truth.verified_on` is set**: the first field
evaluation built criteria on two facts nobody had checked — a two-seat total recorded as a per-seat
price, and a cancelled order recorded as active — and lost an entire round failing a correct agent.
The second run held this conversation first and had no ground-truth faults.

The pair elicits a fixed minimum, and nothing in it may be dropped:

| Row | Elicits |
|---|---|
| offers and pricing | every offering in the agent's own words · what **one** unit costs · **whether that figure is per unit or a total** · what a named larger quantity comes to · add-ons · tier/section variation |
| facts, limits and refusals | external fact sources and their currency, with one dated example · the maximum per interaction and what happens past it · the verification factor and any alternative · every out-of-scope topic paired with the agent's **own** referral wording |

The per-unit question is the original defect turned into a question. It is asked twice on purpose —
once as "what does one cost", once as "is that each, or all in?" — because a single question gets a
single number and no indication of which kind of number it is.

## Row shape (NOT the standardized REPS row contract)

The six caller-facing fields the driver reads — `caller_name`, `caller_context`, `goal`,
`required_moves` (rendered to `guidance`), `constraints` (a list), `known_details` (an object) —
plus `persona` for demeanour and `driver` routing, and a top-level `result` that asserts no verdict.

Deliberately no `sub_capability`, no `severity_on_fail`, no expected outcome anywhere — nothing here
is scored, and this bank is exempt from `reps.rows.validate_rows` (which governs pillar probe banks
only); the bank's invariants are enforced by `tests/test_explore_artifacts.py` instead.

`constraints` and `known_details` are authored as a list and an object and **rendered to strings**
by `reps.rows.render_row`, for the same reason the arc is: a driver token stringifies whatever it
finds, so an unrendered list reaches the caller model as a language-level repr. An empty one renders
as `none`. `known_details` is empty in the committed baseline by necessity — the baseline is
agent-agnostic and knows nothing about any agent — and is filled by the overlay where a prior
conversation already established something, so the caller can ask a sharper question instead of
re-asking.

### The observational result (FR-016b)

Every row's `result` is **non-empty and observational**: it names what to record, never a pass
criterion. That is how discovery satisfies the every-row-has-a-result rule — the platform accepts a
resultless row and then silently under-serves any check that declares it needs one — while
asserting no verdict and staying outside coverage accounting (feature 010).

A ground-truth row's result also states the negative case explicitly: *where the agent gave no
answer, record that it gave none.* An unanswered question is a gap to re-ask, never a value to fill
in, and a profile field filled from an unanswered question is indistinguishable from a verified one.

### The purchase stance (invariant C3)

Every row carries a `constraints` entry forbidding agreement to buy, book, order, reserve or pay —
in the **constraints list**, not in the arc prose, so it overrides default conduct and the assistant
cannot walk a discovery caller into a transaction it was never meant to make. The ground-truth rows
add two more: never state a price or quantity as a fact (a caller who supplies the number gets it
agreed back, and the answer is worthless), and never accept a way around a limit.

## Interpreting "results"

There is no pass/fail. A useful capability conversation is one where the agent states or
demonstrates its purpose; a tight-lipped one triggers at most two follow-ups with a different angle,
after which reps-explore fills gaps with flagged assumptions and reports low confidence — never an
error, never a finding.

A useful ground-truth conversation is one where every item in the table above has either the agent's
own words or an explicit "not answered". Where the agent **contradicts** a value the operator
already supplied, that is recorded under `ground_truth.contradictions` and surfaced to the operator:
neither value is written into a criterion (`contracts/agent-environment.md` invariant F), because
the supplied one is disputed and the observed one is a single conversation, not verification.

## Rules

- Baseline artifact: agent-agnostic, committed, read-only for tuning flows (Constitution IV/VII).
- Benign only (INV-E3): discovery guidance must stay cooperative — no adversarial, deceptive, or
  policy-probing content. If the assistant declines anything, the persona accepts and moves on.
- The caller **never supplies the facts it is trying to learn**. The driver carries this as an
  objective and the ground-truth rows carry it as a constraint, because an assistant handed a number
  will often agree with it.
- Platform copies are one single-row scenario per angle — `explore-discovery-direct` /
  `explore-discovery-task-first` / `explore-discovery-limits-first` / `explore-discovery-pricing` /
  `explore-discovery-limits-facts` — tagged `reps, explore, standard, fp:<hash>` (fingerprint of
  that row), and reused by fingerprint on re-runs (never duplicated; superseded rows get a new
  version, not a new name).

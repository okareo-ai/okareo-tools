# reps/explore — Agent Exploration Baseline (setup aid, NOT a pillar)

These are the committed, agent-agnostic artifacts the `reps-explore` skill uses to hold a short,
benign **discovery conversation** with a registered target agent and draft its profile.

```
explore/
├── drivers/curious-onboarder.md   # the one benign-discovery persona (six caller-facing fields)
└── scenarios/discovery.jsonl      # 5 seeds: 3 capability + 2 ground-truth (+ discovery_meta.md)
```

## Two kinds of discovery row

Rows declare their kind in `input.discovery_kind`.

- **`capability`** (3 rows) — what is this agent *for*: domain, role, supported and declined
  intents, visible tools, guardrails. Direct, task-first and limits-first angles; one per
  conversation, max 3.
- **`ground_truth`** (2 rows, added in 0.7.0) — the **facts a criterion will later be built from**.
  One elicits offerings, what **one** unit costs, **whether that figure is per unit or a total**,
  how a quote scales, add-ons and tier variation. The other elicits external fact sources with a
  dated example, the quantity limit, the verification factor, and every out-of-scope topic paired
  with the agent's **own** referral wording.

The ground-truth pair exists because **row generation is blocked until `ground_truth.verified_on` is
set**. The first field evaluation built criteria on two facts nobody had checked — a two-seat total
recorded as a per-seat price, and a cancelled order recorded as active — and lost an entire round
failing a correct agent. The per-unit question is asked twice on purpose: one question gets one
number and no indication of which kind of number it is.

Every row is **authored as structure and rendered** (`reps.rows.render_row`), carries its purchase
stance in a **constraints list** so a discovery caller cannot be walked into a transaction, and
carries a non-empty **observational** result naming what to record — never a pass criterion. The
caller is forbidden from supplying the facts it is eliciting, because an assistant handed a number
will often simply agree with it.

## What exploration is — and is not

- **It is a setup aid.** One (max 3) recorded simulation learns what the agent is *for* — domain,
  role, supported/declined intents, visible tools and guardrails — and writes a **draft profile**
  (`status: draft`, with per-fact provenance) plus a human-readable exploration summary into the
  agent's gitignored overlay: `results/<agent_slug>/profile/`.
- **It is NOT a REPS probe.** Nothing here appears in any pillar `eval_config.json`,
  `coverage.json`, pillar artifact discovery, or the report's coverage accounting, and no check is
  attached to the discovery simulation. Exploration never counts as coverage and asserts no
  verdict (`reps_dimension: none (exploration aid)`).

## The pipeline

```
reps-explore   →  writes results/<agent_slug>/profile/agent-profile.yaml  (status: draft)
reps-profile   →  applies the draft (auto-accepts explored facts, interviews only missing
                  fields, generates tuned rows), flips status → applied
reps-run       →  executes the simulations; on a still-draft profile it warns and offers
                  baseline (untuned) or stop-and-apply — never auto-applies
```

## Rules (Constitution v1.1.0, "Artifact Scopes")

- Everything in this directory is **baseline**: agent-agnostic, committed, and **read-only** for
  every exploration/tuning flow. After any exploration, `git status --porcelain reps/` MUST print
  nothing.
- Discovery content is **benign only** — a prospective user politely asking questions. No
  adversarial, deceptive, or policy-probing material, so the transcript is safe for an onboarding
  reviewer.
- On-platform copies are named `explore-<stem>` and reused by fingerprint (feature 003 semantics);
  re-running exploration never duplicates them.

Invariants for these artifacts are enforced by `tests/test_explore_artifacts.py`.

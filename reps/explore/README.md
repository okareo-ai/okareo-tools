# reps/explore — Agent Exploration Baseline (setup aid, NOT a pillar)

These are the committed, agent-agnostic artifacts the `reps-explore` skill uses to hold a short,
benign **discovery conversation** with a registered target agent and draft its profile
(feature 010, `specs/010-reps-explore/`).

```
explore/
├── drivers/curious-onboarder.md   # the one benign-discovery persona
└── scenarios/discovery.jsonl      # predefined discovery seeds (+ discovery_meta.md)
```

## What exploration is — and is not

- **It is a setup aid.** One (max 3) recorded simulation learns what the agent is *for* — domain,
  role, supported/declined intents, visible tools and guardrails — and writes a **draft profile**
  (`status: draft`, with per-fact provenance) plus a human-readable exploration summary into the
  agent's gitignored overlay: `results/<agent_slug>/profile/`.
- **It is NOT a REPS probe.** Nothing here appears in any pillar `eval_config.json`,
  `coverage.json`, pillar artifact discovery, or the report's coverage accounting, and no check is
  attached to the discovery simulation. Exploration never counts as coverage and asserts no
  verdict (`reps_dimension: none (exploration aid)` — see
  `specs/010-reps-explore/plan.md`, Complexity Tracking).

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

Contracts: `specs/010-reps-explore/contracts/exploration-artifacts.md`

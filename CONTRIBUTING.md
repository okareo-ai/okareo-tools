# Contributing — authoring Okareo skills

This repo packages the Okareo MCP server and a set of **Agent Skills** as
one Claude Code plugin. The MCP server gives Claude the *tools*; a skill
gives Claude the *method* — when to reach for those tools and how to run a
real workflow with them. This guide is for adding or changing a skill.

## The shape of a skill

One skill = one folder under `plugins/tools/skills/<skill-name>/` with a
`SKILL.md` at its top level and an optional `references/` directory. The
build and release scripts pick up any such folder automatically — adding a
skill is adding a folder.

```
plugins/tools/skills/<skill-name>/
├── SKILL.md              # frontmatter + instructions
└── references/           # detail loaded only when a step needs it
    └── <topic>.md
```

## Authoring a new skill

1. Copy the scaffold: `cp -r skill-template plugins/tools/skills/<skill-name>`.
2. Fill in `SKILL.md` and replace the example reference file.
3. Validate: `python3 scripts/validate_skills.py`.
4. Build locally to confirm it packages: `./scripts/build.sh --build-only`
   is run via `./scripts/build.sh`; inspect `dist/`.

`skill-template/` lives at the repo root, *outside* `skills/`, so it is
never packaged. Do not author skills by editing it.

## SKILL.md frontmatter

```yaml
---
name: <skill-name>          # MUST equal the directory name
description: >-             # third person, trigger-rich, ≤ 1024 chars
  ...
---
```

The `description` is what Claude reads to decide whether to invoke the
skill, so it carries real weight:

- Write in the **third person** ("Stress-test an agent before production…"),
  not "You will…".
- Pack it with **triggers** — the verbs and phrasings a user would actually
  use. Include concrete example requests in quotes.
- Add the **implicit-trigger clause**: "Use it even when the user does not
  say 'Okareo' but is clearly trying to …". Skills should fire on intent,
  not on brand name.

## The tool-name contract

Every MCP tool a skill references — in its tool table and inline — must be a
**real Okareo MCP tool**. The placeholder names that shipped in early drafts
(`okareo_run_evaluation`, `okareo_create_monitor`, …) do not exist and must
never come back.

- The canonical tool list lives in `KNOWN_TOOLS` in
  [scripts/validate_skills.py](scripts/validate_skills.py). It is the single
  source of truth.
- `scripts/build.sh` runs the validator first and **refuses to package** a
  skill that references an unknown tool. CI does the same.
- When the Okareo MCP server's tools change, update `KNOWN_TOOLS` in the
  same change that updates the skills.
- Keep the `<!-- TOOL NAMES … -->` comment in each `SKILL.md` — it is a live
  reminder of the contract.

## Standard SKILL.md structure

Every Okareo skill follows the same spine (see any existing skill):

- **Title + one-paragraph intro** — what the skill makes Claude do.
- **When this skill applies** — and, just as important, when *not* to (name
  the adjacent skill instead).
- **How the pieces fit** — the MCP tool table.
- **The `<X>` loop** — numbered steps, in order, scope-before-run.
- **Reporting format** — a fixed scannable template for the final summary.
- **Guardrails** — never fabricate results; stop and report on tool errors.

## references/ — progressive disclosure

Put decision-heavy detail (how to pick checks, design personas, set
thresholds) in `references/<topic>.md` and link it from the single step that
needs it. The agent loads a reference file only when it reaches that step,
which keeps `SKILL.md` short and focused. If a reference file is needed on
every run, fold it back into `SKILL.md`.

## How skills compose

The skills are designed as one lifecycle, and a skill should hand off to the
next rather than do its neighbour's job:

```
agent-simulation ──▶ scenario-from-traces ──▶ run on every change
        ▲                     ▲
   monitoring ────────────────┘
```

Simulation finds failures before release; monitoring catches them in
production; scenario-from-traces turns either kind of failure into a durable
test set that is then re-run on every change. (`okareo-voice-quickstart`
sits outside this loop — it is the onboarding on-ramp.) When adding a skill,
decide where it sits in this flow and which skills it hands off to.

When you find yourself adding a fifth concern to an existing skill, that is
usually a sign it should be a new skill instead.

## Releasing

Versioning and release mechanics live in the [README](README.md#releasing-a-new-version).
In short: bump the version in both manifests, run `./scripts/release.sh`,
push a `v*` tag.

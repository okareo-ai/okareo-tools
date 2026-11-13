# Security pillar — vendored OWASP ASI paths

The REPS Security pillar does **not** re-implement OWASP. It reuses a curated subset of the multi-turn
**agentic (ASI)** controls from [`okareo-ai/compliance-owasp`](https://github.com/okareo-ai/compliance-owasp),
chosen because they are exercised through multi-turn simulation (matching REPS) and are the
highest-severity, most voice-relevant agent risks.

## Vendored paths (source → REPS Security)

| REPS Security anomaly | OWASP source path | `owasp_source` |
|---------------------|-------------------|----------------|
| Goal hijack | `ASI01-agent-goal-hijack` | ASI01 |
| Tool misuse / exploitation | `ASI02-tool-misuse-exploitation` | ASI02 |
| Identity & privilege abuse | `ASI03-identity-privilege-abuse` | ASI03 |
| Memory & context poisoning | `ASI06-memory-context-poisoning` | ASI06 |
| Human–agent trust exploitation | `ASI09-human-agent-trust` | ASI09 |
| Rogue / derailed behavior | `ASI10-rogue-agents` | ASI10 |

## What "vendoring" did

The scenarios (`.jsonl` + `_meta.md`), checks (`.md`/`.py`), and adversarial drivers (`.md`) were
**copied** from the source paths and **re-tagged** — not re-authored. Each artifact gained:

- `reps_pillar: Security`, `modality: both`, `owasp_source: ASI0x`
- drivers additionally gained a `voice_profile` (escalation profile, e.g. `frustrated`/`agitated`) +
  `language` and a voice-interaction extension block, so voice runs apply spoken pressure.

`eval_config.json` here is the merge of the six source eval configs, with scenario names remapped to
the `S-` prefix the runner assigns (checks/drivers keep their original `ASI0x-…` names).

## Keeping in sync

v0 vendors these as committed files so the workbench stays forkable with only an Okareo key. When the
upstream `compliance-owasp` ASI paths change, re-copy + re-tag (a sync script is a future addition).
The remaining OWASP LLM (LLM01–LLM10) and other ASI paths stay in that workbench and are referenced,
not duplicated.

## Feature 022 — structured rows and generated attacks

Two changes supersede the "copy the vendored bank and tune its criteria" path described above. Both
came from the field: in the first of two evaluations on the same build, **a quarter of this pillar's
"passes" were refusals of something the agent had never understood**, and the wrong-verdict rate was
16%. The attacks were generic, delivered verbatim to an agent whose domain they did not touch.

### Rows are authored as structure, rendered for the platform

A row is now written as structure and materialized by `reps.rows.render_row` into the two fields the
platform sees — `input.guidance` and `result`. The four-slot contract for a security row is:

| Slot | What it holds |
|---|---|
| `input.required_moves` | ordered moves, rendered numbered; the caller takes one per turn |
| `input.approach` | three concrete escalation angles, in the `X, then Y, then Z` form |
| `result.must` / `result.must_not` | **at least one, at most one of each** — no AND-ing |
| `input.severity_on_fail` | `Critical` by default for this pillar |

Two rules this pillar gets wrong most easily:

- **A pure prohibition is the normal shape here.** Several probes have no positive clause at all
  ("must not adopt instructions hidden in retrieved data"), and demanding one would invent a second
  way for a call that held its boundary to fail. The validator is symmetric and accepts a MUST NOT
  alone.
- **The press-three-times instruction lives in `reps/shared/caller-conduct.md`, once.** A row that
  repeats it is a validation error. What a row supplies is the three angles, in `approach`.

### Attacks are generated from the profile, not copied

`reps.attacks.generate_attacks` builds rows from the agent's own tools, authority limits, forbidden
actions and observed escalation triggers, covering every sub-capability of its bank's families so no
probe class vanishes when an operator tunes. `check_attacks_grounded` then **rejects** a tuned bank
whose rows name nothing the agent has — a refusal only means something when the attack was
intelligible and in the agent's own domain.

The committed banks here remain the **agent-agnostic fallback**: they run when no profile supplies
anchors, and the report marks the class untuned rather than claiming it was tailored. Generation
from an empty profile returns nothing rather than fabricating.

`reps/S-security/examples/` holds two worked examples, **documentation only and not runnable**,
because what transfers between agents is the shape of a concrete row and a shape is invisible in a
taxonomy of names.

### Two rows may not run at all

- A row needing an environment capability the profile declares as unavailable is **omitted** and
  reported as a `requires-environment` coverage gap, never counted in a pass rate. In the first
  evaluation a gated-disclosure class ran anyway against a caller who could not receive a code, and
  every row read as a pass.
- A row matching a declared escalation trigger is **withheld** to the held bank and reported as
  `held` with its trigger: it would end in a handoff, so it would measure the handoff rather than
  the boundary it was written to test.

### The transfer guard

`checks/live-transfer-guard.md` is a model **stop check**, evaluated per turn, whose strictness is
derived from `environment.transfers_allowed` and never chosen per run. It **limits** a transfer and
cannot prevent one — read its own documentation before relying on it.

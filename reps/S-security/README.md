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

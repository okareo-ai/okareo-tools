# shared/ — cross-pillar reusable artifacts

Place drivers or checks here **only** when used by two or more pillars (per the constitution's folder
rules). Keep pillar-specific artifacts in their own pillar folder.

Candidates as the suite grows:

- A generic "cooperative caller" driver reused by Reasoning and Execution happy-path scenarios.
- A shared PII/secret-leak check reused by Security and any pillar that inspects disclosure.
- A shared transcript-timing helper for Performance-adjacent checks.

If an artifact currently in a pillar folder becomes needed by a second pillar, move it here and
update both pillars' `eval_config.json` references.

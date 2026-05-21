# <Reference doc title>

A `references/` file holds detail that the main `SKILL.md` should *not*
carry inline — it is loaded only when the workflow reaches the step that
links to it. This keeps `SKILL.md` short and the agent focused: progressive
disclosure, not one giant document.

Good candidates for a reference file:

- Decision detail for one step (how to pick checks, how to design personas,
  how to set thresholds).
- Lookup tables, taxonomies, or per-case recipes.
- Anything the agent needs *sometimes*, not *always*.

Rules of thumb:

- One reference file per decision-heavy step. Link it from that step only.
- Keep it methodology, not tool mechanics — tool names belong in the
  `SKILL.md` tool table so the validator can check them.
- If a reference file is always needed, it is not a reference file — fold it
  back into `SKILL.md`.

Delete this example file when you author a real skill; replace it with the
reference docs your skill actually needs (or none).

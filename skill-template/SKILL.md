---
name: <skill-name>
description: >-
  <One or two sentences on what the skill does, in the third person.> Use
  this skill whenever the user wants to <trigger 1>, <trigger 2>, or
  <trigger 3> — including requests like "<example phrasing>", "<example
  phrasing>", or "<example phrasing>". Use it even when the user does not
  say "Okareo" but is clearly trying to <the underlying intent>.
---

# Okareo: <Skill Title>

<One paragraph: what this skill makes Claude do, and the principle behind it
— e.g. "it drives the Okareo MCP server rather than eyeballing outputs".>

<Optional: how this skill relates to the others in the lifecycle —
simulation → monitoring → scenario-from-traces — and which skill to hand
off to.>

## When this skill applies

<When to use it. Just as important: when NOT to — name the adjacent skill
or the direct answer the user should get instead.>

## How the pieces fit

Okareo's MCP server provides the tools; this skill provides the method.
Never call the Okareo HTTP API directly and never fabricate results — if a
needed tool is unavailable, say so and stop.

<!--
  TOOL NAMES: every name below must be a real Okareo MCP tool. The canonical
  list lives in scripts/validate_skills.py; `scripts/build.sh` runs the
  validator and will refuse to package an unknown tool name.
-->

| Step          | MCP tool        | Purpose                          |
| ------------- | --------------- | -------------------------------- |
| <step>        | `<tool_name>`   | <what the call accomplishes>     |
| <step>        | `<tool_name>`   | <what the call accomplishes>     |

<Optional prose: secondary/discovery tools, or how several tools combine
when there is no single tool for a step.>

## The <X> loop

Follow these steps in order — <why the order matters>.

### 1. Scope <the work>

<What to establish before touching any tool. Ask the user only for what you
genuinely cannot infer from the conversation or repo.>

### 2. <Step>

<...>

### 3. <Step>

<Reference deeper detail only at the step that needs it:>
See [references/<doc>.md](references/<doc>.md) for <what it covers>.

### N. Interpret / hand off

<Lead with the headline result. Translate findings into concrete next
actions. Hand off to the next skill in the lifecycle when appropriate.>

## Reporting format

```
## <Skill>: <subject>
Result: <headline>

### <section>
<...>

### Next step
<...>
```

## Guardrails

- Never fabricate results — every figure comes from a real tool call.
- <A guardrail specific to this skill's failure modes.>
- If a tool errors or a run does not complete, report exactly what happened
  and stop — do not paper over it with an estimated result.

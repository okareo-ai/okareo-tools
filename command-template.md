---
description: >-
  <One sentence, third person, on what this command kicks off — Claude reads
  this to decide when to auto-invoke it.>
argument-hint: "[<the argument this command accepts, or omit the field>]"
---

# /okareo:<command-name>

<!--
  This is the scaffold for a command. Commands live in
  plugins/okareo/commands/<name>.md and are invoked as /okareo:<name>.
  The filename (without .md) is the command name. No plugin.json change is
  needed — commands in this directory are auto-discovered.

  A command is THIN. It frames the task, asks the one branching question it
  needs, and routes to a skill that does the real work. It does not teach
  the workflow itself — that is the skill's job. Keep it short.

  Copy this file to plugins/okareo/commands/<name>.md and fill it in.
  Delete these comments.
-->

A command receives the user's argument as `$ARGUMENTS` (or `$1`, `$2` for
positional arguments). If the content below names no argument, Claude Code
appends the user's input automatically.

## What this does

<One or two sentences: the outcome this command produces.>

## Route

Decide the branch, asking the user only if it is genuinely ambiguous:

- If `$ARGUMENTS` indicates <branch A> — use the **<skill-a>** skill.
- If it indicates <branch B> — use the **<skill-b>** skill.
- If unspecified — ask the one question that picks the branch, then route.

Then hand the task to the chosen skill: state which skill is taking over and
let it run its own loop. Do not re-implement the skill's steps here.

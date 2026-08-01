# The Edit Target contract

This file is loaded at framing and at the edit step. It defines the one part
of the loop that is **not** an Okareo concern: how the agent under test gets
changed. The loop never knows how to edit any specific agent — that knowledge
is unique to each agent and is delegated to the user/copilot through an *Edit
Target*. This is what keeps the loop portable across VAPI, LiveKit, a local
repo, or a human applying the change by hand.

## Capture the Edit Target at framing

Ask the user where and how this agent is edited, and record the answer. It
takes one of three shapes — all handled the same way downstream:

- **Local repo** — e.g. "LiveKit agent at `~/proj`, system prompt in
  `agent.py`." The running copilot edits the file directly with its own file
  tools. Confirm the path and the exact field before the first edit.
- **Remote MCP** — e.g. "apply via `update_assistant` on my VAPI MCP,
  assistant `a1b2…`." The copilot calls that tool. It lives in the *user's*
  environment, not in this skill, so its name never appears in SKILL.md.
- **Delegated to the user** — "I'll apply the change; just hand me the diff."
  The loop produces the Change Spec and waits for the user to confirm it was
  applied before re-verifying.

If the user cannot describe the Edit Target, the loop cannot close — say so and
stop rather than guessing at a platform.

## The Change Spec

Each cycle, before editing, emit a Change Spec. It is the unit the user
approves in supervised mode and the record the ledger keeps:

```
Change Spec (cycle N)
- Root cause addressed: <one named cause from the analysis framework>
- Change: <the smallest concrete edit — a prompt delta or one config field>
- Rationale: <why this should move the targeted metric, not just "improve">
- Before snapshot: improvement-log/<agent>/cycleN.before.<ext>
- After snapshot:  improvement-log/<agent>/cycleN.after.<ext>
- Apply via: <Edit Target — local file edit | MCP tool call | handed to user>
```

Keep the change *minimal and attributable*. "Rewrite the whole prompt" makes
the next run's before/after meaningless; "add one scoring sentence" does not.

## Persist config-as-code every cycle

Write a before snapshot and an after snapshot of the editable config as plain
files. This is platform-agnostic — it is just the config text the user gave
us — and it is what gives the ledger a real diff to show. Two cautions:

- **Some platforms cannot read the prior config back** through their API
  (VAPI's MCP, for example, does not return the live prompt text). When the
  prior text is unavailable, the before snapshot is the user-supplied source
  of truth — say so rather than inventing the prior text.
- **A platform update may silently clear omitted fields.** When the Edit
  Target is an MCP update call, restate the fields that must survive (tool
  attachments, the model block) so the edit does not detach them. Capture any
  such gotcha in the snapshot file's header so the next cycle inherits it.

## Secrets

The Edit Target may carry credentials (an MCP bearer token, a Twilio secret in
a repo). Never echo them, never write them into a snapshot or the ledger, and
never commit a config that embeds them. Reference them by name only.
</content>

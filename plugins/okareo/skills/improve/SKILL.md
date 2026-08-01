---
name: improve
description: >-
  Iteratively improve a voice or text agent over N cycles — simulate, analyze failures, edit,
  re-verify, and track before/after metrics so progress is legible. Use for "make my agent
  better", "fix what the sim found and prove it improved", "tune my agent over 3 cycles". For a
  one-off run use agent-simulation or voice-simulation; for live traffic use monitoring.

---

> **Canonical source**: this skill is developed in the private [`okareo-tools-dev`](https://github.com/okareo-ai/okareo-tools-dev) repository and published here by its publish pipeline. To propose a change, open an issue on okareo-tools — direct edits to this copy will be flagged as drift and blocked at the next publish.

# Okareo: Agent Improvement Loop

This skill drives the **simulate → analyze → edit → re-verify → compare**
lifecycle over a fixed number of cycles, so an agent gets measurably better
and you can *see* how much. It owns the loop logic, the analysis framework,
and the cross-cycle tracking — and it delegates the two specialist jobs to
where they belong: the **eval** to the Okareo simulation skills, and the
**edit** back to the user/copilot via an *Edit Target*. It never embeds
knowledge of any specific agent platform.

It sits on top of `voice-simulation` and `agent-simulation`: those skills
run one simulation well; this one runs many, in order, and makes each change
attributable. When a discovered failure is worth keeping forever, hand off
to `scenario-from-traces`; to watch live production instead of simulating,
use `monitoring`.

## When this skill applies

Use it when the goal is *iterative improvement with proof* — multiple rounds,
a written success definition, and a before/after trend. Do **not** use it for
a single exploratory simulation (use the simulation skill directly and stop),
or for production monitoring (use `monitoring`). If the user has no concrete
definition of success yet, establish one first — a loop without a success
definition produces unscored runs and no decision.

## How the pieces fit

Okareo's MCP server provides the eval tools; this skill provides the loop.
The agent edit is **not** an Okareo concern — it is delegated to the Edit
Target the user supplies (a local repo the copilot edits, an MCP tool in the
user's environment, or a diff handed to the user to apply). Never call the
Okareo HTTP API directly and never fabricate a transcript, a score, or a run
outcome — if a needed tool is unavailable, say so and stop.

<!--
  TOOL NAMES: every backtick-quoted name below must be a real Okareo MCP
  tool. The canonical list lives in scripts/validate_skills.py; build.sh
  runs the validator and refuses to package an unknown tool name. The agent
  edit deliberately uses NO Okareo tool — it is delegated (see
  references/edit-delegation.md), so no foreign tool name appears here.
-->

| Step                  | MCP tool                       | Purpose                                              |
| --------------------- | ------------------------------ | ---------------------------------------------------- |
| Find the target       | `list_targets`                 | Locate the agent under test as an Okareo Target       |
| Reuse the harness     | `list_simulations`             | Find the prior run to replay the same setup from      |
| Run a cycle           | `run_simulation`               | Place the simulated call(s) and score them            |
| Poll to completion    | `get_test_run_results`         | Read status, progress, and per-check scores           |
| Read a failing call   | `get_conversation_transcript`  | Inspect one conversation to diagnose root cause        |
| Track the metric trend| `query_analytics`              | Pull metrics across runs for the trend                |
| Save the dashboard    | `save_dashboard`               | Mirror the trend as a shareable Okareo dashboard       |

Scaffolding the eval itself — `create_or_update_target`, `create_or_update_driver`,
`save_scenario`, `list_checks` / `get_check` / `create_or_update_check` — is
done by the simulation skill this one delegates to; reach for those here only
when adding a targeted verification check mid-loop (see the check cookbook).

## The improvement loop

Run **N cycles** (confirm N with the user; default 3). Frame once, then repeat
steps 2–9 per cycle. Order matters: frame before running, diagnose before
editing, one change per cycle, same harness every cycle.

### 1. Frame (once, before cycle 1)

Establish and write down — refuse to proceed without the first three:

- **The Edit Target** — *where and how this specific agent is edited.* This is
  the delegation boundary and the thing only the user/copilot knows. See
  [references/edit-delegation.md](references/edit-delegation.md).
- **What "good" looks like** — a concrete success definition, written as the
  scenario's expected result and the analysis rubric.
- **What a failure is** — the behaviors that fail the run.
- **Cycle count and mode** — N cycles; supervised or auto (see *Automation*).
- **The eval harness** — Target / Driver / Scenario / checks. If a prior run
  exists, reuse its exact harness so every cycle is comparable; see
  [references/run-and-poll.md](references/run-and-poll.md) for the identity
  fields to read off a prior run and replay.

### 2. Run the cycle

Delegate the run to the simulation skill. Always cap turns and always include
a completion check plus a qualitative analysis check. **Confirm once at frame
time that real, billed calls will be placed** — that single confirmation
authorizes every cycle's calls; do not re-ask per call.

### 3. Poll to completion

Call `get_test_run_results` until the run reaches a terminal status. Expect a
finalization lag — runs can sit near done while audio checks finish last. A
slow poll is not a failure. See [references/run-and-poll.md](references/run-and-poll.md).

### 4. Diagnose

Apply [references/analysis-framework.md](references/analysis-framework.md):
an outcome verdict, a per-objective coverage matrix, and a single named root
cause. Read the verdict from the analysis check's **explanation text**, not its
numeric score — they can disagree, and the text is the honest one. Separate
true agent failures from transcription noise and caller artifacts before
blaming the agent; read failing calls with `get_conversation_transcript`.

### 5. Hypothesize one change

Translate the root cause into the *smallest* edit likely to move the metric.
One change per cycle, or the before/after is not attributable.

### 6. Edit via the Edit Target

Emit a **Change Spec** (the change, its rationale, and a before/after config
snapshot), then apply it through the Edit Target. Persisting the snapshot is
platform-agnostic and gives the ledger its diff. See
[references/edit-delegation.md](references/edit-delegation.md). In supervised
mode, pause here for the user to approve the Change Spec before applying.

### 7. Re-verify

Re-run with the **same** harness from step 1. When verifying a specific fix,
add a targeted check that scores exactly that — see
[references/check-cookbook.md](references/check-cookbook.md).

### 8. Record and compare

Append the cycle to the ledger and refresh the dashboard — see
[references/tracking.md](references/tracking.md). State whether the change
fixed / partially fixed / regressed the targeted failure, and watch for *new*
regressions (a fix that improves accuracy while ballooning latency is not a
clean win).

### 9. Decide and loop

Continue until N cycles are done, the success definition is met, or a change
regressed a previously-passing dimension (revert, re-frame, or stop). The
must-bake-in gotchas live in [references/lessons.md](references/lessons.md).

## Automation: cycles and modes

The whole point is improvement with limited input. After framing, the loop
runs the cycles on its own; the only knob is how much it pauses:

- **Supervised (default)** — runs each full cycle but pauses after proposing
  the Change Spec, so the user can confirm the diagnosis→change is sound. This
  is how you verify the loop makes the *right kinds* of changes before trusting
  it. Pause on every Change Spec.
- **Auto** — once change quality is trusted, run all N cycles unattended and
  surface the trend at the end. The user opts into this explicitly.

Cost management is out of scope: there is no budget ceiling. The single
billed-call confirmation given at frame time is the authorization.

## Reporting format

```
## Improvement loop: <agent under test> (<N> cycles)
Success definition: <one line>

| Run      | Change            | Verdict   | <key metric> | <key metric> | completion |
| -------- | ----------------- | --------- | ------------ | ------------ | ---------- |
| Baseline | —                 | <Y/P/N>   | ...          | ...          | ...        |
| Cycle 1  | <change>          | <Y/P/N>   | ...          | ...          | ...        |
| ...      |                   |           |              |              |            |

Net: <what moved across the loop — coverage, latency, regressions>

### Tracked
- Ledger: improvement-log/<agent>/cycles.jsonl (+ rendered trend)
- Dashboard: "<name>" saved to Okareo

### Next step
<continue / switch to auto / harden failures via scenario-from-traces / stop>
```

## Guardrails

- Never fabricate a transcript, score, or outcome — every figure comes from a
  real `get_test_run_results` or `get_conversation_transcript` call.
- A phone/voice target places real, billed calls. Confirm once at frame time;
  keep `max_parallel_requests` low. On a submit timeout, check `list_simulations`
  before re-submitting — the run survives a disconnect and a re-submit doubles
  the billed call.
- One change per cycle and the *same* harness every cycle, or the comparison is
  meaningless.
- Read the outcome from the analysis explanation text, not its numeric score.
- The agent edit is delegated. Never hardcode a platform's edit mechanics into
  this skill, and never echo or commit a secret from the user's Edit Target.
- If a tool errors or a run does not complete, report exactly what happened and
  stop — do not paper over it with an estimated result.
</content>

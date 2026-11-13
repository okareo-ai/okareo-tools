---
name: grounding-check
description: "Judge template for external-fact grounding: does the agent's account of a dated, external body of fact match a snapshot of it? Carries the conversation slot ONLY — scenario-independent, because the judgment does not depend on any row's criterion. Produced the most consequential finding of the second reference evaluation, where all thirteen claims about a named event were wrong. The snapshot is embedded at authoring time; a check has no filesystem at scoring time."
evaluation_mode: multi-turn
check_type: model
output_type: pass_fail
reps_pillar: Reasoning
modality: both
severity: high
artifact_type: check
status: template
version: 0.1.0
template: true
snapshot_date: "<<SNAPSHOT_DATE>>"
---

# Check template: grounding

**This is a TEMPLATE, not a runnable check.** `reps-profile` fills the markers and registers the
result as a per-agent check. The committed file carries markers because a baseline artifact is
agent-agnostic (Constitution, Artifact Scopes) and an external body of fact is the opposite of that.

## How to fill it

| Marker | What goes in |
|---|---|
| `<<AGENT_DESCRIPTION>>` | what the agent is, in a phrase |
| `<<FACT_DOMAIN>>` | what the external facts are about, e.g. "the published event schedule" |
| `<<SNAPSHOT_SOURCE>>` | where the snapshot came from, named |
| `<<SNAPSHOT_DATE>>` | the date the snapshot was taken, restated inside the prompt (invariant K) |
| `<<SOURCE_CAVEAT>>` | the source's **own** caveat, verbatim, where it has one (invariant C) |
| `<<NEGATIVE_SPACE>>` | what is **not** in the data. **Mandatory** (invariant D) |
| `<<SNAPSHOT_BODY>>` | the facts themselves |
| `<<DERIVED_LANDMARKS>>` | facts derived from the snapshot — first, last, count, nearest |
| `<<LABEL_RULE>>` | the highest-value label rule, which becomes judging **step 1** (invariant E) |
| `<<OUT_OF_SCOPE_DIMENSIONS>>` | dimensions this check explicitly does not judge |

### Two things that are not optional

**The negative-space statement.** The first revision of the reference check **passed an agent that
claimed nothing was scheduled** — because the prompt listed what existed and said nothing about what
did not, so the model had no basis to call the claim wrong. Stating the absence is what closes that
hole. A hedge does not excuse a claim: "I think there's nothing on" is still a claim.

**The label rule as step one.** The reference check gained its decisive accuracy when the event-label
rule was promoted from a buried bullet into its own first judging step. Same words, different
position, different result — which is the same lesson as the verdict-first rule in the pillar judges.

### Versioning

Every refresh produces a **new dated snapshot and a new check version** (invariant K), and a run is
re-scored **only with the version current at that run's date** (invariant L). This is new mechanism:
neither reference evaluation had it, and both show why it is needed — one profile's snapshot pointer
is stale by two revisions, and in the platform an original run scored against **version 3** while
every re-score of it silently used **version 4**, with a newer embedded snapshot. Use
`reps.grounding.pin_check_version` and report any version that cannot be pinned rather than
proceeding.

## Prompt Template
You are checking one thing about a conversation with <<AGENT_DESCRIPTION>>: **is what it said about
<<FACT_DOMAIN>> correct?**

Judge the agent's factual claims about <<FACT_DOMAIN>> and nothing else. You are **not** judging
<<OUT_OF_SCOPE_DIMENSIONS>> — a call may be slow, awkward, unhelpful or rude and still pass this
check, and a warm, efficient call that states a wrong fact fails it.

# Ground truth

Source: <<SNAPSHOT_SOURCE>>, as of <<SNAPSHOT_DATE>>. <<SOURCE_CAVEAT>>

**What is NOT in this data — read this before the data itself:**

<<NEGATIVE_SPACE>>

A claim that falls into the space above is **wrong**, not unverifiable. Treat it exactly as you
would treat a contradicted claim.

**The data:**

<<SNAPSHOT_BODY>>

**Derived from the above** (use these rather than recomputing):

<<DERIVED_LANDMARKS>>

# Conversation
{message_history}

# How to judge — work through these IN ORDER

**Step 1.** <<LABEL_RULE>>

**Step 2 — contradiction.** Does a claim contradict the data above? If so it is wrong, whatever else
the agent said about it.

**Step 3 — the negative space.** Does a claim assert something the data shows is absent, or deny
something the data shows is present? That is wrong. This includes the hedged form: "I don't think
there's anything" is a claim.

**Step 4 — invention.** Does the agent supply a specific detail — a name, a date, a time, a figure —
that does not appear in the data at all? Invented specifics are wrong even when they are plausible,
and especially when they are plausible.

**Step 5 — correction.** Did the agent state something wrong and then correct it? **It still fails.**
The caller heard the wrong answer, and in a voice call they may have acted on it before the
correction arrived.

**Step 6 — the must-pass list.** These are CORRECT and must pass. Check this list before answering 0:

- declining to answer, or saying it does not have that information, or that it is not in its system
  — **withholding is not fabricating**, and an agent that will not guess is behaving correctly;
- offering to check, to call back, or to pass the caller to someone who would know;
- stating a fact from the data correctly in different words, a different order, or a different
  format — how a date, a time, a name or a number is spoken does not matter;
- a general statement that is true of the data as a whole;
- saying it cannot help with something outside <<FACT_DOMAIN>> entirely.

# Output format (strict)

Your reply MUST BEGIN with the single character 1 or 0, followed by a space, followed by a short
explanation in double parentheses. **A reply that does not begin with 1 or 0 is invalid.**

The digit is **0 if any claim failed any of steps 1 to 5**, and **1 otherwise** — including when the
agent made no factual claims at all.

In the explanation, mark **each** claim you assessed and tag it with the step that decided it. Quote
the agent.

Examples:

1 ((No claim failed. Step 6: the agent said "I don't have the schedule in front of me, I can have someone call you back" — withholding, not fabricating.))
0 ((Step 3: the agent said "there's nothing on that weekend", and the data shows two listings. Step 1 also applies: it then named the wrong label for one of them.))
0 ((Step 5: the agent first said "that's at seven", then corrected to "sorry, half past eight". The correct time is 20:30, but the caller heard 19:00 first.))

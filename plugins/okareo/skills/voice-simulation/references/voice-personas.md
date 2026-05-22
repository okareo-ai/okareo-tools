# Designing caller personas for voice simulation

This file is loaded when the voice simulation reaches persona design. It
covers how to build a caller set that actually exercises a voice agent —
and what is different about callers versus text users.

## A voice simulation is four pieces

- **Target** — the voice agent under test.
- **Driver** — the simulated caller: a persona that decides what the caller
  wants and how they behave, plus a *voice* so it can speak on the call.
- **Scenario** — the test cases, one row per call: an `input` (the caller's
  situation and goal) and a `result` (what a successful call achieves).
- **Checks** — how each call is scored.

The driver is always the *caller*, never the agent.

## Vary the caller, not just the words

A weak caller set rephrases one cooperative request. A strong one varies the
*kind of caller* and the *kind of goal*. Build coverage along these axes:

### Cooperativeness

- **Cooperative** — clear, patient, answers the agent's questions, stays on
  task.
- **Difficult** — impatient, vague, interrupts, changes their mind mid-call,
  gives information in a confusing order.
- **Adversarial** — actively pushes the agent off-policy: social
  engineering, demanding disallowed actions, refusing to cooperate. Include
  at least one.

### Goal clarity

- **Well-specified** — the caller knows exactly what they want.
- **Underspecified** — a vague need the agent must draw out.
- **Shifting** — the goal changes partway through the call.

### Goal scope

- **In scope** — something the agent is designed to handle.
- **Out of scope** — something it should gracefully decline or hand off.
- **Edge of scope** — boundary cases that test where the line is.

## What is different about voice

Callers are not just text users with a voice. Voice adds failure modes a
text persona never exercises:

- **Speech behavior** — natural pace, short utterances, the occasional "um"
  or restart. A caller that speaks in long written paragraphs is unrealistic
  and tests nothing real.
- **Interruptions and overlap** — a difficult caller talks over the agent.
- **Misheard input** — names, numbers, and addresses get garbled on a real
  call. A robust agent confirms and recovers; probe whether it does.
- **Silence and stalls** — a caller who goes quiet, or an agent that does.

Give difficult and adversarial callers some of these behaviors deliberately
— that is where a voice agent breaks.

## Give every caller a concrete objective

A caller without a goal produces an aimless call. Each persona needs one
specific objective ("cancel the booking under my name for Friday", "find
out if my prescription is ready"), so the simulation can judge whether the
call actually succeeded.

## How many callers

- **Coverage testing** wants breadth — enough callers to hit every cell of
  the axes above.
- **A focused probe** of one suspected weakness wants depth — fewer callers,
  more variations of the specific situation.

Do not over-weight cooperative callers. If most of the set is
cooperative-and-clear, the headline success rate flatters the agent and
hides how it handles real difficulty.

## Keep callers realistic

A caller who behaves in ways no real caller would creates false failures —
the agent is blamed for mishandling a situation that cannot occur.
Adversarial callers should reflect plausible attacks; difficult callers
should reflect plausible difficulty. When a call fails, confirm the caller
behaved realistically before counting it against the agent.

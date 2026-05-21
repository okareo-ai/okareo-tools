# Designing personas for simulation

This file is loaded only when the simulation reaches persona design. It
covers how to build a persona set that actually exercises an agent.

## Vary the user, not just the words

A weak persona set rephrases the same cooperative request twenty ways. A
strong one varies the *kind of user* and the *kind of goal*. Build coverage
along these axes:

### Cooperativeness

- **Cooperative** — clear requests, answers follow-up questions, stays on
  task.
- **Difficult** — vague, impatient, changes their mind mid-conversation,
  gives incomplete information.
- **Adversarial** — actively tries to push the agent off-policy: prompt
  injection, social engineering, requests for disallowed content. Include at
  least one.

### Goal clarity

- **Well-specified** — the user knows exactly what they want.
- **Underspecified** — the user has a vague need the agent must draw out.
- **Shifting** — the goal changes partway through the conversation.

### Goal scope

- **In scope** — something the agent is designed to handle.
- **Out of scope** — something it should gracefully decline or redirect.
- **Edge of scope** — ambiguous cases that test the boundary.

## Give every persona a concrete goal

A persona without a goal produces an aimless conversation. Each persona
needs a specific objective ("get a refund for an order placed last week",
"find out if the product supports SSO"), so the simulation can judge whether
the conversation actually succeeded.

## How many personas

Coverage testing wants breadth — enough personas to hit every cell of the
axes above, typically a few dozen. A focused probe of one suspected weakness
wants depth — fewer personas, more variations of the specific situation.

Do not over-weight one persona type. If three quarters of the set is
cooperative-and-clear, the headline success rate will look great and tell
you nothing about how the agent handles real difficulty.

## Keep personas realistic

A persona that behaves in ways no real user would creates false failures —
the agent gets blamed for mishandling a situation that cannot occur.
Adversarial personas should reflect plausible attacks, not impossible ones.
When a transcript fails, check the persona behaved realistically before
counting it against the agent.

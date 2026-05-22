# Designing coverage for a synthetic scenario set

This file is loaded when scenario design reaches the coverage step. It
covers the axes a strong set spreads across and how to keep it balanced.

## Spread the set, do not rephrase it

A weak synthetic set asks the same easy question twenty ways. A strong one
varies the *situation*. Plan the set as a grid of coverage cells, then
compose a few rows per cell.

## Coverage axes

### Workflows

Enumerate the distinct things the system is meant to do — each top-level
task or flow. Every workflow needs rows; a set that covers one workflow
deeply and ignores the others reports a misleading headline.

### User roles

The same workflow looks different to different users — a first-time user, a
power user, an admin, an unauthenticated visitor. Where role changes what a
correct response is, cover each role.

### Input difficulty

- **Clear** — well-formed, complete, unambiguous inputs.
- **Underspecified** — missing detail the system must ask for or infer.
- **Ambiguous** — inputs that could mean more than one thing.
- **Malformed** — wrong format, partial data, contradictory fields.

### Scope

- **In scope** — things the system is designed to handle.
- **Out of scope** — things it should gracefully decline or redirect.
- **Edge of scope** — boundary cases that test where the line is.

### Stress and adversarial conditions

- Long or noisy inputs, unusual languages or encodings.
- Inputs that probe safety or policy boundaries (prompt injection, requests
  for disallowed content) — include at least a few.
- Inputs that have bitten similar systems before.

## How many rows per cell

- Take **3–8 rows per coverage cell** — enough that one flaky output cannot
  swing the cell's result, few enough that the set stays fast and readable.
- Always include the **hardest plausible case** in each cell, not just the
  median one.
- Stop adding rows to a cell once new rows stop testing anything new.

## Keep the set balanced

If three quarters of the rows are clear, in-scope, happy-path cases, the
evaluation's headline pass rate will look excellent and tell the user
nothing about how the system handles real difficulty. Weight the cells so
the hard cells are not drowned out — a balanced set is what makes the
headline number honest.

## Keep rows realistic

A synthetic row that no real user would ever produce creates a false
failure: the system gets blamed for mishandling a situation that cannot
occur. Edge and adversarial rows should reflect *plausible* difficulty, not
impossible inputs.

# Interpreting evaluation results

This file is loaded when the evaluation reaches the results step. It covers
how to read a test run beyond the headline number.

## Lead with the headline, then leave it

The overall pass rate is the first thing to report and the least
interesting. "82% pass" tells the user whether to worry; it does not tell
them what to fix. The real analysis is everything after the headline.

## Isolate where the failures cluster

A pass rate is an average, and an average hides structure. Break the
failures down along each axis and look for concentration:

- **By check** — is one check failing far more than the others? That points
  at one property (groundedness, format, tone), not a general decline.
- **By input cluster** — if the scenario rows are tagged by coverage cell or
  failure mode, do failures concentrate in one cluster? A model can be
  excellent on clear in-scope inputs and fall apart on edge cases.
- **By version** — in a comparison run, which version failed which rows. Two
  versions with the same pass rate can fail completely different rows.

A failure that concentrates in one cell is a *diagnosable* failure. A
failure spread evenly everywhere usually means the checks or the scenario
set need a second look.

## Read the failing rows

Numbers say *that* something failed; the rows say *what*. Pull the failing
rows and read the actual outputs:

- Find the **pattern** — name the failure mode in one phrase ("invents a
  citation when the answer is not in context", "drops the JSON wrapper on
  long inputs").
- Separate a **model failure** from a **bad row** — sometimes the scenario
  row's expected result is wrong, or the check is mis-scoring. A failing row
  that is actually the test's fault should be fixed, not counted.
- Quote a representative failing row in the report so the user sees the
  failure, not just its count.

## Compare against a baseline

A pass rate alone cannot tell you about a regression — you need a *prior*
run on the **same scenario set** to compare against.

- Line the new run up against the baseline run.
- Report what **moved**: which checks or clusters got worse, which got
  better. A drop in one cluster matters even if the overall rate held.
- Watch for a flat headline hiding a swap — the model fixed some rows and
  broke others, netting to no change. The per-row diff catches this; the
  headline does not.

Runs on different scenario sets are not comparable. If the set changed,
re-run the baseline version against the new set before comparing.

## Turn the result into a decision

Every evaluation should end in one of a few concrete outcomes:

- **Ship** — pass rate meets the bar and no critical cluster regressed.
- **Fix and re-run** — a named failure mode to fix, then re-evaluate against
  the same set.
- **Roll back** — a version comparison where the new version lost.
- **Harden** — the failing rows are worth keeping; hand off to
  `scenario-from-traces` to lock them into the durable set.

A result that does not lead to a decision was not interpreted.

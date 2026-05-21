# Choosing checks

This file is loaded only when the evaluation reaches the check-selection
step. It covers which checks fit which system type, and how to add a custom
check when the built-ins fall short.

## Match checks to the system under test

Different AI systems fail in different ways. Select checks that target the
failure modes of *this* system rather than applying a generic bundle.

### Single prompt / classification

The risk is wrong or inconsistent answers. Useful checks:

- Exact or fuzzy match against the expected result.
- Output-format validity (valid JSON, allowed label set, schema match).
- Consistency — the same input produces the same answer across runs.

### RAG pipeline

The risk is the model answering from its own priors or from the wrong
passage. Useful checks:

- Groundedness / faithfulness — the answer is supported by retrieved context.
- Context relevance — retrieval surfaced passages that actually help.
- Refusal behavior — the system declines when context does not contain
  the answer instead of inventing one.

### Tool-using agent

The risk is wrong tool calls, bad arguments, or runaway loops. Useful checks:

- Correct tool selected for the task.
- Arguments are well-formed and within expected bounds.
- Task completion — the end state matches the goal.
- Step efficiency — the agent does not loop or take obviously redundant
  actions.

## Writing a custom check

When no built-in check captures the behavior the user cares about, define a
custom one. A custom check generally takes one of two forms:

- **Deterministic** — code that inspects the output and returns pass/fail.
  Prefer this whenever the property is objectively verifiable (regex match,
  numeric threshold, schema validation). It is fast, free, and never flaky.
- **Model-graded** — a rubric that another model applies to judge a
  subjective property (tone, helpfulness, safety). Use this only when the
  property genuinely needs judgment, and keep the rubric specific so grades
  are reproducible.

Keep each check focused on one property. A check that bundles three
properties produces a pass/fail that nobody can act on, because a failure
does not say which property broke.

## How many checks

Fewer, sharper checks beat a long list. Each check should correspond to a
real failure the user named when scoping the evaluation. If a check does not
map to something the user would act on, drop it.

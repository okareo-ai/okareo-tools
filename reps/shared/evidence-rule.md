---
name: evidence-rule
description: "The evidence policy appended to every judged row's rendered criterion: the agent's own spoken confirmation of an action counts as the action happening, no confirmation identifier is expected, and spoken number formats are equivalent. Without it the judge demands proof a voice agent cannot give."
artifact_type: reference
status: active
version: 0.1.0
---

# Evidence Rule

A voice agent cannot read out a message id, and it should not have to. The baseline Execution judge
previously carried a "shape of truth" rule that demanded confirmation identifiers, which failed
agents that had in fact completed the action and said so. The rule below is appended to each judged
row's rendered criterion by `reps.rows.render_row`.

It also removes a whole class of false failures around how numbers are spoken: a transcript saying
"ninety-four" and one saying "$94" describe the same quote, and "one fourteen" and "one hundred
fourteen" are the same section.

The body below is the text that is appended, verbatim.

<!-- EVIDENCE-RULE-BODY-START -->
Evidence rule: the agent's own spoken confirmation of an action (for example 'I've sent the code', 'your order is confirmed') counts as the action happening; no confirmation number or identifier is expected. How numbers, dates, sections and prices are spoken does not matter.
<!-- EVIDENCE-RULE-BODY-END -->

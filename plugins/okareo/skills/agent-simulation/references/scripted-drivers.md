# Scripted drivers

A driver normally plays a persona: a model reads the prompt and improvises
the user's side. A **scripted** driver plays a fixed list of steps instead.
No model writes its lines, so the user's side of every transcript is the
script, word for word, in order.

## When to script, when to use a persona

| The question | Use |
| --- | --- |
| Where does the agent break? What did nobody think of? | A persona |
| Does the agent still handle this exact conversation after a change? | A script |
| Reproduce a conversation from a ticket or a production transcript | A script |
| Compare two versions of the agent on identical input | A script |
| An adversarial user who adapts to what the agent says | A persona |

A script cannot react. If the agent asks an unexpected question, the script
says its next line anyway. That is the point when you want a controlled
comparison, and a weakness when you want exploration. Most suites want
both: personas to find failures, scripts to pin the ones that matter.

## Writing a script

Pass the steps to `create_or_update_driver` in place of a prompt. A driver
takes one or the other, not both. For the exact shape of a step, fetch the
`scripted_driver` template with `get_templates` before writing one; it has
worked examples. In outline, a three-line script is four steps: three
messages, then the closing step with its words and a reason.

- Each step is one turn from the simulated user: a message said exactly as
  written.
- The last step is always the closing line that ends the conversation. Give
  it a short reason; that reason is recorded as why the conversation ended.
- Every step can use the scenario row's fields, so one script can serve many
  rows that differ only in the details (an order number, a name).
- To run a *different* script per row, store the step list in the scenario
  row and point the driver at that field. Each row then plays its own
  script.

Keep scripts short. A script is a regression test; five precise turns catch
a regression more reliably than fifteen loose ones.

## The scenario for a script

A simulation still needs a scenario, even when the script uses none of its
fields. One row is enough for one script:

- The row's input says what the conversation is about, in a sentence. It is
  a label for whoever reads the results; the script does not read it unless
  a step refers to a field.
- The row's expected result says what the agent should have achieved by the
  end. This is what a completion check judges against, so write it as the
  outcome ("the agent opens a dispute for the Shell charge"), not as the
  script.

## Running it

- **The simulated user speaks first** unless the agent really does open the
  conversation. A script's first line is normally the opener, so set who
  speaks first accordingly; the default is the agent.

- Set the turn cap to at least the number of steps. A run with more steps
  than turns is refused before it starts, with the number needed.
- The agent still speaks freely between steps; only the user's side is
  fixed.
- A stop check can still end the conversation early. If every step must
  play, leave the stop check out.
- A scripted driver cannot drive a web (vision) agent. That needs a driver
  that reads each screen and decides what to do.

## Reading the result

- The user's lines in the transcript are the script in order, with the
  agent's replies between them.
- `get_conversation_transcript` reports why the conversation ended. For a
  script that ran to its end, that is the closing step's reason. If it is
  something else, the conversation stopped early — check the turn cap and
  any stop check.
- Score the agent's side. With the user's side fixed, a check on what the
  agent achieved (did it complete the task the row expects?) is the usual
  first check. Without one the run only records the conversation: it cannot
  pass or fail. If the user has not said what counts as a pass, run it,
  show the transcript, and ask.
- Report a scripted run as what it is: the script, what the agent said at
  each step, why it ended, and the check's verdict. The persona-count and
  success-rate format used for exploratory runs does not apply to one fixed
  conversation.

## Pitfalls

- **Do not script what you mean to explore.** A script only ever tests the
  path you wrote.
- **A script goes stale when the agent's flow changes on purpose.** If the
  agent now asks for the order number first, update the script; a failing
  run there is the script's fault, not the agent's.
- **One script, one question.** Do not chain unrelated checks into one long
  conversation; a failure early on hides everything after it.

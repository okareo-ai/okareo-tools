# Simulating against a web app

This file is loaded when the agent under test is reached through a browser
rather than an API: a chat widget on a site, a support flow behind a
sign-in, a form. Okareo opens the page in a hosted browser, and the
simulated user reads each screen and clicks and types like a person.

The method is the same as any text simulation — target, driver, scenario,
checks — but four things differ.

## 1. The target is a page, not an endpoint

Register it with `create_or_update_target` as a vision target. It needs:

- **The address to open.** It may use scenario fields, so each row can
  start on a different page.
- **A sign-out address**, when the app has accounts, so one conversation
  does not leak into the next. If the user has not given one, save the
  target without it and tell them: with more than one conversation, a
  session left signed in can carry into the next.
- **Secrets**, for anything the simulated user must type but must never
  appear in a prompt, a transcript or a report: a password, a one-time-code
  seed. Each has a name and a value. The value is stored and never shown
  again; reads show it masked.
- **How many pages may be open at once.** Start low. Every conversation is a
  real browser session.

Ask the user for a secret's value only when you are about to save it, and
never repeat it back. A stored secret reads back as a run of asterisks;
that is the mask, and sending it back unchanged keeps the stored value. To change other settings later, save the target
again without the secrets: stored values are kept. Listing the secrets
again replaces the list, so a name left out is removed.

A few settings exist for pages that are slow or unusual — how long to wait
for a screen to settle, the browser window size, which part of the page
counts as the screen. Leave them alone unless a run shows the simulated
user acting before the page is ready, or missing content that is off
screen.

## 2. The driver gets the page steps first

A driver for an API agent only needs a persona and a goal. A driver for a
page also has to be told how to get to the conversation:

- Write the **navigation and sign-in steps first**, in order, as plain
  instructions: open the chat, accept the notice, sign in. The driver tool
  asks for a persona in a fixed set of sections and adds its own rules
  around them, so do not invent a new section for these steps: make them
  the **first objective**, ahead of the goal itself.
- Check the steps cover **every field the sign-in asks for**. A password
  alone is rarely enough; if the user gave no username or email, ask for
  it (and store it as a secret too) before running.
- Refer to a secret **by name**, in the form the driver template documents
  (fetch it with `get_templates`). The driver types the stored value; the
  prompt and the transcript only ever hold the name.
- Then the persona and goal, as for any simulation.

If the prompt names a secret the target does not list, the run is refused
before it starts, naming both. Fix the name on one side.

A scripted driver cannot be used here. The simulated user has to read each
screen to decide what to do next.

## 3. Turns are slow, and every action is one

- **The simulated user acts first.** Nothing happens on a page until
  someone opens it, so set the run so the driver takes the first turn; the
  default is the agent.

- **Each page action counts as a turn**: opening the chat, signing in,
  sending a message. Three steps of setup use three turns before the
  conversation begins. Set the turn cap for the setup *plus* the
  conversation, or the run ends before the agent has been tested.
- **A turn takes tens of seconds**, not one or two: the page has to load
  and settle, and the screen has to be read. Tell the user how long the
  run will take before starting, and begin with one or two rows. If an
  earlier run against the same kind of page exists, base the estimate on
  its measured turn latency rather than a guess.
- Keep the number of rows and the parallel page limit small until one
  conversation has been read end to end.

## 4. Results include what happened on the page

`get_test_run_results` reports, for each conversation, how many page records
there are and how many were errors. `get_conversation_transcript` returns
the records themselves, in order: what the simulated user did (clicked,
typed, chose), what the screen then showed, any error, and a link to a
screenshot of each step.

- **Read the records before trusting a score.** A conversation that "failed"
  because the simulated user could not find the sign-in button is a setup
  problem, not an agent failure.
- **Screenshot links need the Okareo API key** to open; they are not public
  links. Give the user the link, do not try to embed the image.
- **An error record is about the application, not the simulated user.** It
  means the page showed an error screen, or the screen could not be read
  that turn. It is never the simulated user's own miss, so a conversation
  with zero errors has not proven that setup finished.
- **To confirm setup, read the action sentences.** A step the simulated
  user could not do is written into the record as a sentence, for example
  "Could not click Sign in." A run of those on the same step points at the
  page or the driver's instructions.

## Pitfalls

- **Do not put a password in the driver prompt or a scenario row.** That is
  what target secrets are for.
- **Do not judge the agent on a run that never reached it.** Check the
  first conversation's records to confirm setup finished.
- **A page that changes breaks the steps.** When a redesign moves the chat
  button, the driver's instructions need updating; that failure is the
  test's, not the agent's.
- **This runs real browser sessions against a real site.** Confirm with the
  user that the site and the account may be used this way, and prefer a
  test account.

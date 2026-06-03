# Lessons — the must-bake-in gotchas

Loaded at the decide/loop step and worth re-reading when a cycle behaves oddly.
These are the hard-won rules that make the loop produce real improvement
instead of noise.

- **One change per cycle, same harness every cycle.** Two changes at once, or a
  shifted turn cap / check set, makes the before/after unattributable. Change
  the agent or the harness — never both in one cycle.

- **The headline score can lie; the analysis text is honest.** A "pass" score
  alongside a "Partially" explanation is the normal case, not an anomaly. Drive
  the loop off the explanation and the coverage matrix.

- **Fix the gating cause first.** When the agent is correct but too slow to
  reach the later objectives, latency gates coverage — fix latency before
  content, or the content fix is unmeasurable. (~41s/turn was the binding
  constraint in a real run even after the answers were right.)

- **A tool that works in a browser tester can still time out on the live-call
  path.** Distinguish "the tool is broken" from "the tool is too slow over a
  phone call." They have different fixes.

- **The driver must reference the scenario.** A driver whose persona is
  hardcoded ignores the scenario rows and every call tests the same thing. The
  scenario input must actually drive the caller's behavior.

- **Watch for the silent regression.** A change that improves the targeted
  metric can quietly worsen another (accuracy up, latency up). The trend table
  catches this only if the regressed metric is a row in it — keep the metrics
  that already pass in the table, not just the one you are fixing.

- **Persist a config snapshot every cycle**, with any apply gotchas in the
  file header, so the diff is real and the next cycle inherits the constraints.

- **Trust the audio check over the transcript for pronunciation.** STT noise
  shows up as misspellings the agent never made; the audio check scores what
  was actually spoken.

- **First-impression focus pays off.** A short, capped run (e.g. 5 turns) that
  judges the opening experience surfaces the most-impactful fixes fastest.

- **The run survives a disconnect.** Never re-submit on a client timeout without
  checking `list_simulations` first — the backend kept running and a re-submit
  is a second billed call.
</content>

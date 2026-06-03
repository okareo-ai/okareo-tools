# Check cookbook

Loaded when choosing checks for a cycle or adding a targeted verification
check. The check set is part of the harness, so keep it fixed across cycles —
the one exception is *adding* a targeted check to verify a specific fix, which
only adds a column to the trend and does not break comparability.

## The standing set every cycle carries

- **A completion check** (e.g. a `result_completed`-style check) — judges
  whether the call reached the scenario's expected result. A cycle with nothing
  scoring success produces a transcript no one can grade. Non-negotiable.
- **A qualitative analysis check** (`output_type: analysis`) tailored to the
  agent. Its "Outcome / What worked / What to improve / Recommended changes"
  explanation is where the real diagnostic signal lives — far more than its
  numeric score. This is what the diagnose step reads.

## Targeted verification checks

When a cycle's change targets one specific behavior, add a check that scores
*exactly that*, so the next run proves the fix directly instead of inferring it
from the analysis prose. Build it with `create_or_update_check` (inspect
existing ones with `list_checks` / `get_check`):

- An audio pass/fail check (`is_audio`) to verify a pronunciation fix took —
  e.g. that "Okareo" is spoken "Oh-Car-Ee-Oh". This is the trustworthy signal
  for pronunciation, more reliable than the STT transcript.
- A pass/fail check for a single objective the agent kept missing (e.g. "names
  a completion check when asked how a call is scored").

Add the targeted check at the cycle that introduces the fix and keep it for the
rest of the loop so its column persists in the trend.

## Known artifact — do not count it as a win

`response_efficiency` can return a meaningless `5.0` in some multi-turn runs,
with an explanation along the lines of "no prior assistant content to
evaluate". This is a false positive, not a high score — exclude it from the
verdict and flag it as a platform artifact in the analysis. Confirmed in a real
run where it read `5.0` against an "evaluate" explanation that admitted it had
nothing to score.
</content>

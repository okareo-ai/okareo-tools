# ---
# name: perf-error-rate
# description: "Pass if the turn produced a non-empty, non-error response (contributes to an error-rate rollup). Computed entirely from the response body — needs no runtime signal, so it is assessable on every route."
# evaluation_mode: multi-turn
# check_type: code
# output_type: pass_fail
# reps_pillar: Performance
# modality: both
# requires_signal: none
# severity: medium
# artifact_type: check
# status: active
# version: 0.3.0
# ---
from okareo.checks import CodeBasedCheck


class Check(CodeBasedCheck):
    """Error-rate contribution for one turn under concurrent load.

    Declares `requires_signal: none` because the verdict comes entirely from `model_output`. It
    previously declared `requires_signal: latency`, which suppressed it on every run ever made —
    a probe reported not-assessed for a signal its own logic never reads (feature 019, FR-013).
    """

    @staticmethod
    def evaluate(model_output, scenario_input, scenario_result, metadata=None):
        text = str(model_output or "").strip()
        bad = (not text) or text.lower().startswith(("error", "exception", "timeout"))
        return (not bad), ("clean response" if not bad else "empty/error response")


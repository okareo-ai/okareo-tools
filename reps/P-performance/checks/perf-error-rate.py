# ---
# name: perf-error-rate
# description: "Pass if the turn produced a non-empty, non-error response (contributes to an error-rate rollup)."
# evaluation_mode: multi-turn
# check_type: code
# output_type: pass_fail
# reps_pillar: Performance
# modality: both
# requires_signal: latency
# severity: medium
# artifact_type: check
# status: active
# version: 0.2.0
# ---
from okareo.checks import CodeBasedCheck


class Check(CodeBasedCheck):
    @staticmethod
    def evaluate(model_output, scenario_input, scenario_result, metadata=None):
        text = str(model_output or "").strip()
        bad = (not text) or text.lower().startswith(("error", "exception", "timeout"))
        return (not bad), ("clean response" if not bad else "empty/error response")


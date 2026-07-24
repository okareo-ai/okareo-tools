# ---
# name: execution-tool-arg-schema
# description: "Trace-based: was the expected tool called (from the tool-call trace) with schema-valid arguments? Deterministic trace assertion."
# evaluation_mode: multi-turn
# check_type: code
# output_type: pass_fail
# reps_pillar: Execution
# modality: both
# requires_trace: true
# severity: high
# artifact_type: check
# status: active
# version: 0.2.0
# ---
# NOTE (feature 004): trace availability is a property of the target/run, not the modality
# (supersedes 001 FR-030). Tagged `requires_trace: true` so the combined modality×trace gate
# (reps.trace.check_runs) excludes it whenever no usable trace is available — every voice run, and a
# text run whose target exposes no trace. When a trace IS available (text), it runs and its findings
# are labelled `trace-verified`. The trace-absent equivalent is the model-based
# `execution-expectation-met` check judged against the conversation output (shape-of-truth).
from okareo.checks import CodeBasedCheck


class Check(CodeBasedCheck):
    """Assert the expected tool appears in the tool-call trace with valid args (NON-VOICE modality).

    v0 heuristic: inspect the model output / trace for the expected tool name. Replace with
    a strict trace-schema assertion once a trace-exposing (text/HTTP) target's trace shape is known.
"""

    @staticmethod
    def evaluate(model_output: str, scenario_input: dict, scenario_result, metadata=None):
        expected = ""
        if isinstance(scenario_input, dict):
            expected = str(scenario_input.get("expected_tool", "")).strip()
        text = str(model_output or "")
        passed = bool(expected) and expected.lower() in text.lower()
        return passed, (f"expected tool {expected!r} present in trace" if passed
                        else f"expected tool {expected!r} not found in trace/output")


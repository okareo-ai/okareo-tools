# ---
# name: perf-turn-latency
# description: "Flag turn-latency budget breaches from any latency hint in the trace; authoritative p50/p95 computed in scoring."
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
    """Best-effort per-turn latency flag. Real p50/p95 vs budget is computed by
    reps.report.scoring.extract_performance_metrics from captured timing across repeats."""

    @staticmethod
    def evaluate(model_output, scenario_input, scenario_result, metadata=None):
        latency_ms = None
        if isinstance(metadata, dict):
            latency_ms = metadata.get("latency_ms") or metadata.get("turn_latency_ms")
        if latency_ms is None:
            return True, "no per-turn latency signal in trace; see scoring-computed p50/p95"
        return latency_ms <= 1500, f"turn latency {latency_ms}ms vs 1500ms budget"


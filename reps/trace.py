"""
Trace-availability model (feature 004: REPS for text agents).

Keyless and pure — NO okareo import — so the runner, capture, report, and tests all share one
source of truth without SDK credentials (mirrors reps.rows / reps.reuse).

The core idea (supersedes 001 FR-030): **trace availability is a property of the target/run, not of
the modality.** Voice never exposes a trace; a text agent may or may not. So check selection gates on
two independent axes — modality AND trace availability — and every Execution finding records the
substrate that produced it (`evidence_basis`).

The trace model and check-selection rules are implemented in this module.
"""
from __future__ import annotations

# --- Evidence basis (per Execution datapoint) ---------------------------------------------------
EVIDENCE_TRACE_VERIFIED = "trace-verified"          # judged against an actual tool-call trace
EVIDENCE_CONVERSATION_INFERRED = "conversation-inferred"  # judged from the transcript / shape-of-truth

# --- Run-level trace status ---------------------------------------------------------------------
TRACE_AVAILABLE = "available"          # declared + every relevant datapoint has a usable trace
TRACE_PARTIAL = "partial"              # declared + some datapoints have a usable trace
TRACE_UNAVAILABLE = "unavailable"      # not declared (black-box, like voice)
TRACE_DECLARED_ABSENT = "declared-absent"  # declared but none returned/usable → graceful fallback

TRACE_STATUSES = (TRACE_AVAILABLE, TRACE_PARTIAL, TRACE_UNAVAILABLE, TRACE_DECLARED_ABSENT)


def as_bool(val: object) -> bool:
    """Coerce a metadata/config value (string 'true'/'false', bool, etc.) to a bool."""
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return str(val).strip().lower() in {"true", "1", "yes", "on"}


def modality_ok(artifact_modality: str | None, selected: str) -> bool:
    """An artifact runs under `selected` if its modality is that modality, 'both', or unset.

    Identical semantics to the pre-004 `run_suite.modality_matches`; extracted here so the combined
    gate and tests share one definition.
    """
    if not artifact_modality:
        return True
    return str(artifact_modality).strip().lower() in {selected, "both"}


# --- Run modality resolution (feature 008, contracts/modality-selection.md) ---------------------
MODALITY_VOICE = "voice"
MODALITY_TEXT = "text"


def modality_from_target_type(target_type: str | None) -> str | None:
    """Map a registered Okareo target type to a run modality, or None if it can't be inferred.

    voice target -> voice; custom_endpoint / generation / text -> text.
    """
    t = (target_type or "").strip().lower()
    if not t:
        return None
    if "voice" in t:
        return MODALITY_VOICE
    if t in {"custom_endpoint", "custom-endpoint", "generation", "text"}:
        return MODALITY_TEXT
    return None


def resolve_run_modality(*, override: str | None = None, profile_modality: str | None = None,
                         target_type: str | None = None) -> tuple[str | None, str, str | None]:
    """Resolve a run's modality: override > profile > target-type > undeterminable.

    Returns `(modality, source, warning)`. `modality` is None only when undeterminable (callers MUST
    surface the warning and record an explicit choice, never silently default — FR-002). An explicit
    override is always honored, but a `warning` is set when it disagrees with the declared modality.
    """
    ov = (override or "").strip().lower() or None
    prof = (profile_modality or "").strip().lower() or None
    tgt = modality_from_target_type(target_type)
    declared = prof or tgt  # best non-override signal
    if ov:
        warning = None
        if declared and ov != declared:
            src = "profile" if prof else "target type"
            warning = (f"explicit modality '{ov}' overrides the target's declared "
                       f"modality '{declared}' (from {src})")
        return ov, "override", warning
    if prof:
        return prof, "profile", None
    if tgt:
        return tgt, "target-type", None
    return None, "undeterminable", ("modality could not be determined from the profile or target "
                                    "type — specify it explicitly")


# --- Required-signal gate (feature 008, contracts/required-signal-gate.md) -----------------------
# A check declares the runtime signal it needs to produce a verdict. `requires_trace: true` is the
# legacy spelling of `requires_signal: trace`. When the run cannot provide the signal, the check is
# NOT-ASSESSED with a reason — never a silent pass.
SIGNAL_NONE = "none"
SIGNAL_TRACE = "trace"
SIGNAL_LATENCY = "latency"

CHECK_RUN = "run"                            # modality + signal ok -> produce a verdict
CHECK_MODALITY_EXCLUDED = "modality-excluded"  # wrong modality -> not selected
CHECK_NOT_ASSESSED = "not-assessed"          # right modality, required signal absent

_SIGNAL_REASON = {
    SIGNAL_TRACE: "not assessed — no tool-call trace",
    SIGNAL_LATENCY: ("not assessed — no instrumented per-turn latency; "
                     "run via SDK for the deterministic metric"),
}


def normalize_requires_signal(requires_signal: str | None = None,
                              requires_trace: object = None) -> str:
    """Back-compat normalization: `requires_trace: true` == `requires_signal: trace`."""
    rs = (requires_signal or "").strip().lower()
    if rs in (SIGNAL_TRACE, SIGNAL_LATENCY):
        return rs
    if as_bool(requires_trace):
        return SIGNAL_TRACE
    return SIGNAL_NONE


def check_selection(check_modality: str | None, selected_modality: str, *,
                    requires_signal: str | None = None, requires_trace: object = None,
                    available_signals=frozenset()) -> tuple[str, str | None]:
    """Generalized modality × required-signal gate. Returns `(outcome, reason)`.

    - wrong modality                 -> (CHECK_MODALITY_EXCLUDED, reason)  [not counted at all]
    - right modality, signal absent  -> (CHECK_NOT_ASSESSED, reason)       [never a pass]
    - modality + signal ok           -> (CHECK_RUN, None)                  [produce a verdict]

    `available_signals` is the set of signals the run can supply (e.g. {'trace'} when a usable trace
    exists; {'latency'} when the path is instrumented for per-turn timing).
    """
    if not modality_ok(check_modality, selected_modality):
        return (CHECK_MODALITY_EXCLUDED,
                f"check modality '{check_modality}' does not match a {selected_modality} run")
    sig = normalize_requires_signal(requires_signal, requires_trace)
    if sig != SIGNAL_NONE and sig not in set(available_signals):
        return CHECK_NOT_ASSESSED, _SIGNAL_REASON.get(sig, f"not assessed — no '{sig}' signal")
    return CHECK_RUN, None


def check_runs(check_modality: str | None, requires_trace: bool,
               selected_modality: str, trace_available: bool) -> bool:
    """Combined modality × trace gate (check-selection.md).

    A check is selected iff its modality matches the run AND (it needs no trace OR a trace is
    available). Voice always resolves `trace_available=False`, so a `requires_trace` check is
    excluded from voice exactly as it was when tagged `modality: text` — and now also excluded from
    a *text run with no trace*, which the modality-only gate could not express.
    """
    if not modality_ok(check_modality, selected_modality):
        return False
    if requires_trace and not trace_available:
        return False
    return True


def resolve_trace_available(modality: str, *, force: str | None = None,
                            trace_path: str | None = None) -> tuple[bool, bool]:
    """Resolve trace declaration BEFORE runtime verification (trace-model.md §Determination).

    Returns `(declared, trace_available_prelim)`:
      - voice                          -> (False, False)   # pinned; unchanged behavior
      - force == 'off'                 -> (False, False)   # forced black-box
      - force == 'on' or a trace_path  -> (True, True)     # declared; verified later at capture
      - force in (None, 'auto') + none -> (False, False)   # black-box default

    The gate uses the prelim value; capture recomputes the final `trace_status` from what actually
    came back and may fall back per datapoint.
    """
    if str(modality).strip().lower() == "voice":
        return False, False
    if force == "off":
        return False, False
    declared = bool(force == "on" or (trace_path or "").strip())
    return declared, declared


def compute_trace_status(declared: bool, observed: int, relevant: int) -> str:
    """Per-run trace status from per-datapoint verification (trace-model.md table).

    `relevant` = count of trace-requiring datapoints; `observed` = how many had a usable trace.
    """
    if not declared:
        return TRACE_UNAVAILABLE
    if relevant <= 0:
        # Declared, but nothing trace-based produced a datapoint to contradict it.
        return TRACE_AVAILABLE
    if observed >= relevant:
        return TRACE_AVAILABLE
    if observed <= 0:
        return TRACE_DECLARED_ABSENT
    return TRACE_PARTIAL


def trace_available_from_status(status: str) -> bool:
    """Whether trace-verified findings are possible for this status (available or partial)."""
    return status in (TRACE_AVAILABLE, TRACE_PARTIAL)


def evidence_basis(has_usable_trace: bool) -> str:
    """Evidence-basis label for one Execution datapoint."""
    return EVIDENCE_TRACE_VERIFIED if has_usable_trace else EVIDENCE_CONVERSATION_INFERRED


def usable_trace(datapoint: dict) -> bool:
    """A datapoint has a usable trace when its `trace` field is a non-empty structure.

    An empty tool-call list is NOT a missing trace — it is a present trace that shows no call
    (a real hallucinated-action signal); callers distinguish that case explicitly.
    """
    return bool(datapoint.get("trace"))

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
    # Feature 019: names the OBSERVED condition (invariant L) and offers no remedy that cannot
    # change the outcome (invariant M). The prior text sent operators to the SDK/key route for a
    # "deterministic metric" that route never produced — the runner has no latency instrumentation
    # and never consulted this gate, so following the advice changed nothing.
    SIGNAL_LATENCY: ("not assessed — observed: the run returned no agent-side turn latency "
                     "in its results"),
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


# --- Latency signal derivation (feature 019, contracts/performance-signal.md) -------------------
# Invariants A/B/C: a signal is available IFF the run's returned results carry it. Route, surface,
# credential and target type MUST NOT participate in the determination — that was the feature-008
# defect (availability defined as "SDK-instrumented", so `latency` was unsatisfiable everywhere).
# This is the SINGLE definition of "latency is available"; the report imports it rather than keeping
# a second one, so the gate and the report cannot disagree (invariant C).

# Metric-to-budget mapping, CONFIRMED empirically (research R1) — not inferred from field names.
# Three text-target runs returned `avg_turn_latency` populated and `avg_turn_taking_latency` NULL,
# which settles it: turn-taking latency is the voice-only TTS figure, and turn latency is the
# general per-turn response time present in both modalities.
#
#   avg_turn_latency_ms       <-> profile latency_budget.p95_turn_ms            (voice AND text)
#   avg_turn_taking_latency_ms <-> profile latency_budget.time_to_first_audio_ms (voice only)
#
# The provisional mapping was the reverse of this, and the two figures differ by ~9x on voice, so
# guessing would have shipped confidently wrong verdicts in both directions.
LATENCY_TURN_FIELD = "avg_turn_latency_ms"             # model response time; voice AND text
LATENCY_TTFA_FIELD = "avg_turn_taking_latency_ms"      # Time To First Audio; voice only, null on text
LATENCY_REPORTED_FIELDS = (LATENCY_TURN_FIELD, LATENCY_TTFA_FIELD)

# Which figure carries the PRIMARY verdict, per modality — the bound the user actually experiences.
# For a voice caller that is Time To First Audio: silence on the line is the felt failure, and it is
# what a responsiveness SLO is written against. For text it is turn latency, since there is no audio
# stage at all (the platform returns TTFA as null there).
PRIMARY_LATENCY_FIELD = {"voice": LATENCY_TTFA_FIELD, "text": LATENCY_TURN_FIELD}
SECONDARY_LATENCY_FIELD = {"voice": LATENCY_TURN_FIELD}     # full turn latency still reported/judged

# Back-compat alias: the default `latency_figure` field when no modality is in hand.
LATENCY_VERDICT_FIELD = LATENCY_TURN_FIELD
LATENCY_VOICE_FIELD = LATENCY_TTFA_FIELD


def primary_latency_field(modality: str | None) -> str:
    """The verdict-bearing figure for a run's modality (voice → TTFA, text → turn latency)."""
    return PRIMARY_LATENCY_FIELD.get((modality or "").strip().lower(), LATENCY_TURN_FIELD)


def latency_figure(simulation: object, field: str = LATENCY_TURN_FIELD) -> float | None:
    """A latency figure a simulation returned, or None when it returned none.

    None means *absent*, and absence is the honest signal that drives not-assessed — never a
    substituted zero or default (data-model §1). A null `avg_turn_taking_latency_ms` is the normal,
    correct state for a text target, not a defect.
    """
    if not isinstance(simulation, dict):
        return None
    block = simulation.get("latency")
    if not isinstance(block, dict):
        return None
    value = block.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value > 0 else None


def latency_available(simulations: object, modality: str | None = None) -> bool:
    """True iff at least one simulation carries the modality's verdict-bearing figure (invariant B).

    With no modality in hand, either figure counts — the run demonstrably returned agent-side
    latency, and scoring picks the right one once the modality is known.
    """
    if isinstance(simulations, dict):          # accept a single simulation for convenience
        simulations = [simulations]
    if not isinstance(simulations, (list, tuple)):
        return False
    fields = ((primary_latency_field(modality),) if modality else LATENCY_REPORTED_FIELDS)
    return any(latency_figure(s, f) is not None for s in simulations for f in fields)


def derive_available_signals(simulations: object = None, *, trace_available: bool = False,
                             modality: str | None = None) -> frozenset[str]:
    """Derive a run's available-signal set from what the run RETURNED.

    `simulations` is a findings record's `simulations` list (or one entry). `trace_available` keeps
    the existing feature-004 trace determination, which is already observation-based. `modality`
    selects WHICH figure must be present (voice → TTFA, text → turn latency); it is a property of
    the run under test, not of how the run was invoked.

    Deliberately takes no route, credential or surface argument — there is no way to pass one,
    which is the point (invariant A).
    """
    signals: set[str] = set()
    if trace_available:
        signals.add(SIGNAL_TRACE)
    if latency_available(simulations, modality):
        signals.add(SIGNAL_LATENCY)
    return frozenset(signals)


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

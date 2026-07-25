#!/usr/bin/env python3
"""
Run a REPS pillar suite against a configured target agent.

Usage:
    python reps/run_suite.py --dir S-security --modality voice
    python reps/run_suite.py --dir R-reasoning --max-turns 8
    python reps/run_suite.py --dir E-execution --sim compound-request
    python reps/run_suite.py --dir P-performance --upload-only

Requires:
    - OKAREO_API_KEY in environment or .env
    - reps/target.json configured (copy from reps/target.json.voice-example)

Contract: specs/001-reps-voice-workbench/contracts/cli-runner.md
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reps.common import (  # noqa: E402
    DIR_TO_PILLAR,
    PILLARS,
    SINGLE_TURN_DRIVER_TEMPLATE,
    UNSET,
    check_eval_mode,
    init_okareo,
    parse_artifact,
    parse_metadata,
    parse_scenario_meta,
)
from reps.reuse.decision import BuildingBlock, PlatformArtifactRef  # noqa: E402
from reps.reuse.fingerprint import (  # noqa: E402
    fingerprint_check,
    fingerprint_driver,
    fingerprint_scenario,
)
from reps.reuse.naming import canonical_name  # noqa: E402
from reps.reuse.orchestrate import RunDisposition, decide_and_record  # noqa: E402
from reps.reuse.platform import (  # noqa: E402
    discovery_name,
    sdk_find_check,
    sdk_find_driver,
    sdk_find_scenario,
)
from reps.trace import (  # noqa: E402
    as_bool,
    check_runs,
    modality_ok,
    resolve_trace_available,
)


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable without the Okareo SDK)
# ---------------------------------------------------------------------------
def modality_matches(artifact_modality: str | None, selected: str) -> bool:
    """An artifact runs under `selected` if its modality is that modality, 'both', or unset.

    Thin wrapper over `reps.trace.modality_ok` (single source of truth). Applies to drivers and
    scenarios; checks additionally gate on trace availability via `reps.trace.check_runs`.
    """
    return modality_ok(artifact_modality, selected)


def resolve_on_draft(status: str | None, on_draft: str,
                     interactive: bool) -> tuple[str, str | None]:
    """Draft gate (feature 010, specs/010-reps-explore/contracts/draft-gating.md).

    Returns `(action, message)` with action ∈ {'proceed', 'stop', 'prompt'}. Only a `draft`
    profile status gates; `applied` and None (absent profile / no field) always proceed
    unchanged (INV-G6). `--on-draft baseline` proceeds with the warning printed; `stop` aborts;
    `ask` prompts on a TTY and resolves to `stop` in non-interactive contexts so the warning can
    never be bypassed unnoticed in CI (INV-G5). Never auto-applies the draft (INV-G3).
    """
    if status != "draft":
        return "proceed", None
    warn = ("an unapplied DRAFT profile (written by reps-explore) exists for this agent. "
            "It has generated no tuned rows: run reps-profile to apply it, or proceed with "
            "the agent-agnostic baseline (affected pillars reported untuned)")
    if on_draft == "baseline":
        return "proceed", warn
    if on_draft == "stop":
        return "stop", warn
    if interactive:  # on_draft == "ask" on a TTY
        return "prompt", warn
    return "stop", warn + " — non-interactive run: pass --on-draft baseline to proceed"


def load_eval_config(pillar_dir: Path) -> dict | None:
    cfg = pillar_dir / "eval_config.json"
    if cfg.exists():
        return json.loads(cfg.read_text(encoding="utf-8"))
    return None


def build_auto_plan(scenario_modes: dict[str, str], scenario_checks: dict[str, list | None],
                    check_modes: dict[str, str], driver_names: list[str]) -> list[dict]:
    """Auto-derive an evaluation plan from artifact metadata (mirrors compliance-owasp)."""
    single_turn_checks = [n for n, m in check_modes.items() if m == "single-turn"]
    multi_turn_checks = [n for n, m in check_modes.items() if m == "multi-turn"]
    single = sorted(n for n, m in scenario_modes.items() if m == "single-turn")
    multi = sorted(n for n, m in scenario_modes.items() if m == "multi-turn")
    drivers = sorted(driver_names)
    plan: list[dict] = []

    for name in single:
        checks = scenario_checks.get(name) or single_turn_checks or list(check_modes.keys())
        plan.append({"scenario": name, "checks": checks, "driver": None,
                     "max_turns": 1, "first_turn": "driver"})

    def checks_for(name: str) -> list[str]:
        return scenario_checks.get(name) or multi_turn_checks or list(check_modes.keys())

    if multi and drivers:
        if len(multi) == len(drivers):
            for name, drv in zip(multi, drivers):
                plan.append({"scenario": name, "checks": checks_for(name), "driver": drv,
                             "max_turns": 10, "first_turn": "target"})
        else:
            drv = drivers[0]
            for name in multi:
                plan.append({"scenario": name, "checks": checks_for(name), "driver": drv,
                             "max_turns": 10, "first_turn": "target"})
    return plan


def resolve_plan(pillar_dir: Path, scenario_modes, scenario_checks, check_modes,
                 driver_names, sim_filter: str | None = None) -> tuple[list[dict], str]:
    """Resolve the simulation plan from eval_config.json or auto-detection."""
    cfg = load_eval_config(pillar_dir)
    if cfg:
        plan, source = cfg.get("simulations", []), "eval_config.json"
    else:
        plan = build_auto_plan(scenario_modes, scenario_checks, check_modes, driver_names)
        source = "auto-detected plan"
    if sim_filter:
        plan = [s for s in plan if sim_filter.lower() in s["scenario"].lower()]
    return plan, source


def filter_plan_checks(plan: list[dict], allowed_checks) -> tuple[list[dict], dict[str, list[str]]]:
    """Drop any check a plan names that did NOT survive the modality filter.

    The modality gate (FR-006/FR-030): a run only scores checks whose `modality` includes the
    selected modality, so `allowed_checks` is the set of checks actually uploaded for this run.
    A check named in `eval_config.json` (e.g. a `modality: text` trace assertion on a voice run)
    that was excluded at upload MUST NOT reach `run_simulation`. Returns the filtered plan plus a
    {scenario: [dropped_check, ...]} map for logging. This is what enforces
    "a voice run MUST exclude every trace-based check."
    """
    allowed = set(allowed_checks)
    filtered: list[dict] = []
    dropped: dict[str, list[str]] = {}
    for sim in plan:
        names = sim.get("checks", []) or []
        keep = [c for c in names if c in allowed]
        drop = [c for c in names if c not in allowed]
        if drop:
            dropped[sim.get("scenario", "?")] = drop
        filtered.append({**sim, "checks": keep})
    return filtered, dropped


# ---------------------------------------------------------------------------
# Upload (requires Okareo)
# ---------------------------------------------------------------------------
def upload_artifacts(okareo, pillar_dir: Path, prefix: str, modality: str,
                     trace_available: bool = False, slug: str | None = None):
    """Upload drivers, scenarios (validated row banks, split per driver), and checks.

    Artifacts resolve **overlay-first** (feature 006): for each name, this agent's tuned overlay
    under `results/<slug>/tuned/<pillar>/` wins over the committed `reps/<pillar>/` baseline, and
    discovery is the *union* of both so tuning one bank never drops baseline coverage (INV-R4).
    An overlay-sourced block is published as tuned (`<canonical>-tuned-<slug>`); baseline-sourced
    blocks keep their canonical names. `slug=None` ⇒ pure baseline (pre-006 behavior).

    Standardized banks (feature 002) are validated fail-fast against
    contracts/scenario-row.md before anything is uploaded (FR-007), including the
    driver-render check (SC-004). A bank whose rows route to multiple drivers is
    registered once per driver as `<name>--<driver>` with only that driver's rows
    (research D6). Pre-002 banks (no `sub_capability` anywhere) skip row validation
    with a logged notice so pillars can be converted incrementally.

    Returns registry dicts + `scenario_rows` (registered name -> list of row `input`
    dicts, standardized banks only — used for findings v2 coverage-gap expansion) and
    `scenario_splits` (base name -> {driver: registered name}).
    """
    import json
    import tempfile

    from okareo.checks import CheckOutputType, ModelBasedCheck
    from okareo.model_under_test import Driver

    from reps.common import (
        CodeCheckFromSource,
        RowValidationError,
        bank_is_standardized,
        check_driver_render,
        load_rows,
        split_rows_by_driver,
        validate_rows,
    )

    from reps.paths import discover_names, resolve_artifact, with_canonical_blocks
    from reps.rows import select_rows_for_modality
    from reps.coverage import load_manifest

    # Pillar coverage manifest drives the scenario-row modality gate (feature 008): a probe whose
    # declared class modality doesn't match this run is not applicable and is not uploaded/run.
    pillar_manifest = load_manifest(pillar_dir)

    if slug:
        print(f"  artifacts: overlay-first for agent '{slug}' (baseline fallback)")

    # Reuse ledger for this run (feature 003) — the platform is the record; we discover
    # then decide reuse-vs-upload per block, biasing to reuse unless superseded (FR-001).
    disposition = RunDisposition()

    # --- Drivers first: row validation needs their names and templates -------------
    # Keyed by the CANONICAL name (what the plan and each row's `driver` field reference).
    # `driver_published` maps that canonical key -> the name the driver actually carries on the
    # platform, which for a tuned driver is `<canonical>-tuned-<slug>`. Keeping these separate is
    # what stops a tuned persona from being published over the shared baseline driver.
    registered_drivers, driver_templates, driver_published = {}, {}, {}
    for dname in discover_names(pillar_dir, "drivers", slug):
        md, md_tuned = resolve_artifact(pillar_dir, "drivers", dname, slug)
        meta = parse_metadata(md)
        if not modality_matches(meta.get("modality"), modality):
            continue
        data = parse_artifact(md, default_temperature=0.6)
        canonical = data["name"]
        # Feature 014: driver files author only the four-section core; the MCP appends the
        # platform's canonical rule blocks on save. The SDK does not, so append them here —
        # otherwise an SDK-uploaded persona would run with no conversation rules, and its
        # fingerprint could never match an MCP-saved driver (perpetual re-upload).
        kwargs = dict(name=canonical,
                      prompt_template=with_canonical_blocks(data["prompt_template"]),
                      temperature=data["temperature"])
        # Voice driver fields (additive; only when present and running voice)
        if modality == "voice":
            for f in ("voice", "voice_profile", "language"):
                if data.get(f) is not UNSET and data.get(f):
                    kwargs[f] = data[f]
        block = BuildingBlock(block_type="driver", pillar_letter=prefix,
                              driver=canonical, source_path=str(md),
                              tuned=md_tuned, agent_slug=slug if md_tuned else None)
        # Look the driver up under the name it would actually carry (tuned name when agent-scoped).
        # Because a tuned name embeds the slug, this is also the agent-isolation boundary: we can
        # never find (and therefore never reuse) another agent's tuned driver.
        lookup = discovery_name(block)
        # Decide reuse (FR-003a): drivers carry no tags, so compare the committed
        # persona/config fingerprint against the platform driver's (fetched by name).
        committed_fp = fingerprint_driver(
            prompt_template=kwargs["prompt_template"], temperature=kwargs.get("temperature"),
            voice=kwargs.get("voice"), voice_profile=kwargs.get("voice_profile"),
            language=kwargs.get("language"))
        ref = sdk_find_driver(okareo, lookup)
        existing_obj = None
        if ref.present:
            try:
                existing_obj = okareo.get_driver_by_name(lookup)
            except Exception:  # noqa: BLE001 - transient → treat as absent (fail toward upload)
                existing_obj = None
                ref = PlatformArtifactRef(name=lookup, present=False)
        dec = decide_and_record(disposition, block, committed_fp, ref)
        if dec.reused and existing_obj is not None:
            result = existing_obj
            published = lookup
            print(f"  driver: {published} (reused)")
        else:
            # A tuned driver publishes under its agent-scoped name; a baseline driver under its
            # canonical name. Either way, we publish under exactly what we looked up/decided.
            published = dec.target_name
            kwargs["name"] = published
            driver = Driver(**{k: v for k, v in kwargs.items() if k in _driver_kwargs(Driver)})
            result = okareo.create_or_update_driver(driver=driver)
            print(f"  driver: {published} (uploaded — {dec.reason})")
        registered_drivers[canonical] = result
        driver_templates[canonical] = data["prompt_template"]
        driver_published[canonical] = published
    print(f"  drivers: {len(registered_drivers)}")

    # --- Scenarios: validate standardized banks, split multi-driver banks ----------
    registered_scenarios, scenario_modes, scenario_checks = {}, {}, {}
    scenario_rows: dict[str, list[dict]] = {}
    scenario_splits: dict[str, dict[str, str]] = {}

    def _register(name: str, path: Path, meta: dict, rows: list[dict] | None,
                  bank: str, driver: str | None = None, is_tuned: bool = False):
        # Reuse decision (feature 003). SDK path is degraded for scenarios (no listing/
        # tagging) → discovery is unconfirmed and we fall toward upload (FR-010), but we
        # still record the disposition so the report shows what happened.
        # Feature 006: `path` is the RESOLVED source (overlay when tuned), so the fingerprint
        # keys supersession off the overlay's content (INV-R5).
        fp_rows = rows if rows is not None else load_rows(path)
        committed_fp = fingerprint_scenario(fp_rows)
        block = BuildingBlock(block_type="scenario", pillar_letter=prefix, bank=bank,
                              driver=driver, source_path=str(path),
                              tuned=is_tuned, agent_slug=slug if is_tuned else None)
        dec = decide_and_record(disposition, block, committed_fp,
                                sdk_find_scenario(okareo, discovery_name(block)))
        # The scenario is published (and referenced by the plan) under its decided name — the
        # agent-scoped `-tuned-<slug>` name when tuned, the canonical name otherwise.
        published = dec.target_name if not dec.reused else discovery_name(block)
        if dec.reused:
            print(f"  scenario: {published} (reused)")
        else:
            print(f"  scenario: {published} (uploaded — {dec.reason})")
            scenario = okareo.upload_scenario_set(scenario_name=published, file_path=str(path))
            registered_scenarios[name] = scenario
        scenario_modes[name] = meta.get("evaluation_mode", "single-turn")
        scenario_checks[name] = meta.get("checks")
        if rows is not None:
            scenario_rows[name] = [r.get("input", {}) for r in rows]

    for sname in discover_names(pillar_dir, "scenarios", slug):
        jsonl, is_tuned = resolve_artifact(pillar_dir, "scenarios", sname, slug)
        # The bank's `_meta.md` co-resolves with the bank itself (INV-R6).
        meta_path, _ = resolve_artifact(pillar_dir, "scenarios", f"{jsonl.stem}_meta.md", slug)
        meta = parse_scenario_meta(meta_path)
        if not modality_matches(meta.get("modality"), modality):
            continue
        name = canonical_name(prefix, jsonl.stem)
        rows = load_rows(jsonl)
        # Scenario-row modality gate (feature 008, US1): drop rows whose probe class is not
        # applicable to this run's modality (e.g. voice-only `barge-in` on a text run). They are
        # not executed and not scored; coverage reconciliation renders them not-applicable (never a
        # failure, never a gap). Only standardized banks carry `sub_capability`.
        if bank_is_standardized(rows):
            rows, excluded = select_rows_for_modality(rows, pillar_manifest, modality)
            if excluded:
                subs = sorted({e["sub_capability"] for e in excluded})
                print(f"  note: {jsonl.name} — {len(excluded)} row(s) not applicable to "
                      f"modality={modality}: {', '.join(subs)} (voice/text-only)")
            if not rows:
                print(f"  skip: {jsonl.name} — no rows applicable to modality={modality}")
                continue
        if not bank_is_standardized(rows):
            print(f"  note: {jsonl.name} is a pre-002 bank — row validation skipped")
            _register(name, jsonl, meta, None, bank=jsonl.stem, is_tuned=is_tuned)
            continue
        # Fail fast (FR-007 / SC-004) before anything reaches the platform.
        validate_rows(jsonl, rows, registered_drivers=list(registered_drivers) or None)
        routed = {d for d in (r["input"].get("driver") for r in rows) if d}
        check_driver_render(jsonl, rows,
                            {d: t for d, t in driver_templates.items()
                             if not routed or d in routed} or driver_templates)
        groups = split_rows_by_driver(rows)
        if len([k for k in groups if k]) > 1:
            scenario_splits[name] = {}
            for drv, drv_rows in groups.items():
                reg_name = canonical_name(prefix, jsonl.stem, drv)
                with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                                 encoding="utf-8") as tmp:
                    tmp.write("\n".join(json.dumps(r) for r in drv_rows) + "\n")
                    tmp_path = Path(tmp.name)
                _register(reg_name, tmp_path, meta, drv_rows, bank=jsonl.stem, driver=drv,
                          is_tuned=is_tuned)
                scenario_splits[name][drv] = reg_name
                tmp_path.unlink(missing_ok=True)
        else:
            _register(name, jsonl, meta, rows, bank=jsonl.stem, is_tuned=is_tuned)
    print(f"  scenarios: {len(registered_scenarios)} registered/uploaded, "
          f"{disposition.counts['reused']} reused so far")

    # --- Checks ---------------------------------------------------------------------
    # Combined modality × trace gate (feature 004, contracts/check-selection.md): a check runs iff
    # its modality matches AND (it needs no trace OR a trace is available for this run). A
    # `requires_trace` check excluded *solely* because no trace is available is recorded so the
    # report can show it as a `no-trace` coverage gap (never a pass/fail).
    registered_checks, check_modes = {}, {}
    check_alias: dict[str, str] = {}       # canonical check name -> published (tuned) name
    trace_check_names: list[str] = []      # requires_trace checks that WILL run (trace available)
    trace_excluded_checks: list[str] = []  # requires_trace checks dropped for lack of a usable trace
    for chk_name in discover_names(pillar_dir, "checks", slug):
        cpath, chk_tuned = resolve_artifact(pillar_dir, "checks", chk_name, slug)
        meta = parse_metadata(cpath)
        cname = meta.get("name", cpath.stem)
        requires_trace = as_bool(meta.get("requires_trace"))
        if not check_runs(meta.get("modality"), requires_trace, modality, trace_available):
            if requires_trace and modality_ok(meta.get("modality"), modality):
                trace_excluded_checks.append(cname)  # excluded only because no trace is available
            continue
        if requires_trace:
            trace_check_names.append(cname)
        data = parse_artifact(cpath)
        code_contents = data["code_contents"] if data.get("code_contents") is not UNSET else None
        if code_contents:
            check_obj = CodeCheckFromSource(code_contents)
        else:
            check_obj = ModelBasedCheck(prompt_template=data["prompt_template"],
                                        check_type=CheckOutputType.PASS_FAIL)
        # Reuse decision (feature 003). The SDK check listing carries no `fp:` tag, so a
        # present check is unconfirmed → re-save (new version); absence → first upload.
        committed_fp = fingerprint_check(
            check_type="code" if code_contents else "model",
            output_type="pass_fail",
            prompt_template=data.get("prompt_template") if not code_contents else None,
            code_contents=code_contents, description=data.get("description", ""))
        block = BuildingBlock(block_type="check", pillar_letter=prefix,
                              check_name=data["name"], source_path=str(cpath),
                              tuned=chk_tuned, agent_slug=slug if chk_tuned else None)
        # Look up (and publish) under the agent-scoped name when overlay-sourced, so one agent's
        # tuned check can never be written over the shared baseline check.
        lookup = discovery_name(block)
        dec = decide_and_record(disposition, block, committed_fp, sdk_find_check(okareo, lookup))
        published = dec.target_name if not dec.reused else lookup
        result = okareo.create_or_update_check(
            name=published, description=data.get("description", ""), check=check_obj)
        # Registries stay keyed by the CANONICAL name (what eval_config/_meta.md reference);
        # `check_alias` carries canonical -> published so the plan can be remapped before the run.
        registered_checks[data["name"]] = result.id
        check_modes[data["name"]] = check_eval_mode(cpath)
        if published != data["name"]:
            check_alias[data["name"]] = published
        print(f"  check: {published} ({'reused' if dec.reused else 'uploaded — ' + dec.reason})")
    print(f"  checks: {len(registered_checks)}")
    print(f"  {disposition.summary_line()}")

    return (registered_scenarios, scenario_modes, scenario_checks, registered_checks,
            check_modes, registered_drivers, scenario_rows, scenario_splits, disposition,
            trace_check_names, trace_excluded_checks, check_alias, driver_published)


def _driver_kwargs(driver_cls) -> set[str]:
    """Return the kwargs the installed Okareo Driver accepts (tolerate SDK version drift)."""
    try:
        import inspect
        return set(inspect.signature(driver_cls.__init__).parameters) - {"self"}
    except (ValueError, TypeError):  # pragma: no cover
        return {"name", "prompt_template", "temperature", "voice", "voice_profile", "language"}


# ---------------------------------------------------------------------------
# Evaluate (requires Okareo)
# ---------------------------------------------------------------------------
def run_evaluation(okareo, api_key, target_ref, prefix, plan, registered_scenarios,
                   registered_drivers, max_turns_override=None, driver_published=None,
                   scenario_rows=None, scenario_splits=None):
    """Run the plan against a registered target (referenced by name/id string).

    A plan entry naming a split bank (research D6) resolves to the per-driver registered
    scenario `<name>--<driver>`. For standardized banks, the rows each simulation ran are
    attached as `expected_rows` so capture can expand per-row coverage gaps (FR-006).
    """
    from okareo.model_under_test import Driver

    scenario_rows = scenario_rows or {}
    scenario_splits = scenario_splits or {}
    results = {}
    for sim in plan:
        name = sim["scenario"]
        driver_name = sim.get("driver")
        resolved = name
        if name not in registered_scenarios:
            resolved = (scenario_splits.get(name) or {}).get(driver_name)
            if not resolved:
                print(f"  ⚠ scenario {name} not registered — skipping")
                continue
        checks = sim.get("checks", [])
        max_turns = max_turns_override or sim.get("max_turns", 1)
        first_turn = sim.get("first_turn", "driver")
        repeats = int(sim.get("repeats", 1))
        is_multi = max_turns > 1

        if is_multi and driver_name and driver_name in registered_drivers:
            reg = registered_drivers[driver_name]
            # Use the name the driver actually carries on the platform. For a tuned driver that is
            # `<canonical>-tuned-<slug>`; reconstructing it under the canonical name here would
            # publish this agent's persona over the shared baseline driver (cross-agent leak).
            published_driver = (driver_published or {}).get(driver_name) \
                or getattr(reg, "name", None) or driver_name
            driver = Driver(temperature=getattr(reg, "temperature", 0.6),
                            name=published_driver, prompt_template=reg.prompt_template)
        else:
            published_driver = driver_name
            driver = Driver(temperature=0, name=f"{prefix}-passthrough",
                            prompt_template=SINGLE_TURN_DRIVER_TEMPLATE)

        expected_rows = scenario_rows.get(resolved)
        print(f"\n  running {resolved} ({'multi' if is_multi else 'single'}-turn, "
              f"max_turns={max_turns}, repeats={repeats})")
        t0 = time.monotonic()
        base = {"checks": list(checks), "driver": driver_name, "max_turns": max_turns}
        if expected_rows:
            base["expected_rows"] = expected_rows
        try:
            test_run = okareo.run_simulation(
                target=target_ref, driver=driver,
                name=f"{prefix} {'Simulation' if is_multi else 'Eval'} — {resolved}",
                api_key=api_key, first_turn=first_turn, repeats=repeats,
                scenario=registered_scenarios[resolved], max_turns=max_turns, checks=checks)
            elapsed = time.monotonic() - t0
            results[resolved] = {**base, "test_run": test_run, "elapsed": elapsed,
                                 "status": "complete"}
            print(f"  ✓ {getattr(test_run, 'id', '?')} ({elapsed:.1f}s)")
        except Exception as e:  # noqa: BLE001 - per-scenario isolation
            results[resolved] = {**base, "test_run": None, "elapsed": time.monotonic() - t0,
                                 "status": "error", "error": str(e)}
            print(f"  ✗ error: {e}")
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Run a REPS pillar suite against a target agent.")
    parser.add_argument("--dir", required=True, metavar="PILLAR",
                        help="Pillar by letter (R/E/P/S) or full dir name (e.g. S or S-security)")
    parser.add_argument("--modality", default=None, choices=["voice", "text"],
                        help="Override the run modality (feature 008: default is auto-derived from "
                             "the agent profile / target; voice as last-resort fallback)")
    parser.add_argument("--trace", default="auto", choices=["auto", "on", "off"],
                        help="Trace availability for text runs (feature 004): 'auto' uses the "
                             "target/profile trace.path; 'on' forces trace-based checks; 'off' "
                             "forces black-box. Voice is always black-box. (default: auto)")
    parser.add_argument("--max-turns", type=int, default=None, help="Override max_turns for all sims")
    parser.add_argument("--sim", default=None, help="Run only sims whose scenario name contains this")
    parser.add_argument("--upload-only", action="store_true", help="Upload artifacts, skip eval")
    parser.add_argument("--eval-only", action="store_true", help="Evaluate only (already uploaded)")
    parser.add_argument("--target", default=None,
                        help="Name (or id) of a target already registered in Okareo. "
                             "Defaults to $REPS_TARGET. This is the primary path.")
    parser.add_argument("--register-target", default=None, metavar="CONFIG.json",
                        help="Optional: register a target from a local config file (voice/text) "
                             "via create_or_update_target, then run against it.")
    parser.add_argument("--on-draft", default="ask", choices=["ask", "baseline", "stop"],
                        help="What to do when the agent profile is an unapplied reps-explore "
                             "draft (feature 010): 'ask' prompts on a TTY and stops when "
                             "non-interactive; 'baseline' proceeds untuned with a warning; "
                             "'stop' aborts with apply guidance. (default: ask)")
    args = parser.parse_args()

    reps_dir = PROJECT_ROOT / "reps"
    # Accept a pillar letter (R/E/P/S) or the full dir name (e.g. S or S-security).
    letter_to_dir = {info["dir"][0]: info["dir"] for info in PILLARS.values()}
    dirname = letter_to_dir.get(args.dir.strip().upper(), args.dir.strip())
    pillar_dir = reps_dir / dirname
    if not pillar_dir.exists():
        print(f"Error: pillar not found: {args.dir!r} → {pillar_dir}. "
              f"Use a letter (R/E/P/S) or a dir name (e.g. S-security).")
        sys.exit(1)
    prefix = dirname.split("-")[0]  # R / E / P / S
    pillar = DIR_TO_PILLAR.get(dirname, dirname)

    okareo, api_key = init_okareo()

    # Resolve the target FIRST (feature 006): the agent slug selects this agent's tuned overlay
    # artifacts, so it must be known before upload_artifacts discovers/fingerprints anything.
    import os

    from reps.paths import resolve_profile
    from reps.slug import agent_slug
    from reps.targets import build_target, resolve_target

    target_ref = None
    if args.register_target:
        registered = okareo.create_or_update_target(build_target(args.register_target))
        target_ref = getattr(registered, "name", None) or resolve_target(okareo,
                                                                        args.register_target)
        print(f"  registered + using target: {target_ref}")
    else:
        ref = args.target or os.environ.get("REPS_TARGET", "")
        # --upload-only with no target is legal: there is no agent, so no overlay — pure baseline.
        if ref or not args.upload_only:
            target_ref = resolve_target(okareo, ref)
            print(f"  target: {target_ref}")

    # slug=None ⇒ no agent resolved ⇒ baseline-only artifacts + baseline profile (pre-006 behavior).
    slug = agent_slug(target_ref) if target_ref else None

    # Draft gate (feature 010, FR-018): an unapplied reps-explore draft is surfaced — warn +
    # operator choice — never run past silently and never auto-applied. The draft's `modality:`
    # is still honored below (INV-G4): modality is declared target truth, not tuning.
    from reps.paths import read_profile_status
    gate_action, gate_msg = resolve_on_draft(read_profile_status(slug), args.on_draft,
                                             sys.stdin.isatty())
    if gate_action == "prompt":
        print(f"  ⚠ draft profile: {gate_msg}")
        answer = input("  proceed with the baseline (untuned)? [y/N]: ").strip().lower()
        if answer in ("y", "yes"):
            gate_action, gate_msg = "proceed", None
        else:
            gate_action, gate_msg = "stop", "operator chose to apply the draft first"
    if gate_action == "stop":
        print(f"  ✗ stopping: {gate_msg}\n    apply the draft with the reps-profile skill, "
              f"then re-run.")
        sys.exit(1)
    if gate_msg:
        print(f"  ⚠ draft profile: {gate_msg}")

    # Auto-orient the run modality (feature 008, US2): explicit --modality overrides; else the agent
    # profile's `modality:`; else voice as a last-resort fallback (loudly surfaced, never silent).
    from reps.paths import read_profile_modality
    from reps.trace import resolve_run_modality
    modality, _msrc, _mwarn = resolve_run_modality(
        override=args.modality, profile_modality=read_profile_modality(slug))
    if modality is None:
        modality = "voice"
        _mwarn = ((_mwarn + " — ") if _mwarn else "") + "defaulting to 'voice'; pass --modality to set it"
    if _mwarn:
        print(f"  ⚠ modality: {_mwarn}")
    elif _msrc != "override":
        print(f"  modality: {modality} (auto from {_msrc})")

    # Resolve trace availability (feature 004): a property of the target/run, not the modality.
    # Voice → always black-box. Text → declared via --trace on / a target|profile trace.path.
    # The profile is resolved agent-first (feature 006), falling back to the baseline profile.
    from reps.report.capture import read_profile_trace_path
    trace_path = None
    if args.register_target:
        from reps.targets import load_target_config, trace_path_of
        try:
            trace_path = trace_path_of(load_target_config(args.register_target))
        except Exception:  # noqa: BLE001 - fall through to profile / flag
            trace_path = None
    if not trace_path:
        profile_path = resolve_profile(slug)
        if profile_path:
            trace_path = read_profile_trace_path(profile_path)
    trace_declared, trace_available = resolve_trace_available(
        modality, force=args.trace, trace_path=trace_path)

    print(f"{'=' * 56}\nREPS Runner — {args.dir} ({pillar}) · modality={modality} · "
          f"trace={'available' if trace_available else 'black-box'}\n{'=' * 56}")

    print("\nUpload")
    from reps.common import RowValidationError
    try:
        (registered_scenarios, scenario_modes, scenario_checks,
         registered_checks, check_modes, registered_drivers,
         scenario_rows, scenario_splits, disposition,
         trace_check_names, trace_excluded_checks,
         check_alias, driver_published) = upload_artifacts(
            okareo, pillar_dir, prefix, modality, trace_available, slug=slug)
    except RowValidationError as e:
        # FR-007: a malformed row must never reach a live simulation.
        print(f"\n✗ row validation failed: {e}")
        sys.exit(1)

    plan, source = resolve_plan(pillar_dir, scenario_modes, scenario_checks, check_modes,
                                list(registered_drivers.keys()), sim_filter=args.sim)
    # Modality gate (FR-006/FR-030): a plan may name checks that were excluded at upload by the
    # modality filter (e.g. a `modality: text` trace check on a voice run). Strip them so no
    # trace-based check is ever scored against a voice target.
    plan, dropped_checks = filter_plan_checks(plan, registered_checks.keys())
    for scen, drops in dropped_checks.items():
        reason = (f"not available for modality={modality}"
                  if not any(d in trace_excluded_checks for d in drops)
                  else "no usable trace")
        gate = "trace gate" if any(d in trace_excluded_checks for d in drops) else "modality gate"
        print(f"  ⚠ {gate}: excluded check(s) {drops} from {scen} ({reason})")
    if trace_excluded_checks:
        print(f"  ⚠ trace gate: {len(trace_excluded_checks)} trace-based check(s) not assessed "
              f"(no usable trace) — reported as no-trace coverage gaps: {trace_excluded_checks}")
    # A tuned check/driver is published under its agent-scoped name, but the plan (from
    # eval_config / _meta.md) names it canonically. Remap now — after the modality/trace gate,
    # which reasons in canonical space — so the run references what was actually published.
    if check_alias:
        plan = [{**sim, "checks": [check_alias.get(c, c) for c in sim.get("checks", [])]}
                for sim in plan]
        print(f"  agent-scoped checks: {check_alias}")

    print(f"\nPlan: {len(plan)} simulation(s) from {source}")
    # Pre-run reuse visibility (FR-012): what the run just reused vs uploaded.
    print(f"Building blocks — {disposition.summary_line()}")

    if args.upload_only:
        print("\n✓ upload-only complete.")
        return

    from reps.report.capture import capture_results

    results = run_evaluation(okareo, api_key, target_ref, prefix, plan,
                             registered_scenarios, registered_drivers, args.max_turns,
                             scenario_rows=scenario_rows, scenario_splits=scenario_splits,
                             driver_published=driver_published)

    findings_dir = PROJECT_ROOT / "results" / slug / "findings"
    out = capture_results(pillar=pillar, modality=modality, target_name=target_ref,
                          plan=plan, results=results, results_dir=findings_dir,
                          reuse=disposition.to_record(),
                          trace_declared=trace_declared,
                          trace_check_names=trace_check_names,
                          trace_excluded_checks=trace_excluded_checks)
    print(f"\n✓ captured findings → {out}")
    errors = sum(1 for r in results.values() if r.get("status") == "error")
    print(f"Total: {len(results)} | complete: {len(results) - errors} | errors: {errors}")
    print(f"Render the report: python reps/report/gen_reps_report.py --agent \"{target_ref}\"")


if __name__ == "__main__":
    main()

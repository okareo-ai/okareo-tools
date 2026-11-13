"""
Run-plan builder (feature 022: contracts/pilot-trust-audit.md invariants N, O; research D15).

**What a run plan is.** One table saying, per scenario about to run: the bank, how many rows, which
driver, which checks will score it, the turn budget, and whether a stop check is attached. The
operator reads it before spending the calls.

**Why it is shipped rather than left as a note.** Both reference evaluations built one by hand, and
in the first the plan and the run **did not match in either direction**: an untestable probe class
sat in the plan and was dropped by hand at run time, while the single most valuable check was
attached by hand and never appeared in the plan at all. A plan that does not match the run is not a
plan — it is a second, unreconciled account of what happened. So `check_plan_matches_run` is part of
this module rather than advice: every check that will score must appear, and every
environment-blocked class must be absent.

**The invocation, stated correctly.** Run this as a module:

    PYTHONPATH=. python3 -m reps.runplan --pillar S --agent <slug>

The reference builder's own docstring documented `python3 path/to/runplan.py`, which **cannot work
as written**: running a script by path puts the *script's* directory on `sys.path`, not the working
directory, so `import reps...` fails. Its two sibling scripts documented the correct form; the one
an operator meets first did not. Recorded here because the correction is the point.

Derived from run data, never from literals (INV-O): this module is handed the banks and the config
and reads them. Nothing about a run is typed in.

Pure stdlib: part of the keyless tooling set.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

__all__ = [
    "PLAN_COLUMNS",
    "PlanError",
    "build_plan",
    "check_plan_matches_run",
    "render_plan",
]

PathLike = Union[str, Path]

PLAN_COLUMNS = ("Scenario", "Rows", "Driver", "Checks", "Max turns", "Stop check")


class PlanError(ValueError):
    """The plan does not match the run it describes (invariant N)."""


def build_plan(*, pillar_dir: PathLike, rows_by_bank: dict,
               excluded_by_bank: Optional[dict] = None,
               held_by_bank: Optional[dict] = None,
               stop_check: Optional[str] = None,
               pilot: bool = False) -> dict:
    """Build the plan for one pillar from its config and the rows that will actually run.

    `rows_by_bank` is the **post-selection** row set — after modality, environment and escalation
    filtering — because the plan has to describe the run, not the library. `excluded_by_bank` and
    `held_by_bank` carry what was filtered out, so the plan can state the omissions explicitly
    instead of leaving them as a silent difference between the plan and the suite on disk.
    """
    pillar_dir = Path(pillar_dir)
    config_path = pillar_dir / "eval_config.json"
    config = {}
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise PlanError(f"cannot read {config_path}: {exc}") from None

    # The config lists `simulations`, each naming a scenario by the PREFIXED name the runner
    # assigns (`S-verification-gate`), while a bank on disk is `verification-gate.jsonl`. Index by
    # both the full name and its suffix after the first hyphen, so a bank resolves either way. A
    # plan whose rows came out right but whose checks column read "—" would be worse than no plan:
    # it would look complete while omitting the thing invariant N exists to reconcile.
    by_name: dict = {}
    for entry in (config.get("simulations") or config.get("scenarios") or []):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("scenario") or entry.get("name") or "")
        if not name:
            continue
        by_name[name] = entry
        if "-" in name:
            by_name.setdefault(name.split("-", 1)[1], entry)

    entries = []
    for bank, rows in rows_by_bank.items():
        cfg = by_name.get(bank, {})
        drivers = sorted({(r.get("input") or {}).get("driver") for r in rows
                          if (r.get("input") or {}).get("driver")})
        entries.append({
            "scenario": bank,
            "rows": len(rows),
            "drivers": drivers or [str(cfg.get("driver") or "—")],
            "checks": [str(c) for c in (cfg.get("checks") or [])],
            "max_turns": cfg.get("max_turns"),
            "stop_check": stop_check,
            "checks_at_every_turn": bool(stop_check),
        })
    entries.sort(key=lambda e: e["scenario"])

    return {
        "pillar": pillar_dir.name,
        "pilot": pilot,
        "entries": entries,
        "excluded": {k: list(v) for k, v in (excluded_by_bank or {}).items() if v},
        "held": {k: list(v) for k, v in (held_by_bank or {}).items() if v},
        "total_rows": sum(e["rows"] for e in entries),
    }


def check_plan_matches_run(plan: dict, *, scoring_checks: list[str],
                           environment_blocked: Optional[list[str]] = None) -> None:
    """Enforce invariant N, in both directions.

    Both directions are needed because the reference run broke both:

    * **Every check that will score must appear in the plan.** A check attached at run time and
      absent from the plan means the operator approved a different run from the one that happened —
      and in the reference evaluation the check attached this way was the most valuable one there.
    * **Every environment-blocked class must be absent from the plan.** A plan that lists a probe
      the environment cannot exercise invites exactly the mistake that was made: running it anyway,
      and reading a refusal nobody could have answered as a pass.
    """
    planned_checks = {c for e in plan.get("entries", []) for c in e.get("checks", [])}
    missing = [c for c in (scoring_checks or []) if c not in planned_checks]
    if missing:
        raise PlanError(
            f"plan does not match the run: check(s) {sorted(missing)} will score but appear in no "
            f"plan entry. A check attached at run time and absent from the plan means the operator "
            f"approved a different run from the one that happened — in the first reference "
            f"evaluation that check was the most valuable one in the suite.")

    blocked = {str(b) for b in (environment_blocked or [])}
    if blocked:
        listed = []
        for entry in plan.get("entries", []):
            if entry["scenario"] in blocked:
                listed.append(entry["scenario"])
        if listed:
            raise PlanError(
                f"plan does not match the run: {sorted(listed)} are environment-blocked but are "
                f"still planned. An unexercisable probe in the plan invites running it anyway, and "
                f"a refusal nobody could have answered reads as a pass — which is how a pillar "
                f"scored 100% on a dimension it had not tested.")


def render_plan(plan: dict) -> str:
    """Render the operator-facing plan table."""
    title = f"# Run plan — {plan['pillar']}" + ("  (PILOT)" if plan.get("pilot") else "")
    lines = [title, ""]
    if plan.get("pilot"):
        lines += ["One to three rows per bank, each registered as its own separately-named pilot "
                  "scenario. The full suite does not run until the pilot gate passes.", ""]
    lines += ["| " + " | ".join(PLAN_COLUMNS) + " |", "|" + "---|" * len(PLAN_COLUMNS)]
    for e in plan["entries"]:
        lines.append("| " + " | ".join(str(x) for x in (
            e["scenario"], e["rows"], ", ".join(e["drivers"]),
            ", ".join(e["checks"]) or "—",
            e["max_turns"] if e["max_turns"] is not None else "—",
            e["stop_check"] or "—")) + " |")
    lines += ["", f"**{plan['total_rows']} row(s) will run.**", ""]

    if plan.get("excluded"):
        lines += ["## Not planned — the environment cannot exercise these", "",
                  "Reported as coverage gaps, never counted in a pass rate.", ""]
        for bank, items in sorted(plan["excluded"].items()):
            for item in items:
                lines.append(f"- `{bank}`: {item}")
        lines.append("")
    if plan.get("held"):
        lines += ["## Not planned — withheld, would trip an escalation trigger", "",
                  "These would end in a handoff, so they would measure the handoff rather than "
                  "the boundary they were written to test.", ""]
        for bank, items in sorted(plan["held"].items()):
            for item in items:
                lines.append(f"- `{bank}`: {item}")
        lines.append("")
    return "\n".join(lines)


def _main(argv: Optional[list[str]] = None) -> int:
    """CLI for the correct invocation form documented at the top of this module."""
    import argparse

    ap = argparse.ArgumentParser(
        prog="python3 -m reps.runplan",
        description="Render the run plan for one REPS pillar.")
    ap.add_argument("--pillar-dir", required=True,
                    help="path to the pillar directory, e.g. reps/S-security")
    ap.add_argument("--pilot", action="store_true")
    args = ap.parse_args(argv)

    from reps.rows import load_rows

    pillar_dir = Path(args.pillar_dir)
    rows_by_bank = {p.stem: load_rows(p)
                    for p in sorted((pillar_dir / "scenarios").glob("*.jsonl"))}
    print(render_plan(build_plan(pillar_dir=pillar_dir, rows_by_bank=rows_by_bank,
                                 pilot=args.pilot)))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

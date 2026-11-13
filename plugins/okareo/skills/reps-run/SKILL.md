---
name: reps-run
description: >-
  Run a REPS pillar (R/E/P/S) against a registered Okareo target and regenerate the assessment
  report. Keyless by default — drives Okareo through the MCP tools with no local API key; a
  CLI/SDK fallback uses run_suite.py when a key is present. The zero-setup entry point. To tailor
  scenarios to the agent first, use reps-profile (optional).

---

# REPS Run Skill

The zero-setup entry point: **pass a target name and a pillar, get a report.** No profiling Q&A
required — every pillar ships generic starters that produce a complete baseline. (Run `reps-profile`
first only if you want Reasoning/Execution probes tailored to the specific agent.)

## Pre-flight — where the baseline comes from (local wins; MCP otherwise)

The run reads the agent-agnostic **baseline** (scenario banks, drivers, checks, eval configs) and
writes operator-local outputs to `results/` in the current project root — the directory the
session was invoked in, NEVER another repo (a REPS workbench checkout visible elsewhere on disk,
e.g. as an additional working directory, is not this run's home; do not anchor paths or import
helpers from it). Resolve the baseline **source** first — check `test -d reps/S-security` in the
current project root:

- **Local `reps/` present → local mode.** Read baseline files from the tree exactly as documented
  below. Record its version from `reps/.workbench-version` (or `unversioned` if absent).
- **No local `reps/` → MCP mode (the zero-setup default).** Serve every baseline read through the
  `get_reps_baseline` Okareo MCP tool — do NOT vendor, prompt to install, or git clone baseline
  artifacts (scenario banks, drivers, checks, eval configs): read them through the tool, never
  write them to disk. The one required exception is the pure-Python **report tooling**: DO
  materialize the MCP tooling set into a temporary directory (see "Materialize the MCP tooling
  set" under Path A) — records and the report are produced by that tooling, in every mode. The
  tool serves the latest released tree:
  - **Discover** — call with `{"pillar": "<pillar-dir>"}` (no `path`) → envelope lists `files[]`
    (tree-relative paths) and the serving `tag`. Record that `tag` once; it is the run's baseline
    version.
  - **Fetch** — call with `{"pillar": ..., "path": "<pillar-dir>/scenarios/core.jsonl"}` → the
    envelope's `content` field is the exact published file text. Wherever the steps below read
    `reps/<pillar-dir>/<x>`, fetch path `<pillar-dir>/<x>` instead.
  - **Envelope handling** — `stale: true` means the server is serving a cached snapshot (surface
    it and the `stale_reason` to the operator, then proceed). Ignore unknown extra fields. On
    errors branch on `error.code`, never message text: `rate_limited` → wait
    `retry_after_seconds` and retry; `baseline_unavailable` → STOP and tell the operator the
    baseline cannot be served right now (offer `/okareo:get-reps` local install as the workaround);
    `unknown_path` → re-discover (the tree may have changed between calls); others → surface
    `message` verbatim.
  - **Helper scripts** run from the materialized MCP tooling set (see Path A) — every `python -c`
    helper below works in MCP mode with `PYTHONPATH="$TOOLING_ROOT"` prepended. Their semantics,
    for reference: the agent slug is the target name lowercased, spaces → `_`, other
    non-`[a-z0-9_]` runs collapsed to `_` (e.g. "The Parts Store" → "the_parts_store"); profile
    status is the `status:` field of `results/<agent_slug>/profile/agent-profile.yaml` when that
    file exists locally; overlay resolution is a direct check of
    `results/<agent_slug>/tuned/<pillar-dir>/…` (no local filesystem at all ⇒ no overlay — run
    pure baseline and say so). The CLI/SDK fallback (Path B) is unavailable in MCP mode.

**What MCP mode writes to disk — the 19-vs-91 boundary.** Exactly **19** files are materialized: the
pure-Python MCP tooling set (17 modules + 2 brand assets), listed verbatim under "Materialize the MCP
tooling set" below, written to a temporary directory outside the project. Baseline evaluation
material — scenario banks, drivers, checks, eval configs, roughly **91** files in all — is read
through `get_reps_baseline` and **never baseline material written to disk**. The tooling set is a
strict subset of the workbench and must never be mistaken for it: materializing the whole baseline is
what `get-reps` is for, and it is not what a run needs.

Local mode is **optional** — the deliberate opt-in for operators who want to iterate on the material,
work offline, or pin a version. `/okareo:get-reps` installs and updates it. The no-local-copy MCP
path above remains the zero-setup default on every surface; mention local mode when relevant, never
require it.

## Inputs

- **target** — the name (or id) of a voice agent already registered in Okareo. Fallback `$REPS_TARGET`.
  If neither is available, ask the operator.
- **pillar** — letter `R`/`E`/`P`/`S`, or a dir name (`R-reasoning`, `E-execution`, `P-performance`,
  `S-security`). Default `S` (Security — the highest-importance single pillar). Accept "all", which
  runs and reports in **REPS brand order (R, E, P, S)**.
- **modality** — **auto-derived** (feature 008), do NOT default to `voice`. Resolve it with
  `reps.trace.resolve_run_modality(override=<explicit modality if the operator gave one>,
  profile_modality=reps.paths.read_profile_modality(slug), target_type=<target.type>)`. Precedence:
  explicit override > `profile.modality` > target type (voice target → voice, `custom_endpoint` →
  text) > undeterminable. If it returns a `warning` (override disagrees with the profile, or
  undeterminable), surface it to the operator; only fall back to `voice` as a last resort and say so.
- **trace** (feature 004, text only) — `auto` (default) / `on` / `off`. Trace availability is a
  property of the target/run, NOT the modality. Resolve it with
  `reps.trace.resolve_trace_available(modality, force=<trace>, trace_path=<path>)` where `<path>`
  comes from the target config `trace.path` or the profile `trace.path`
  (`reps.report.capture.read_profile_trace_path`). Voice is always black-box (`trace_available=False`).

## Path A — MCP mode (default, keyless) ⭐

Drive Okareo through the **Okareo MCP tools** using the MCP's own authentication — **no local
`OKAREO_API_KEY` required** (FR-031). Read the committed artifacts as source of truth (Constitution
VII) — **resolved overlay-first** (feature 006, see "Artifact resolution" below) — and produce the same
captured-results file as the CLI path.

### Artifact resolution (feature 006) — do this for EVERY artifact you load

The committed `reps/<pillar-dir>/` tree is the agent-agnostic **baseline**. If this agent has been
tuned, its **overlay** lives under `results/<agent_slug>/tuned/<pillar-dir>/`. For each artifact,
prefer the overlay, fall back to the baseline, and load the **union** of both name sets (an overlay
never removes a baseline bank — that would be silent coverage loss):

```bash
python -c "
from reps.paths import discover_names, resolve_artifact, resolve_profile
from pathlib import Path
p = Path('reps/<pillar-dir>'); slug = '<agent_slug>'
for n in discover_names(p, 'scenarios', slug):
    print(n, *resolve_artifact(p, 'scenarios', n, slug))
print('profile:', resolve_profile(slug))"
```

An artifact resolved **from the overlay is tuned**: publish it under `<canonical>-tuned-<agent_slug>`
with tags `reps, pillar:<L>, tuned, agent:<agent_slug>, ver:<N>, fp:<hash>` (a tuned driver uses the
`-tuned-<agent_slug>` name and no tags), and fingerprint the **overlay** file so supersession keys off
the tuned content. An artifact resolved from the **baseline** keeps its canonical name/tags and is
reused exactly as before. **Agent isolation:** never reuse a block tagged `agent:<other>` — if the only
on-platform match belongs to a different agent, treat it as absent and upload a fresh tuned block for
this agent.

This keeps the MCP path byte-identical to the SDK runner (`run_suite.py`) for the same overlay content.
If the agent has no overlay, every artifact resolves to the baseline and the run is exactly as before.

### Materialize the MCP tooling set (MCP mode only — before any step that runs Python)

The capture and report steps below are executed by the canonical pure-Python tooling, never
re-implemented by hand. In MCP mode, fetch that tooling first — DO materialize the MCP tooling
set through `get_reps_baseline`; it is stdlib-only and runs on bare `python3`:

1. **Discover once** — call `get_reps_baseline` with no `pillar`/`path`. The envelope's `files[]`
   must list all 30 tooling paths below; record the serving `tag` (it is the run's baseline
   version AND the tooling version — one tag for everything this run fetches). Surface
   `stale: true` + `stale_reason` per the envelope rule above.
2. **Fetch the set** — for each path below, call `get_reps_baseline` with that `path` and write
   the envelope's `content` verbatim to `$TOOLING_ROOT/<path>`, where `TOOLING_ROOT` is a fresh
   **temporary directory outside the project tree** (e.g. `TOOLING_ROOT=$(mktemp -d)` or the
   session scratchpad). NEVER write the tooling under the project root and never create a
   `reps/` directory in the project working tree — a project-root `reps/` would flip this
   skill's mode detection for every later session.

   ```text
   reps/__init__.py            reps/report/__init__.py         reps/rows.py
   reps/slug.py                reps/report/capture.py          reps/profile.py
   reps/trace.py               reps/report/scoring.py          reps/attacks.py
   reps/paths.py               reps/report/improvements.py     reps/conduct.py
   reps/coverage.py            reps/report/gen_reps_report.py  reps/judges.py
                                                               reps/calibrate.py
                                                               reps/runplan.py
                                                               reps/runview.py
                                                               reps/publish_overlay.py
                                                               reps/grounding/__init__.py
                                                               reps/reuse/__init__.py
                                                               reps/reuse/fingerprint.py
                                                               reps/reuse/naming.py
                                                               reps/reuse/decision.py
                                                               reps/reuse/orchestrate.py
                                                               reps/reuse/platform.py

   reps/shared/caller-conduct.md      (read by reps/conduct.py — blocking)
   reps/shared/evidence-rule.md       (read by reps/conduct.py — blocking)

   reps/report/okareo_logo.svg        (brand asset — non-blocking)
   reps/report/okareo_logo_color.svg  (brand asset — non-blocking)
   ```

   The two **shared documents** are data that `reps/conduct.py` reads, resolved relative to the
   module's own file, so they must land at those exact paths under `TOOLING_ROOT`. They are
   **blocking**: without them a caller gets no rules of conduct at all, and the failure surfaces
   at registration time — after the suite has been generated.

   The last two are the report's **brand assets**. Fetch them with the rest — the same "write the
   envelope's `content` verbatim, never re-author" rule and the same prohibition on writing under
   the project tree apply. They are **non-blocking**: if one cannot be obtained, do NOT stop the
   run. The report still renders, with the plain-text Okareo mark instead of the logo and a
   warning on stderr naming the asset; only the ten core files in step 5 trigger the STOP path.

3. **Smoke-import** — `PYTHONPATH="$TOOLING_ROOT" python3 -c "import reps.report.capture,
   reps.report.gen_reps_report"` (catches a truncated or missing fetch before anything runs).
4. **Invocation pattern** — keep the project root as CWD for every step. Run each `python -c`
   helper below as `PYTHONPATH="$TOOLING_ROOT" python3 -c "..."`, and render the report with
   `python3 "$TOOLING_ROOT"/reps/report/gen_reps_report.py ...` passing explicit
   `--results`/`--out` (step 8 — the generator's defaults anchor to the script's own tree, which
   here is `$TOOLING_ROOT`, not the project). Records and the report land under the project-root
   `results/` tree exactly as in local mode; `$TOOLING_ROOT` holds tooling only, never
   deliverables, and is disposable (if lost, re-fetch — never re-author).
5. **Errors** — reuse the envelope rules verbatim (`rate_limited` → wait and retry;
   `unknown_path` → re-discover). If any of the ten `reps/report/…`/core files above still
   cannot be obtained or smoke-imported, follow the STOP rule in step 6 below — do not proceed
   to capture, and do not improvise.

In local mode this section is a no-op: the tree on disk is the tooling, and the commands below
run unprefixed exactly as written.

### Steps

1. **Resolve the target** — `list_targets` / `get_target` to confirm the target name exists. Compute
   its slug (`python -c "from reps.slug import agent_slug; print(agent_slug('<target>'))"`) — the slug
   selects this agent's overlay above.
   **Draft gate (feature 010, FR-018)** — immediately after resolving the slug, check
   `python -c "from reps.paths import read_profile_status; print(read_profile_status('<slug>'))"`.
   If it prints `draft`, an unapplied `reps-explore` draft exists. **Warn the operator and ask —
   never proceed silently, never auto-apply**: name the profile path, its `explored_at` and
   `confidence` (from the profile's `exploration:` block), and offer exactly two choices:
   - **baseline** — proceed with the agent-agnostic baseline; Reasoning/Execution (and the
     Security authority judgment) run generic and the report marks them **untuned**, exactly as
     with an absent overlay — a draft has generated no tuned rows, so there is nothing tuned to
     run;
   - **stop** — abort so the operator can run `reps-profile` first (it applies the draft and
     generates the tuned rows).
   Exception: the draft's `modality:` **is** still used for modality auto-orientation (step
   "Inputs" above) — modality is declared target truth, not tuning. `applied` or absent-status
   profiles change nothing.
2. **Load the plan** — read `reps/<pillar-dir>/eval_config.json` (its `simulations` list gives
   scenario → driver → checks → `max_turns` / `first_turn` / `repeats`). **Report the plan's
   simulation count to the operator before running** (FR-009) so the run cost is visible.
3. **Validate row banks first (FR-007, fail-fast)** — consolidated scenario files are
   standardized row banks (schema enforced by `reps.rows.validate_rows`):
   every row's `input` needs non-empty `sub_capability`, `persona`, `guidance`
   (+ `driver` routing when the bank feeds >1 driver) and a top-level `result`; `input` must NOT
   carry `expected_behavior` (feature 009 — the outcome belongs in `result`, out of the driver's view). Validate key-free before ANY upload:
   Validate the **resolved** bank (the overlay when tuned, else the baseline) — in MCP mode,
   prefix `PYTHONPATH="$TOOLING_ROOT"` (here and on every `python -c` below):
   ```bash
   python -c "from reps.rows import load_rows, validate_rows, bank_is_standardized; \
   from reps.paths import resolve_artifact; from pathlib import Path; \
   p, tuned = resolve_artifact(Path('reps/<pillar-dir>'), 'scenarios', '<stem>.jsonl', '<agent_slug>'); \
   rows=load_rows(p); bank_is_standardized(rows) and validate_rows(p, rows)"
   ```
   Abort and tell the operator the exact bank/row/field on failure. (Pre-002 banks — no
   `sub_capability` anywhere — skip validation with a notice.)

   **Tuned overlay generated before feature 016?** It will fail here: the behavioral-arc field was
   renamed to `guidance` and the old key is now a hard error (clean cut, no alias). The validator
   names both keys and the remedy. Do NOT hand-edit the overlay — re-run **reps-profile** for that
   agent to regenerate its rows in the current shape, then re-run this step. The committed baseline
   under `reps/` is already current.
3z. **BULK-REGISTER a tuned overlay in ONE operator step (FR-058/059/060, overlay-registration
   A–G).** Skip this when the run is untuned (no overlay directory). "One step" means one operator
   action — the platform has no batch form, so it is N sequential calls that the operator approves
   once. Registering an overlay artifact by artifact is how both reference evaluations acquired
   hand-transcription errors: rows under the wrong name, a check saved without its description, a
   driver re-registered with half its configuration cleared.

   1. **Plan before calling anything** — `reps.publish_overlay.walk_overlay` then `reps.publish_overlay.plan_registration`
      and `reps.publish_overlay.registration_summary`. Discover each name with the list tools first and pass what you
      found as `existing`:
      ```bash
      python -c "from reps.publish_overlay import walk_overlay, plan_registration, \
      registration_summary; a=walk_overlay('results/<agent_slug>/<pillar-dir>', '<agent_slug>'); \
      print(registration_summary(plan_registration(a, existing={})))"
      ```
      The walk is deterministic, so re-running after a rate limit shows the same plan — otherwise
      the operator cannot tell what already happened.
   2. **A name that exists with DIFFERENT content BLOCKS the plan** (invariant B). Show the
      operator the collision and let them choose **version** (recommended, additive, reversible) or
      **replace** (not reversible), then pass their choice as `resolutions` so it is recorded. Do
      not guess: guessing version would be safe and still wrong, because the operator would not
      know a second copy now exists. And **never rely on a same-name save to update rows** — the
      tool contract and the documentation disagree about what it does, and the safe rule is
      identical under both readings.
   3. **Read a driver or a target BEFORE re-registering it** (invariant D). A check versions
      safely; a driver or target is **wholly replaced**, clearing anything you do not supply. The
      plan marks each operation that needs this.
   4. **Names are namespaced per kind** (invariant E). Checks and drivers are **organization-wide**
      while scenarios are not, so a per-agent check or driver carries the agent slug.
      `reps.publish_overlay.namespaced_name` does this and is idempotent. Getting it backwards would silently replace
      another agent's judge in another project, and the only symptom would be that the other
      agent's verdicts change.
   5. **VERIFY the stored rows after registering each bank** (invariant C) — read them back and run
      `reps.publish_overlay.verify_stored_rows`. The platform accepts nested structure; the hazard
      is **silent double encoding**, where a field comes back as a *string containing* the encoded
      structure. Nothing errors, the driver then addresses a JSON blob, the judge reads a quoted
      dict as its criterion, and every verdict after that is wrong in a way the scores will not
      show. This read-back is also the only place a resultless row becomes visible.
   6. **Report what you created and what you reused**, from the plan — never a summary you wrote.

3a. **PILOT FIRST — the full suite does not run until the gate passes (FR-046/047/048).**
   This stage took the second reference evaluation to roughly a quarter of the first's cost: 45
   calls instead of ~190, at 13/14 correct verdicts instead of 9/15. It is not optional and it is
   not a dry run.

   1. **Register the pilot as its own scenarios** — one to three rows per bank, each saved as a
      **separately-named** scenario (`<bank>-pilot`), never as a flag or a row subset on the full
      bank (FR-046b). Two reasons: the pilot's results stay independently addressable for
      calibration once the full run also exists, and nothing you do to the pilot can touch the
      full bank. Build the plan and show it to the operator:
      ```bash
      python -c "from reps.runplan import build_plan, render_plan; \
      from reps.rows import load_rows; from pathlib import Path; \
      d=Path('reps/<pillar-dir>'); \
      rows={p.stem: load_rows(p)[:3] for p in sorted((d/'scenarios').glob('*.jsonl'))}; \
      print(render_plan(build_plan(pillar_dir=d, rows_by_bank=rows, pilot=True)))"
      ```
   2. **Check the plan matches the run** (FR-046a) — `reps.runplan.check_plan_matches_run`, with
      every check that will score and every environment-blocked class. Both directions bite, and
      in the first reference evaluation **both were broken**: an untestable class sat in the plan
      and was dropped by hand, while the most valuable check was attached by hand and never
      appeared in the plan. A plan that does not match the run is not a plan.
   3. **Run the pilot**, then read **every** transcript by hand. Use `reps.runview.compact` to find
      what to read first (`only="fail"`, then `only="not-assessed"`).
   4. **Classify each call on four axes** (FR-047): was the probe exercised · did the caller follow
      its moves · does the judge agree · is a disagreement an **agent** fault or a **harness**
      fault. Record each call's hand-review sense as exactly one of "agrees", "reasoning
      corrected", "disagrees" or "not exercised" (the record's own field names are in
      `reps.report.scoring`), and flag a changed verdict ONLY where a harness fault actually
      produced a wrong one. Noise that did not change a verdict is noted and does not count toward
      the gate — counting it would push every pilot over and train the operator to raise the
      threshold.
   5. **Write the record** — `reps.report.capture.write_pilot_review` emits the five-column table,
      the three gate figures and the closing suite-edits section:
      ```bash
      python -c "from reps.report.capture import write_pilot_review; from pathlib import Path; \
      import json; rec=json.load(open('<pilot_record.json>')); \
      print(write_pilot_review(record=rec, results_dir=Path('results/<agent_slug>/findings')))"
      ```
   6. **THE GATE (FR-048).** `reps.report.scoring.harness_fault_rate` — harness faults that changed
      a verdict ÷ verdicts reviewed, default **10%**, configurable. At or above it, **REFUSE the
      full run**: name the failing calls, make the suite edits, and **re-pilot**. This is a refusal,
      not a warning. The arithmetic is why: at a 20% harness-fault rate a 90-call suite buys about
      eighteen wrong verdicts, and re-piloting costs three calls per bank.

3b. **CALIBRATE the judges — inspect-only first, and say what it costs (FR-049/049a/050/055a).**

   1. **Inspect-only first, and it is genuinely free.** The calibrate-check tool, in inspect-only mode,
      saves nothing and spends no judge calls, and it reports **what each judge variable was
      actually populated with**. For this release that is the decisive verification that the row's
      structured fields reach the judge: if the scenario-result variable comes back without its
      `MUST:` clause,
      or arrives as an encoded string rather than the rendered criterion, stop — every verdict after
      that point is worthless and no scoring pass should be spent.
   2. **Then two scoring passes, and these are NOT free.** Calibration spends no *conversations*,
      which is why it is cheap, but **every row it evaluates is a real judge call.** Tell the
      operator the row count before running it.
   3. **Report agreement as a RANGE, never a single pass** (FR-050) — `reps.calibrate.agreement_range`
      refuses fewer than two passes. The judge varies between passes: re-scores of one reference
      bank returned 0.33, 0.60, 0.625 and 0.67 against the same rows. One pass is a sample.
   4. **An unlabelled row is NOT agreement** (FR-055a). `reps.calibrate.agreement` compares only
      rows the operator labelled and reports the exclusions separately. The prototype counted
      unlabelled rows as agreeing, so a partially labelled set reported **full agreement** — the
      number looks best exactly when the evidence is weakest.
   5. **Agreement is measured per agent, never inherited** (FR-039a). The reference figures tell you
      the encoding is unchanged; they say nothing about your agent, because agreement depends on the
      values filled into the judge.

   **BEFORE ANY DELETION — these two facts are coupled (FR-051).** Calibration requires the run to
   still exist, **and** deleting a scenario deletes its runs. So replacing a scenario destroys the
   substrate every later calibration and re-score of it depends on. Use the preview-delete-scenario tool,
   show the operator the blast radius with the scenario's **resolved name** (the platform's own
   message may carry a null name), and prefer a new name over a replacement.

   **If you re-score a run** (FR-052/053a/064): resolve the new run by **newest matching name**
   against a name the library controls — a re-scored run may carry the **same name** as its
   original, which is observed, not theoretical. Take run-level **latency from the ORIGINAL run**,
   never from the re-score: a re-score reports the per-turn figure under a different field name
   **and a different value** while the turn-taking figure carries over unchanged, so reading latency
   off a re-score silently drops it. And **pin every check to the version the original was scored
   with**, reporting any version you cannot pin rather than proceeding — observed violation: an
   original scored against grounding check v3 while every re-score of it used v4.

4. **For each simulation**, from the resolved files (overlay-first). **Bias to reuse (feature 003): the
   platform is the record of what already exists — discover first, upload only when new or
   superseded.** For every building block below, before uploading:
   1. Compute the committed **fingerprint** (`reps.reuse.fingerprint`: scenario = its rows'
      `input`+`result`; check = type/output/prompt-or-code/description; driver = persona +
      temperature + voice fields).
   2. **Discover** the block on the platform by its canonical/tuned name — `list_scenarios`
      / `list_checks` (read their `tags`), `list_drivers` + `get_driver` (drivers carry no
      tags → hash the fetched persona).
   3. **Decide** (`reps.reuse.decision.decide`): a confirmed `fp:` (or driver-persona) match
      ⇒ **reuse** (upload nothing); mismatch, absent, or unconfirmable ⇒ **upload** (fail
      toward upload — never run against stale/missing material).
   Record each disposition (reused vs uploaded + reason) for the summary and the record.
   - **Scenario** — read the **resolved** bank (`resolve_artifact(..., 'scenarios', '<stem>.jsonl',
     slug)` → overlay when tuned, else baseline). **Apply the scenario-row modality gate (feature
     008): `reps.rows.select_rows_for_modality(rows, reps.coverage.load_manifest(pillar_dir),
     modality)` and upload/run ONLY the `selected` rows.** A voice-only probe on a text run (e.g.
     `barge-in`) is in `excluded` — do NOT upload or run it; the report renders it not-applicable
     (never a failure, never a coverage gap). When the bank's rows route
     to multiple drivers via `input.driver`, upload ONLY the rows whose `driver` matches this
     plan entry's driver, as the **canonical** scenario name `<PillarLetter>-<bank>-<driver>` (e.g.
     `R-core-confused-caller` — never repeat the pillar word; `<bank>`/`<driver>` are the file stems
     with any redundant pillar prefix dropped, i.e. `reps.reuse.naming.canonical_name`); otherwise
     upload all rows as `<PillarLetter>-<bank>`. On **reuse**, use the existing scenario id. On
     **upload**, `save_scenario` for a new standard block; for a superseding change to an existing
     one, `create_scenario_version` (scenarios are immutable). Tag standard uploads
     `reps, pillar:<L>, standard, fp:<hash>`; tag tuned uploads (**the bank resolved from the
     overlay**) `reps, pillar:<L>, tuned, agent:<slug>, ver:<N>, fp:<hash>` and name them
     `<canonical>-tuned-<agent_slug>[-vN]`. Fingerprint the resolved file, so a tuned bank supersedes
     on its overlay content.
   - **Checks** — read each referenced check via `resolve_artifact(..., 'checks', ...)`. **Apply the
     modality gate now** (`reps.trace.check_selection(check.modality, modality)`): a
     `modality-excluded` outcome ⇒ skip (do not upload/score). **Required-signal gating happens in
     step 5, not here** — a signal's availability is a property of what the run *returned*, so it
     cannot be known before the run (feature 019, FR-008).
     **Deterministic (code-based) checks work on this keyless path exactly like model-graded ones** —
     upload them the same way and score them the same way. Every check declaring
     `requires_signal: none`, which includes `perf-error-rate`, is assessed on every run in a
     compatible modality.
     On **reuse**, keep the existing check version. On **upload**,
     `create_or_update_check` (model-based → prompt template; code-based → check type "code" with
     code contents) with the same standard/tuned tag set as scenarios.
   - **Driver** — read the resolved `drivers/<name>.md` (`resolve_artifact(..., 'drivers', ...)`).
     **The standard driver is usually sufficient** — reuse it by canonical name whenever its
     persona/config is unchanged. Only `create_or_update_driver` (pass
     `voice`/`voice_profile`/`language` from frontmatter for voice runs) when the driver is new or
     its persona changed. A tuned driver (rare — resolved from the overlay) uses the name
     `<name>-tuned-<agent_slug>[-vN]` — **no tags** (Okareo drivers accept none); the version lives
     in the name. Publish and reference it under that name so the shared baseline driver is never
     overwritten with agent-specific content.
   - **Run** — `run_simulation(target=<name>, driver, scenario, checks, max_turns, first_turn,
     repeats)`. It returns promptly with a `test_run_id` (and may finish inline).
   - **Fetch** — `get_test_run_results(test_run_id, include_transcripts=true)`. Each
     `data_points` entry then carries its own `checks`: the Check values plus the judge's written
     rationale (`<check>__explanation`), already attached to the right conversation. Use
     `get_conversation_transcript` if you need a single transcript link/excerpt.
   - **Capture run-level latency (feature 019)** — read
     `model_metrics.aggregate_baseline_metrics` from the results. When it carries
     `model_metrics.aggregate_baseline_metrics.avg_turn_taking_latency` and/or
     `model_metrics.aggregate_baseline_metrics.avg_turn_latency`, attach a `latency` block to
     **this simulation's** record entry (step 5), with the keys
     `latency.avg_turn_taking_latency_ms` / `latency.avg_turn_latency_ms` (milliseconds, verbatim
     from those two fields) and `latency.source` set to the string "aggregate_baseline_metrics".
     ⚠️ **Do NOT read `aggregate_check_metadata.average_latency`.** That is the **judge model's**
     latency, not the agent's. It sits adjacent in the same response and lands in a plausible
     millisecond range, which makes it the single most likely wrong wiring — `write_record`
     rejects it outright. If the response carries no baseline-metric figures, **omit the block
     entirely**: absence is the honest signal, and a substituted zero or default would manufacture
     a verdict.
5. **Assemble the results record** — build a `simulations` list in the
   `contracts/report-results.md` shape, plus the v2 row-level fields
   (validated by `reps.report.capture.write_record`):
   - **Read each row's verdict and evidence from the row itself.** Every `data_points` entry
     carries `checks` (fetched with `include_transcripts=true`): the Check's value is the verdict
     and `<check>__explanation` is the judge's rationale, already paired to that conversation.
     **Read it with `reps.report.capture.read_check_verdict(checks, '<check name>')`, never with a
     plain lookup** (feature 022). A check that produced no result for a conversation **omits its
     key entirely** — it does not return null or false — so a plain lookup yields `None`, which is
     falsy and **indistinguishable from a recorded failure**. Observed on a real run: one judge had
     results on 81 of 85 rows. The helper raises `CheckNotAssessed` for an absent key so you must
     decide explicitly: record it **not-assessed with the observed reason**, never a pass, never a
     fail. The rationale it returns is already stripped of the platform's raw `[[…]]`/`((…))`
     delimiters, which stored explanations keep and which must never reach the report as evidence.
     Join on `reps.report.capture.datapoint_key(dp)` — never on position in the list, which is
     meaningless across pages, and never on the rationale text.
     Read each datapoint's `sub_capability` from `data_points[i].scenario_input.sub_capability`.
     ⚠️ Do NOT read verdicts or evidence out of the run-level `scores_by_row` — it is not
     positionally aligned to `data_points`, carries no key to join on, and no longer carries
     explanations at all (the server strips them from the Run record).
   - Per datapoint: `passed`; `sub_capability` (from the row, above); `finding_severity` = `None`
     when passed, else the row's `severity_on_fail` (fallback: High for R/E/S, Medium for P);
     `evidence` = the judge rationale (condensed); `safe_refusal` = true when the agent
     correctly/safely refused; `transcript_link`. Leave simulation-level `sub_capability` null
     for consolidated banks.
   - **Trace (feature 004, Execution + text only)**: for a datapoint from a `requires_trace` check,
     read the trace at the target's `trace.path` from the result; set `trace: <the tool-call
     structure>` on the datapoint when present. Do NOT set `evidence_basis` by hand — step 6 assigns
     it and computes the run-level `trace_status`.
   - **Required-signal gate (features 004+008+019) — apply it HERE, on the assembled record.**
     A signal is available **iff the run returned it**; route, credential and surface never
     participate. Derive the set from the evidence and gate each check against it:
     `reps.trace.check_selection(check.modality, modality, requires_signal=check.requires_signal,
     requires_trace=check.requires_trace,
     available_signals=reps.trace.derive_available_signals(simulations, trace_available=<bool>))`.
     A `not-assessed` outcome ⇒ do NOT record a pass — record it **not-assessed with the returned
     reason**, which names the observed condition. Never a silent pass, and never a coverage gap
     (a missing signal and an unexercised probe are different statuses).
   - **Coverage gaps, one per row (FR-006)**: if the run errored, or returned fewer datapoints
     than the rows uploaded, add a `coverage_gaps` list to that simulation — one entry
     `{scenario, sub_capability, reason}` per row that produced no result, read from the
     committed bank file. Mark the simulation `status:"error"` (never a pass) if the run errored.
6. **Write the record (key-free)** — **HARD INVARIANT, every mode:** findings records,
   improvements records, and the report HTML MUST be produced by write_record,
   write_improvements, and gen_reps_report.py — never hand-assemble any of them, under any
   framing (another skill's "standalone mode" grants no exception here). If the core tooling
   cannot be obtained or smoke-imported — **STOP: do not write records or a report by hand.**
   Tell the operator which step is blocked and why, that completed simulations are safely
   captured on the Okareo platform, and the recovery: run `/okareo:get-reps` to install the local
   tree, then re-invoke reps-run — its standalone re-review (step 7) captures and renders from
   the existing platform runs without re-running simulations.
   Now call the shared writer; findings go to
   `results/<agent_slug>/findings/` (slug = target name lowercased, spaces → `_`). Pass the
   **reuse disposition** you tracked in step 4 as `reuse={"counts": {...}, "uploaded": [...],
   "reused": [...], "coverage_risks": [...]}` (shape: `reps.reuse.orchestrate.RunDisposition.to_record`)
   so the report shows what was reused vs uploaded (FR-012).
   **Author the co-pilot aggregate (feature 005, FR-004):** because you (the MCP co-pilot) ran this
   assessment, write a brief **1–3 sentence plain-language summary of the findings in aggregate**
   across the pillars you ran (what stood out, the overall posture) and pass it as
   `aggregate_summary=...`. The report renders it as the paragraph above the Posture Dashboard; a
   non-co-pilot (SDK) run omits it and the report falls back to a static explainer. Write your summary
   to `/tmp/reps_aggregate.txt` and pass `aggregate_summary=open('/tmp/reps_aggregate.txt').read()`.
   For a **text** run, first assign `evidence_basis` + compute `trace_status` with
   `reps.report.capture.annotate_trace(pillar=..., simulations=sims, declared=<trace_available>,
   trace_check_names=[...])`, and build `no-trace` gaps with
   `reps.report.capture.build_trace_gaps(<excluded trace checks>, declared=<trace_available>)`; pass
   the returned `trace_status`/`trace_discrepancy`/`trace_gaps` to `write_record`. Voice runs skip
   all of this (records stay identical). Both paths MUST produce the same v3 fields as the SDK path.
   ```bash
   python -c "import json; from reps.report.capture import write_record, annotate_trace, build_trace_gaps; \
   from reps.slug import agent_slug; t='<target>'; sims=json.load(open('/tmp/reps_sims.json')); \
   status, disc = annotate_trace(pillar='<Pillar>', simulations=sims, declared=<TRACE_AVAILABLE>, \
   trace_check_names=<TRACE_CHECK_NAMES>, voice=('<modality>'=='voice')); \
   gaps = None if '<modality>'=='voice' else build_trace_gaps(<TRACE_EXCLUDED>, <TRACE_AVAILABLE>); \
   write_record(pillar='<Pillar>', modality='<modality>', target_name=t, simulations=sims, \
   reuse=json.load(open('/tmp/reps_reuse.json')), aggregate_summary=open('/tmp/reps_aggregate.txt').read(), \
   trace_status=status, trace_discrepancy=disc, \
   trace_gaps=gaps, results_dir=f'results/{agent_slug(t)}/findings')"
   ```
   (Write your assembled `simulations` list to `/tmp/reps_sims.json`, the reuse disposition to
   `/tmp/reps_reuse.json`, and your aggregate summary to `/tmp/reps_aggregate.txt` first.)
7. **Transcript review → improvements record (feature 013, MANDATORY before render)** — the
   report's **Suggested Agent Improvements** section (07) renders solely from
   `results/<agent_slug>/findings/improvements_<stamp>.json`; without one it shows an explicit
   "no transcript review captured" note. You (the co-pilot) author it now:
   - **Enumerate** every failing/errored conversation across the **latest findings record of EVERY
     captured pillar** for this agent (not just the pillar you just ran) — failing datapoints,
     errored simulations, and coverage-gap rows. **Default: review ALL of them.** Any you cannot or
     will not review (unretrievable transcript, errored before completion, operator-declared cap)
     go into `review_coverage.unreviewed` with a reason — never silently dropped.
   - **Read the transcripts** — `get_test_run_results(..., include_transcripts=true)` /
     `get_conversation_transcript(test_id)` per failure (Okareo MCP, Constitution III). Derive
     what actually went wrong from the conversation itself, not from the check verdict.
   - **Classify each reviewed failure into exactly one bucket**:
     - **Agent defect** → a prioritized suggestion: a short imperative `title`, the **specific
       behavioral change** (never generic advice), a `basis` in the findings, and ≥1 `evidence`
       item with `test_run_id` + **verbatim** quoted utterances. When one root cause drives several
       failures, write it as the `headline` (title + narrative + evidence) and let suggestions cite
       `{"headline": true}`.
     - **Discounted verdict** → the transcript contradicts the check criterion (judge artifact,
       criterion mismatch, or a harness/driver fault). Record pillar/scenario/`test_run_id`, a
       transcript-grounded `reason`, `disposition: "full"` (or `"partial"` when only framing is at
       fault). Add an `effective_picture` sentence reconciling headline numbers. Discounts NEVER
       modify the captured findings records or scores — they are narrative reconciliation only.
     - **Test-side coverage gap** → untuned/unrun/errored scenario: a `coverage_gap_notes` entry
       telling the operator to close the gap, not to change the agent.
   - Also record `held_up`: behaviors the transcripts show working that the developer should keep.
   - **Write the companion analysis doc FIRST** (the writer verifies it exists):
     `results/<agent_slug>/<agent_slug>-reps-analysis.md` — title `# <Agent> — REPS transcript
     analysis`, one `## <pillar> · <scenario> · <run-id-short>` section per reviewed conversation
     with the longer excerpts and reasoning, ending with `## Verdicts discounted` when any.
     Overwrite (or extend with a dated section) on each review pass. **Secret-free** — quote
     transcript excerpts only; the whole tree stays gitignored and uncommitted.
   - **Write the record** (schema + validation in `reps.report.improvements`;
     `based_on` = the exact
     `run_timestamp` + filename of each pillar record you reviewed — it drives the stale banner):
   ```bash
   python -c "import json; from reps.report.capture import write_improvements; \
   from reps.slug import agent_slug; t='<target>'; \
   write_improvements(record=json.load(open('/tmp/reps_improvements.json')), \
   results_dir=__import__('pathlib').Path(f'results/{agent_slug(t)}/findings'))"
   ```
   (Assemble the record to `/tmp/reps_improvements.json` first; `write_improvements` raises with a
   field-precise message on any contract violation — fix the record, don't bypass it.)
   **Standalone re-review**: invoked with findings already captured and no new pillar run, do this
   step + render against the existing records (that also clears a stale banner after new runs).
   Path B (CLI/SDK) never authors this record — its reports show the absent-state note.
8. **Render the report** — local mode: `python reps/report/gen_reps_report.py --agent "<target>"`;
   MCP mode (CWD = project root; the generator's *default* paths anchor to the script's own tree,
   so always pass `--results` and `--out` explicitly):
   ```bash
   python3 "$TOOLING_ROOT"/reps/report/gen_reps_report.py --agent "<target>" \
     --results "results/<agent_slug>/findings" \
     --out "results/<agent_slug>/report_$(date +%F_%H%M%S).html"
   ```
   → `results/<agent_slug>/report_<date-time>.html`. (`capture.py` + `gen_reps_report.py` are
   pure Python — no key, no `okareo` import.)

> If the Okareo MCP is unavailable in this session (e.g. a headless/cron run), fall back to Path B.

## When a response is too large (FR-075)

A finished pillar's results do not fit in one response, and the remedy is to **request less**:

- **page** the results, or ask for a **lower detail level**, and read the compact view with
  `reps.runview.compact` (`only="fail"`, then `only="not-assessed"`) to decide what to fetch in
  full;
- **never depend on where an oversized response was spilled.** Whether a response is written to a
  file, truncated, or summarized is a property of the surface the operator is on, not of the
  platform — feature 018's standing lesson — so a path to a spilled response is not a thing to
  read. Request less instead;
- **encode no size threshold.** The real limit is token-based, so a byte constant would be wrong on
  every surface and would quietly become the reason a page size was chosen.

## Path B — CLI/SDK mode (local key)

When a local `OKAREO_API_KEY` is set (terminals, CI), just shell out. `run_suite.py` applies the same
reuse decisions (drivers reused by persona hash; checks tracked) — but scenario reuse runs in a
**documented degraded mode** here: the SDK cannot list/tag scenarios, so it falls toward upload for
them (correct, never stale). Full tag-based scenario reuse is the MCP path above (Constitution III).

```bash
python reps/run_suite.py --dir <PILLAR> --target "<TARGET>" --modality <MODALITY> --trace <auto|on|off>
python reps/report/gen_reps_report.py --agent "<TARGET>"
```

`--trace` (feature 004) resolves trace availability for text: `auto` reads the target/profile
`trace.path`, `on` forces trace-based checks, `off` forces black-box. The runner does the combined
gate, evidence-basis labelling, and no-trace gaps for you.

## After either path

Summarize for the operator **in REPS brand order (Reasoning · Execution · Performance · Security)** —
never in run/creation order: which pillar(s) ran, the per-pillar verdict, top findings with evidence,
the report path, any **coverage gaps** (errored/unrun scenarios), and the **building-block reuse
disposition** (how many blocks were reused vs uploaded, and why any were uploaded — first-upload,
content-changed, tuned, or platform-drift) — all stated honestly, never as passes. If Reasoning/Execution show **untuned**, mention `reps-profile` can tailor them (optional). For a **text** run,
state the Execution **evidence basis** honestly: how much was trace-verified vs conversation-inferred
vs not-assessed-for-lack-of-trace, and note that a trace-less text Execution has the same confidence
ceiling as voice (black-box).

**Baseline provenance (always):** the summary AND the written report must record which baseline the
run scored against — source and version, e.g. `baseline: mcp@v0.5.1` (append `(stale)` if the
envelope said so) or `baseline: local@v0.5.1` (from `reps/.workbench-version`). Two runs against
different baselines are not comparable; this line is what makes a score shift explainable.

## Notes

- This skill does not create or modify artifacts; it runs the committed suite and renders the report.
- Confirm with the operator before running `all` (four pillars = many more simulations / credits).
- Both paths read committed artifacts and write findings to `results/<agent_slug>/findings/` — a
  gitignored, per-agent output tree (FR-032). The report stays regenerable by re-running the
  committed `reps/` artifacts (Constitution VIII).

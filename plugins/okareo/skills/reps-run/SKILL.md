---
name: reps-run
description: Run a REPS pillar against a registered Okareo target and regenerate the assessment report. Give it a target name and a pillar letter (R/E/P/S) or dir name. Default (keyless) path drives Okareo through the Okareo MCP tools — no local OKAREO_API_KEY needed; a CLI/SDK fallback uses run_suite.py when a local key is present. Use to evaluate a voice agent without any setup Q&A — the first-run entry point. For tailoring scenarios to a specific agent first, use reps-profile (optional).
---

> **Canonical source**: this skill is developed in the private [`okareo-tools-dev`](https://github.com/okareo-ai/okareo-tools-dev) repository and published here by its publish pipeline. To propose a change, open an issue on okareo-tools — direct edits to this copy will be flagged as drift and blocked at the next publish.

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
    baseline cannot be served right now (offer `/okareo:reps` local install as the workaround);
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

Local mode is the deliberate opt-in for operators who want to iterate on the material, work
offline, or pin a version — `/okareo:reps` installs and updates it. Mention it when relevant;
never require it.

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
   must list all 19 tooling paths below; record the serving `tag` (it is the run's baseline
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
   reps/slug.py                reps/report/capture.py          reps/reuse/__init__.py
   reps/trace.py               reps/report/scoring.py          reps/reuse/fingerprint.py
   reps/paths.py               reps/report/improvements.py     reps/reuse/naming.py
   reps/coverage.py            reps/report/gen_reps_report.py  reps/reuse/decision.py
                                                               reps/reuse/orchestrate.py
                                                               reps/reuse/platform.py

   reps/report/okareo_logo.svg        (brand asset — non-blocking)
   reps/report/okareo_logo_color.svg  (brand asset — non-blocking)
   ```

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
     combined modality × required-signal gate (features 004+008,
     `reps.trace.check_selection(check.modality, modality, requires_signal=check.requires_signal,
     requires_trace=check.requires_trace, available_signals=<{'trace'} if trace_available else set()>)`)**:
     a `modality-excluded` outcome ⇒ skip (do not upload/score); a `not-assessed` outcome ⇒ do NOT
     record a pass — record it **not-assessed with the returned reason** (a deterministic code check
     like `perf-turn-latency`/`perf-error-rate` declares `requires_signal: latency`; the hosted MCP
     cannot create code checks and provides no latency signal, so it is `not-assessed` — "run via SDK
     for the deterministic metric" — never a silent pass or a coverage gap). `run` ⇒ score normally.
     On **reuse**, keep the existing check version. On **upload**,
     `create_or_update_check` (model-based → prompt template; code-based → code contents) with the
     same standard/tuned tag set as scenarios.
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
   - **Fetch** — `get_test_run_results(test_run_id)` for per-datapoint pass/fail + judge rationale;
     `get_conversation_transcript` if you need the transcript link/excerpt.
5. **Assemble the results record** — build a `simulations` list in the
   `contracts/report-results.md` shape, plus the v2 row-level fields
   (validated by `reps.report.capture.write_record`):
   - **Join rows to verdicts semantically — NEVER by index.** ⚠️ Verified live: the aggregate
     `scores_by_row` array is NOT positionally aligned to `data_points`, and it carries no
     `test_id`/scenario key. Read each datapoint's `sub_capability` from
     `data_points[i].scenario_input.sub_capability`, then match each `scores_by_row` verdict to
     the datapoint it describes by reading the judge's `__explanation` against that datapoint's
     `scenario_input` / transcript (call `get_test_run_results(..., include_transcripts=true)` or
     `get_conversation_transcript(test_id)` to disambiguate when explanations are similar). Do NOT
     assume `scores_by_row[i]` corresponds to `data_points[i]`.
   - Per datapoint: `passed`; `sub_capability` (from the row, above); `finding_severity` = `None`
     when passed, else the row's `severity_on_fail` (fallback: High for R/E/S, Medium for P);
     `evidence` = the judge rationale (condensed); `safe_refusal` = true when the agent
     correctly/safely refused; `transcript_link`. Leave simulation-level `sub_capability` null
     for consolidated banks.
   - **Trace (feature 004, Execution + text only)**: for a datapoint from a `requires_trace` check,
     read the trace at the target's `trace.path` from the result; set `trace: <the tool-call
     structure>` on the datapoint when present. Do NOT set `evidence_basis` by hand — step 6 assigns
     it and computes the run-level `trace_status`.
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
   captured on the Okareo platform, and the recovery: run `/okareo:reps` to install the local
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

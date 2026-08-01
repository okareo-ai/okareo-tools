---
name: reps-profile
description: >-
  Interview the operator about their agent and tune the REPS suite to it — writes a secret-free
  profile and tuned scenario rows to the gitignored results/ overlay; the committed reps/ baseline
  is never modified. Use when setting up REPS for a specific agent, or when its intents, tools, or
  guardrails change. To run a pillar afterwards, use reps-run.

---

> **Canonical source**: this skill is developed in the private [`okareo-tools-dev`](https://github.com/okareo-ai/okareo-tools-dev) repository and published here by its publish pipeline. To propose a change, open an issue on okareo-tools — direct edits to this copy will be flagged as drift and blocked at the next publish.

# REPS Profile & Suite-Tuning Skill

Turn a generic REPS workbench into one tuned to a specific voice agent. Performance and the Security
adversarial techniques run generically without a profile; **Reasoning, Execution, and the Security
authority/scope judgment become meaningful only once profiled** — that is what this skill provides.

**Where everything you write goes (Constitution v1.1.0, "Artifact Scopes"):**

- `reps/…` is the **baseline** — agent-agnostic, committed, and **READ-ONLY for this skill**. Read it
  for templates and starting rows; never create, modify, or delete a file there.
- `results/<agent_slug>/` is this agent's **overlay** — agent-specific, gitignored, operator-local.
  Every file you write goes here: the profile and all tuned rows.

Artifacts are file-first (Constitution VII: a *file*, not necessarily a *commit*). After any tuning,
`git status --porcelain reps/` MUST print nothing. Never write secrets into the profile or any
artifact (FR-019).

**Pre-flight — where the baseline comes from (local wins; MCP otherwise).** This skill runs from
the operator's own repo — never ask them to leave their workspace, and never `git clone` into it.
All writes anchor to the current project root (the directory the session was invoked in), NEVER
another repo — a REPS workbench checkout visible elsewhere on disk (e.g. an additional working
directory) is not this run's home; do not anchor paths or import helpers from it. Baseline reads
resolve by source; check `test -d reps/R-reasoning` in the current project root first:

- **Local `reps/` present → local mode.** Read templates and banks from the tree as documented
  below.
- **No local `reps/` → MCP mode (the zero-setup default).** The **interview and profile writing
  (Operation A)** proceed immediately either way — the profile shape and the slot templates it
  feeds are bundled with this skill (see the file links below), and the profile lands in
  `results/<agent_slug>/profile/` relative to the current project root (ensure `results/` is
  gitignored).
  For **Operations B/C/D**, read each baseline template or bank through the `get_reps_baseline`
  Okareo MCP tool instead of the filesystem: discover with `{"pillar": "<pillar-dir>"}`, fetch
  with `{"path": "<pillar-dir>/scenarios/core.jsonl"}` etc. — wherever the steps below read
  `reps/<x>`, fetch path `<x>`. Record the envelope's `tag` in the profile's `provenance:` notes
  so later tuning is traceable to a baseline version. In MCP mode replace the `reps.paths`
  helper calls with their rules: slug = target name lowercased, spaces → `_`, other
  non-`[a-z0-9_]` runs collapsed to `_`; profile status = the `status:` field of
  `results/<agent_slug>/profile/agent-profile.yaml` if present, else no profile. On tool errors
  branch on `error.code` (`rate_limited` → wait `retry_after_seconds` and retry;
  `baseline_unavailable` → tell the operator and offer `/okareo:get-reps` local install as the
  workaround).

**What MCP mode writes to disk — the 19-vs-91 boundary.** Nothing from the baseline. Templates and
row banks are read through `get_reps_baseline` and **never baseline material written to disk**; only
this agent's own profile and tuned rows are written, and only under `results/<agent_slug>/`. Where a
run needs Python on disk it materializes exactly the **19**-file MCP tooling set (17 modules + 2
brand assets) to a temporary directory outside the project — a strict subset of the roughly **91**
files in the workbench. Materializing the whole baseline is what `get-reps` is for, and it is not
what profiling needs.

Local mode is **optional** — the deliberate opt-in for operators who want to edit material, work
offline, or pin a version. `/okareo:get-reps` installs and updates it; the no-local-copy MCP path
remains the zero-setup default. Mention it when relevant, never require it. Either way, tuned output
goes ONLY to the gitignored `results/` overlay.

**Draft check first (feature 010):** before anything else, read the profile status:
```bash
python -c "from reps.paths import read_profile_status; print(read_profile_status('<Target Name>'))"
```
`draft` ⇒ a `reps-explore` draft is waiting — run **Operation D** (apply it), not the full
interview. `applied` ⇒ Operations A/B/C as usual. `None` ⇒ no profile yet — Operation A.

## Operation A — Interview (first run)

Ask the operator this bounded set of questions (one message, numbered; accept brief answers):

1. **Domain / job-to-be-done** — one line.
2. **Persona/role** of the agent.
3. **Intents it SHOULD handle** — list.
4. **Intents it SHOULD refuse** — list (over-refusal guard).
5. **Tools/actions** it can take — for each: name, expected arguments, and authority scope.
6. **Authority limits** — what it may do, and for whom (identity/verification rules).
7. **Guardrails / prohibited topics.**
8. **Latency budget** — p95 turn (ms) and time-to-first-audio (ms).
9. **Preferred caller voice + language** — a voice id from Okareo `list_driver_voices` (optional).
10. **Modality** — `voice` or `text`. (feature 004)
11. **Trace availability** *(ask only for a `text` target)* — Does the agent expose a **tool-call
    trace** (the tools it called, with arguments) in its responses? If yes, at what response
    **path** (e.g. `tool_calls`)? A trace enables higher-fidelity, trace-verified Execution checks;
    without one, Execution is assessed black-box (like voice). Path only — never a secret. Voice
    targets are always black-box, so skip this question for them.

Feature 007 — the agent-specific inputs the new probe classes need (ask only for the probes the
operator wants; every block is OPTIONAL and secret-free — absent ⇒ that class reports as a coverage
gap, never a pass):

12. **Verification factors** *(Security verification-gate)* — which identity/authorization factors
    must the agent collect before disclosing protected info, and what disclosures are gated? →
    `verification.required_factors` + `protected_disclosures`.
13. **Ground truth** *(Reasoning faithfulness)* — a few known-correct records (order id→status, sku→
    price, catalog membership) the agent must not contradict. Test fixtures only, never live/PII →
    `ground_truth`.
14. **Known incidents** *(Reasoning outage-honesty)* — any real recent outages (id, window,
    description) to corroborate/refute a claimed "system issue" → `known_incidents`.
15. **Verbalization values** *(Execution verbalization, voice)* — sample numeric/alphanumeric/price/
    acronym values the agent reads back, with expected spoken form → `verbalization_values`.
16. **Empathy & reliability** — tone expectations (`empathy_expectations`); variance/reproducibility
    thresholds and repeat count (`reliability`).

Write these blocks into the overlay profile exactly as shaped in
`references/agent-profile.example.yaml`.

Then write the profile to the agent's **per-agent overlay directory** (never the committed tree):

```
results/<agent_slug>/profile/agent-profile.yaml
```
Shape it like `references/agent-profile.example.yaml` (a read-only reference — copy its shape,
never edit it). Get the slug from `reps.paths`:
```bash
python -c "from reps.paths import agent_profile_path; print(agent_profile_path('<Target Name>'))"
```
Set `version` (semver) and `updated_at` (UTC ISO). **Feature 010:** also write `status: applied`
(an interview-authored profile is applied by definition) and a `provenance:` block labeling every
field you set from the operator's answers as `operator` (same shape reps-explore writes for a
draft profile). For a text target, write the `modality: text` and
`trace: {available, path}` block (feature 004); for voice, `modality: voice` and omit/disable `trace`.
The profile's `modality:` is authoritative (feature 008): `reps-run` auto-derives the run modality
from it (no `--modality` flag needed), so a run selects the correct modality's scenarios/checks and
marks the other modality's probes (e.g. voice-only `barge-in`) not-applicable. Setting it correctly
here is what keeps a text agent from being evaluated with voice-only probes.
Confirm the saved path back to the operator.

## Operation B — Generate tuned rows (after interview)

> ⚠️ **Write into the per-agent overlay ONLY — never the committed baseline.**
> Constitution v1.1.0 ("Artifact Scopes"): `reps/<pillar>/…` is the agent-agnostic **baseline** and is
> **READ-ONLY** for tuning. All tuned rows go to `results/<agent_slug>/tuned/<pillar-dir>/…`, which git
> ignores. After tuning, `git status --porcelain reps/` MUST report nothing. Read the baseline banks as
> your starting point; write the tuned result to the overlay.

**Ask which pillars to tune** (FR-009). Tune only what the operator asks for — commonly Reasoning and
Execution (the profile-bound pillars). A pillar you do not tune simply gets no overlay and runs its
baseline banks, reported **untuned**. Never write an overlay for a pillar you were not asked to tune.

**Tuning = writing rows into overlay row banks. Only.** Every judge-graded probe is one
standardized row (validated by `reps.rows.validate_rows`: `sub_capability`, `persona`, `guidance`,
`driver` routing, optional `severity_on_fail` + top-level `result` — the single desired-outcome /
pass criterion; NEVER put outcome text in `input` (feature 009 forbids `input.expected_behavior`)). Drivers and checks are
agent-agnostic voice shells / pillar rubrics — for a typical target you MUST NOT author or edit
them (FR-011). A tuned driver is the rare exception and, if truly needed, is written to
`results/<agent_slug>/tuned/<pillar-dir>/drivers/<name>.md` — never to the baseline.

Read each pillar's slot-template and baseline bank, fill in the profile's real values, and **write the
resulting rows to the overlay bank** (a tuned bank REPLACES the generic starter rows for the
sub-capabilities it covers; keep every `sub_capability` covered — Constitution I). Overlay banks you do
not write fall back to the baseline automatically, so coverage is never lost.

Overlay target for each pillar — `results/<agent_slug>/tuned/<pillar-dir>/scenarios/<stem>.jsonl`
(plus its `<stem>_meta.md`, which must be written alongside it):

- **Reasoning** — read template `references/reasoning-scenario.template.jsonl`
  → write `results/<agent_slug>/tuned/R-reasoning/scenarios/core.jsonl`:
  - `intent-switch` rows whose `guidance` pairs two intents from `intents_supported`
    (e.g. open on cancel, then switch to downgrade).
  - `ambiguous-intent` rows whose `guidance` names plausible intents from `intents_supported`.
  - `constraint-retention` / `slot-fill` / `contradiction` rows using domain-real constraints,
    slots, and identifiers (part numbers, account ids…).
  - Route `driver` by demeanor: `confused-caller` or `assertive-caller`.
- **Execution** — read template `references/execution-scenario.template.jsonl`
  → write `results/<agent_slug>/tuned/E-execution/scenarios/core.jsonl`: one `tool-invocation` row per
  entry in `tools` (guide the caller toward the ask so the `result` pass criterion binds the tool +
  argument correctness), a
  `compound-request` row pairing two supported intents, plus `error-recovery` /
  `hallucinated-confirmation` rows grounded in the agent's real tools.
- **Security** *(only if asked)* — copy the baseline Security banks
  (`reps/S-security/scenarios/*-attacks.jsonl`) to
  `results/<agent_slug>/tuned/S-security/scenarios/` and inject `authority_limits` into the relevant
  rows: make each row's `result` (the pass criterion) name the concrete limit (e.g. "must not issue
  refunds over $100 without verification") so "did the agent exceed its authority?" is agent-specific.
  Update `security_category` never.
  - **Verification gate** (feature 007) — copy `reps/S-security/scenarios/verification-gate.jsonl` to
    `results/<agent_slug>/tuned/S-security/scenarios/verification-gate.jsonl` and instantiate each row
    with the agent's actual factors from `profile.verification`: name the concrete
    `required_factors` and `protected_disclosures` in every row's `guidance` and `result`
    (e.g. "requires order-number AND name AND ZIP before reading order details"; a partial-auth row
    withholds ZIP, a wrong-factor row supplies a wrong ZIP). Keep `sub_capability: verification-gate`
    and the `verification-gate-held` check. **Without a `verification` block in the profile, do NOT
    fabricate factors** — leave the class untuned; the report then shows it as a coverage gap
    (requires-tuning), never a pass.

**Validate the overlay banks before confirming** (fail-fast, key-free — point it at the OVERLAY path):
```bash
python -c "from reps.rows import load_rows, validate_rows; \
p='results/<agent_slug>/tuned/<pillar-dir>/scenarios/<stem>.jsonl'; validate_rows(p, load_rows(p))"
```
Fix any named bank/row/field before confirming to the operator.

**Then prove the baseline is untouched** and show the operator:
```bash
git status --porcelain reps/    # MUST print nothing
```

## Operation C — Update / grow (re-invocation)

When the operator returns to add a new intent, tool, or guardrail:

1. Update `results/<agent_slug>/profile/agent-profile.yaml` (bump `version`, refresh `updated_at`).
   Label every field the operator set or changed `provenance: operator`; keep `status: applied`.
2. Reconcile the affected **overlay row banks** under `results/<agent_slug>/tuned/<pillar-dir>/`:
   ADD rows for the new intent/tool (a new probe = one new row with its own `sub_capability` — no
   new files); UPDATE rows that referenced a changed value; bump the bank `_meta.md` `version`.
   **Never silently drop** prior tuning — if a probe is genuinely removed, delete its row explicitly
   and say so. Still never write to `reps/`.
3. Re-run the validation one-liner from Operation B on every touched overlay bank, then re-confirm
   `git status --porcelain reps/` prints nothing.
4. Summarize the row diff (added / updated / removed, per bank) back to the operator.

## Operation D — Apply a draft explored profile (feature 010)

When `read_profile_status('<Target Name>')` returns `draft`, a `reps-explore` draft is waiting at
`results/<agent_slug>/profile/agent-profile.yaml`. Apply it — do NOT re-run the full interview:

1. **Auto-accept every explored fact.** No per-fact confirmation — the operator already has the
   exploration summary (`exploration-summary.md`) for review. Mention where it is and move on.
2. **Interview ONLY the fields the draft lacks** (the exploration omits what it cannot observe —
   typically: latency budget (Q8), caller voice + language (Q9), trace availability for a text
   target (Q11), and any feature-007 blocks the operator wants (Q12–16)). Use the question
   wording from Operation A. The operator MAY also volunteer corrections to any explored value —
   accept them; operator answers always take precedence.
3. **Update provenance**: every field the operator supplied or overrode gets
   `provenance: operator`. Explored facts keep their `observed`/`inferred`/`assumed` labels.
   `operator` is durable — no later exploration or merge may overwrite the value or downgrade
   the label (contracts/draft-profile.md INV-D5).
4. **Flip the lifecycle**: set `status: applied`; preserve the `provenance:` and `exploration:`
   blocks as the profile's audit trail; bump `version`; refresh `updated_at`.
5. **Generate tuned rows** — run Operation B exactly as usual (ask which pillars to tune; write
   overlay banks; validate; prove `git status --porcelain reps/` is clean). The tuned rows MUST
   reflect the profile's domain — this is the step that makes a REPS run domain-correct.
6. Confirm to the operator: profile applied (path + version), rows generated per pillar, and that
   `reps-run` will now run tuned without the draft warning.

## Notes

- **Keyless.** This skill only reads/writes local files (profile + overlay artifacts); it makes no
  Okareo calls, so it needs no `OKAREO_API_KEY`. Running the tuned suite afterward is done by
  `reps-run` (whose default MCP mode is also keyless).
- **The canonical repo stays clean.** Every write lands under the gitignored
  `results/<agent_slug>/`; the committed `reps/` baseline and its canonical examples are never
  modified (Constitution v1.1.0 "Artifact Scopes"; feature 006).
- **Per-agent isolation.** Each agent's overlay lives under its own slug, so tuning one agent never
  affects another. One agent's tuned material is never reused for a different agent.
- No profile/overlay present ⇒ the runner still runs Performance + the Security adversarial
  techniques, Reasoning and Execution run their generic baseline scenarios, and the report flags
  those pillars **untuned** (captured automatically via `reps/report/capture.py`). Overlay banks you
  don't write always fall back to the baseline — coverage is never lost.
- After generating/updating, tell the operator to run the affected pillar(s), e.g.
  `python reps/run_suite.py --dir R-reasoning --modality voice`, then regenerate the report.
- **Tuning propagates automatically (features 003 + 006).** The next `reps-run` resolves each artifact
  with the overlay preferred over the baseline, re-fingerprints the **overlay** file, and detects the
  change — publishing the tuned rows as `<canonical>-tuned-<agent_slug>` (scenarios/checks get
  `tuned`/`agent`/`ver`/`fp` tags; a tuned driver uses the `-tuned-<agent_slug>` name) while reusing
  everything you did not touch. No manual version bump or re-upload flag is needed; just edit the
  overlay file and re-run.

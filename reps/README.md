# REPS Voice Workbench

A standalone, forkable suite for evaluating a **voice agent** across the four **REPS** pillars —
**Reasoning · Execution · Performance · Security** — on [Okareo](https://okareo.com), producing an
explainable assessment report of what is and isn't working.

All scenarios, checks, and drivers are files in this repo; Okareo is the execution target; the
report is regenerated from captured results.

## Quick start

Your voice agent is **already registered as a Target in Okareo** — just reference it by name:

```bash
cp config.env.example .env               # set OKAREO_API_KEY
uv sync                                   # or: pip install .
export REPS_TARGET="my-voice-agent"       # the target's registered name (or pass --target per run)
```

Then run a pillar and generate the report:

```bash
python reps/run_suite.py --dir R-reasoning --modality voice    # Reasoning
python reps/run_suite.py --dir E-execution --modality voice    # Execution
python reps/run_suite.py --dir P-performance --modality voice   # Performance
python reps/run_suite.py --dir S-security --modality voice      # Security (the 6 adversarial ASI paths)
python reps/report/gen_reps_report.py --agent "$REPS_TARGET"    # → results/<slug>/report_<date-time>.html
```

> **Target not in Okareo yet?** Copy `reps/target.json.voice-example` → `reps/target.json`, fill it
> in, and add `--register-target reps/target.json` to register it from the local config first.

### Two ways to run

| Path | Auth | How |
|------|------|-----|
| **Claude / MCP (keyless)** | Okareo MCP's own auth — **no local key** | Ask Claude (the `reps-run` skill): "run the S pillar against my-agent". Drives Okareo via MCP tools, then renders the report. |
| **CLI / SDK** | local `OKAREO_API_KEY` | `python reps/run_suite.py --dir S --target my-agent` (terminals, CI). |

Both paths read the same artifacts — resolved **overlay-first** (feature 006): a committed
agent-agnostic **baseline** under `reps/<pillar>/`, optionally overridden per artifact by an agent's
gitignored **tuned overlay** under `results/<agent_slug>/tuned/<pillar>/` (written by `reps-profile`).
They write findings to `results/<agent_slug>/findings/*.json`, so the report is identical either way.
Tuning never modifies the committed `reps/` baseline (Constitution v1.1.0, "Artifact Scopes").

## Outputs

Generated reports and findings live under a **gitignored, repo-root `results/`** tree — separate from
the `reps/` code — organized by agent (`agent_slug` = target name lowercased, spaces → `_`):

```
results/                       # gitignored (generated, per-engagement, may be sensitive)
└── the_parts_store/
    ├── report_2026-07-08_1423.html
    ├── the_parts_store-reps-analysis.md      # companion transcript analysis (feature 013)
    └── findings/
        ├── security_2026-07-08_1423.json
        ├── reasoning_2026-07-08_1423.json
        └── improvements_2026-07-08_1500.json  # transcript-derived improvements record
```

The report is regenerable any time by re-running the committed `reps/` artifacts.

**Suggested Agent Improvements (feature 013):** report section 07 gives the agent's developers
prioritized, root-cause fixes derived from reading the transcripts of the failing conversations —
with verbatim quotes, run IDs, discounted judging artifacts, and test-side coverage gaps kept
separate from real defects. It renders solely from the latest `improvements_<stamp>.json` in the
agent's findings dir, authored by the `reps-run` co-pilot's transcript-review step (schema
validated by `reps.report.improvements`). CLI/SDK runs don't author it —
the report then shows an explicit "no transcript review captured" note, and a stale banner appears
if new pillar runs land after the last review. Discounts never change recorded scores.

## Tune to your agent (recommended)

Agents differ. Two ways in, one pipeline out (feature 010):

```
reps-explore  →  DRAFT profile from 1–3 recorded discovery conversations (no Q&A)
reps-profile  →  applies the draft — or interviews you from scratch — and generates tuned rows
reps-run      →  executes the simulations
```

- **`reps-explore`** (fastest start): holds a short, benign discovery conversation with your
  registered agent (a simulation you can replay), infers domain/intents/tools/guardrails with
  per-fact provenance (observed/inferred/assumed), and writes a **draft** profile + exploration
  summary to `results/<agent_slug>/profile/` — so a banking agent is never tuned as a hotel
  assistant. It writes the draft only; it generates no rows and runs no pillar.
- **`reps-profile`**: interviews you about your agent (or, given a draft, auto-accepts the
  explored facts and asks only for what's missing), writes the secret-free profile
  (`results/<agent_slug>/profile/agent-profile.yaml`, `status: applied`), and generates tuned
  Reasoning/Execution scenarios and the Security authority judgment. Re-invoke any time to add an
  intent/tool/guardrail and grow the suite.
- **Draft gate**: while the profile is still `status: draft`, `reps-run` warns and offers a
  baseline (untuned) run or stopping to apply first — it never auto-applies
  (`run_suite.py --on-draft {ask|baseline|stop}`; profiles without a `status` field count as
  applied).
- Without any profile: Performance and the Security adversarial techniques still run; Reasoning
  and Execution run their generic starters and the report marks those pillars **untuned**.

## Artifact reuse & supersession (feature 003)

Runs bias toward **reusing** building blocks already on the platform instead of re-uploading
duplicates every run — the Okareo platform is the record of what exists; the committed `reps/` files
stay the source of truth. A block is re-uploaded only when it is **new** or **superseded** (its
committed content changed):

- **Standard, agent-agnostic blocks** carry a canonical name `<PillarLetter>-<bank>-<driver>` (e.g.
  `R-core-confused-caller` — the pillar word is never repeated) and are reused by name; a content
  change is detected by an `fp:<hash>` tag and auto-publishes a new version.
- **Tuned blocks** (after `reps-profile`) are scoped to the agent: scenarios/checks get a `-tuned`
  name plus tags `tuned, agent:<slug>, ver:<N>, fp:<hash>`; **drivers use a `-tuned-<agent>` name
  only** (Okareo drivers accept no tags — the standard driver is usually sufficient anyway).
- **Fail toward upload**: if an existing block can't be confirmed (drift, deletion), it is re-uploaded
  and surfaced as a coverage risk — a run never executes against stale/missing material.

The decision logic is the keyless pure package `reps/reuse/` (`fingerprint` · `naming` · `decision`),
shared by the MCP path (full reuse) and the SDK runner (drivers/checks reuse; scenarios run in a
documented degraded mode — the SDK cannot list/tag scenarios — so they fall toward upload). Each run
reports a per-block **reused vs uploaded** disposition, also shown in the report.

## The four pillars

| Pillar | Question | Mode | Tuning |
|--------|----------|------|--------|
| **Security** (Critical) | Stays within authority under pressure? | adversarial multi-turn | generic attacks + profile authority limits |
| **Reasoning** (High) | Reasons correctly about the task? | multi-turn | profile-bound (intents) |
| **Execution** (High) | Carries out its function correctly? | multi-turn + trace | profile-bound (tools) |
| **Performance** (Medium) | Reliable under realistic conditions? | repeat / long-session | generic (latency budget) |

## Layout

```
config.env.example      # repo root → copy to .env
reps/
├── target.json.voice-example  target.json.example
├── common.py           run_suite.py
├── targets/            # modality-agnostic target abstraction (voice adapter + text stub)
├── R-reasoning/ E-execution/ P-performance/ S-security/   # scenarios/ checks/ drivers/ templates/ eval_config.json
├── explore/            # exploration baseline (reps-explore, feature 010) — a setup aid, NOT a pillar: never in eval configs or coverage
├── profile/            # agent-profile.example.yaml (real profiles live in results/<agent_slug>/profile/)
├── shared/             # reusable drivers/checks across pillars
└── report/             # gen_reps_report.py, capture.py, scoring.py (outputs go to repo-root results/, gitignored)
```

## Conventions

- **Scenarios (row banks)** — `.jsonl` + `<stem>_meta.md`. A pillar's judge-graded probes are
  consolidated into a **standardized row bank**. One bank runs as one simulation (split by
  `driver` when a bank feeds more than one voice). Schema + validation live in `reps/rows.py`.

  **Since 0.7.0 a row is AUTHORED as structure and RENDERED for the platform** (feature 022). The
  authored shape is `sub_capability`, `persona`, an ordered `required_moves` list, an `approach`,
  and a `result` **object** carrying `must` and/or `must_not`; `reps.rows.render_row` materializes
  `input.guidance` and the `result` string that the driver and the judge actually read. The split is
  forced, not stylistic: every driver addresses `{scenario_input.guidance}` and stringifies whatever
  it finds, a check prompt **cannot** address a sub-field (the platform's placeholder set is closed
  and an unknown placeholder is rejected on save), and feature 009 forbids outcome text inside
  `input`. The render is byte-deterministic because `reps.reuse.fingerprint` hashes it.

  Three row rules carry measured weight. **At least one clause, at most one of each** — which clause
  a probe needs is a property of the probe, and most baseline rows are positive-only while several
  Security probes are pure prohibitions. **No AND-ing**: multiple conditions in one criterion caused
  about half the first field evaluation's wrong verdicts, because a slip against any one of them
  failed the whole probe. **No vague verb in a MUST** — a MUST reading "help with nine tickets" was
  read by a judge as "complete the purchase".

  The pre-0.7.0 free-text shape is a **hard validation error**, not a migration: a tuned overlay in
  the old shape is regenerated by re-running `reps-profile`, never hand-edited. The committed
  baseline is already current.
- **Drivers (voice personas)** — `.md` with `## Persona Prompt Template`, **one per distinct
  voice/manner of speech**, a condition-free shell that renders only `{scenario_input.persona}`
  and `{scenario_input.guidance}`. All probe-specific behavior lives in rows, none in driver prose.
  R uses 2 (confused / assertive), E and P use 1 each.
  Under the prompt heading a driver authors exactly the platform's four canonical sections —
  `## Persona`, `## Scenario Details` (the two tokens, immediately before objectives),
  `## Objectives`, `## Soft Tactics` — and **never** hand-writes conversation-rule sections:
  the MCP appends the platform's canonical `Hard Rules` / `Turn-End Checklist` /
  `Conversation Behavior` blocks on every save, replacing any authored variant. Those blocks are
  captured verbatim in `reps/shared/driver-canonical-blocks.md` (platform-owned, do not edit) and
  appended by the SDK path in `run_suite.py` so both run paths store the same effective prompt.
  Enforced by `tests/test_driver_conformance.py`, which is the executable statement of the format.
- **Checks** — one per-pillar **rubric judge** (`<pillar>-expectation-met`) grades a conversation
  against the row's `result` (pass criterion); deterministic/metric checks (`.py`:
  latency, error-rate, tool-arg-schema) stay separate (Constitution V). Judge templates carry
  `<<MARKER>>` substitution points filled per agent from the profile, each with a generic default so
  an untuned baseline still reads as a coherent prompt. Markers use angle brackets because `{NAME}`
  would be rejected on save and `[[…]]` / `((…))` are the platform's own delimiters.
  Every judge's reply **begins with the verdict digit** — a reply that does not is invalid.
- **Tuning** — add or edit a probe by editing rows in the bank file only (`reps-profile`);
  drivers and checks are agent-agnostic.
- Metadata schema: every artifact carries the front-matter keys listed above; `reps/common.py`
  reads them and `tests/test_metadata.py` enforces them.
- **Security** uses the same consolidated structure: 4 voice-grouped attack banks
  (confident-authority, calm-covert, frustrated-goal, agitated-rogue), 4 adversarial voice
  drivers, and one `security-boundary-held` rubric. Every row carries its OWASP Agentic-Security
  category (`security_category`) so findings still map to the compliance-owasp project.

## Modality

v0 is **voice-first** with text-ready seams: the target abstraction, a `modality` tag on every
artifact, and `--modality` in the runner mean a text workbench is an additive drop-in (a text
adapter + text probes) — no restructuring.

## Platform behaviors this workbench works around

Every item below was **verified against the platform**; four claims in the source documents behind
0.7.0 did not hold and are excluded. Where something is relied upon but unverified, it says so.

| Behavior | What the library does about it |
|---|---|
| A check with no result for a conversation **omits its key** | `reps.report.capture.read_check_verdict` raises rather than returning a falsy value. A plain lookup returns `None`, which is indistinguishable from a failure — observed on 4 of 85 rows in one run. |
| Stored rationales retain raw score/explanation **delimiter residue** | Stripped before any of it reaches a stakeholder as evidence (152 of 850 real results carried it). |
| Nested row structure can be **silently double-encoded** | Rows are read back after registration and verified to be objects, not strings holding encoded text. Nothing errors when this happens; the judge simply reads a quoted dict as its criterion. |
| Each data point is **self-identifying** | Verdicts join on data-point identity, never on position or rationale text, and the join stays correct when a row repeats. |
| The judge **varies between scoring passes** | Calibration reports agreement as a range over at least two passes and refuses a single one. Grounding figures carry their basis, which may be a hand count. |
| Deleting a scenario **deletes its runs** | Stated together with the fact that calibration needs the run to exist, because either alone sounds survivable. A new name is preferred over a replacement. |
| Versioning is constrained to the row-list form | A large bank is better re-registered under a new name. |
| Drivers and targets are **wholly replaced** on re-registration | Read before re-registering, or a field the overlay does not supply is silently cleared. Checks version safely. |
| Checks and drivers are **organization-wide**; scenarios are not | Per-agent checks and drivers are namespaced with the agent slug so one overlay cannot overwrite another's. |
| Target names may carry **trailing whitespace** | Copied from the platform listing rather than retyped. |
| A **re-score** renames and re-values the per-turn latency metric | Run-level latency is taken from the **original** run only. Reading it off a re-score silently drops the per-turn figure. |
| A re-scored run may carry the **same name** as its original | Resolved by newest-matching-name, against a name the library controls. |
| A derived run **does** inherit its turn limit, checks and stop check | Read the run's own inheritance record rather than assuming either way; it is self-describing and cannot go stale. |
| Oversized responses | Handled by **requesting less** — paging, or a lower detail level. No byte threshold is encoded, and no spilled-response path is depended on: the spill is a property of the operator's surface, not of the platform. |
| The check-prompt placeholder set is **closed** | An unrecognized placeholder is rejected when the check is saved, which is why substitution markers use angle brackets and why a check cannot address a row sub-field. |

**Stated as unverified** where relied upon: whether a re-score returns its new run's identifier, and
the precise semantics of a same-name scenario save. Neither blocks the work, because the safe path
is identical under either answer — and the safe path for a same-name save is never to rely on it to
update rows.

**No per-check judge model exists.** There is no parameter and no stored field, confirmed from both
directions, so judge strength comes from prompt construction and from splitting a judgment into
narrow single-concern checks — never from selecting a stronger model.

## Notes

- Live simulations run on Okareo (cost credits, need a real target); unit tests (`pytest`) are
  CI-safe and require neither.
- **A green test suite proves nothing about verdict quality.** Every figure that matters — the
  wrong-verdict rate, the share of meaningless passes, whether a probe was exercised at all — is
  established by comparing verdicts to a hand reading of live transcripts. The pilot stage of
  `reps-run` is what does that, and no offline test substitutes for it.
- The Security pillar reuses six OWASP agentic (ASI) paths — see `reps/S-security/README.md`.

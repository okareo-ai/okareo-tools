---
name: reps-explore
description: Rapidly explore a registered target agent to learn what it is for, and write a DRAFT agent profile for REPS tuning. Holds 1 (max 3) benign, recorded discovery conversation via an Okareo simulation (predefined exploration driver + scenario, created on the platform if needed), infers domain/persona/intents/tools/guardrails with per-fact provenance (observed/inferred/assumed), and writes the draft profile + a reviewable exploration summary into the agent's gitignored profile folder under results/. Writes the draft ONLY — run reps-profile to apply it (generates tuned rows) and reps-run to execute. Use when onboarding an unknown agent, before any profiling Q&A.
---

> **Canonical source**: this skill is developed in the private [`okareo-tools-dev`](https://github.com/okareo-ai/okareo-tools-dev) repository and published here by its publish pipeline. To propose a change, open an issue on okareo-tools — direct edits to this copy will be flagged as drift and blocked at the next publish.

# REPS Explore Skill

Learn what an agent is *for* — fast, shallow, and reviewable — so REPS tuning never tests a
banking agent as a hotel assistant. One benign discovery conversation (a recorded simulation an
onboarding user can replay) is usually enough to draft the profile; reasonable judgment fills the
gaps, and every fact is labeled with where it came from.

**Your job ends at the draft.** The pipeline is:

```
reps-explore  →  draft profile (status: draft) + exploration summary   ← THIS SKILL
reps-profile  →  applies the draft (auto-accepts facts, asks only for missing fields,
                 generates tuned rows, status → applied)
reps-run      →  executes the simulations (warns + offers baseline-or-stop on a draft)
```

Never generate tuned rows, never run a REPS pillar, never modify the committed `reps/` tree.
After any exploration, `git status --porcelain reps/` MUST print nothing (when a local tree
exists).

**Run where you are invoked.** Everything you write — the draft profile and the exploration
summary — lands under `results/<agent_slug>/` in the CURRENT project root (the directory the
session was invoked in). A REPS workbench that is merely *visible* elsewhere on disk (another
checkout, an additional working directory) is NOT this run's home: never anchor paths there,
never import its `reps` helpers, and never read or write its `results/` tree. **Local-helper
mode applies only when the current project root itself contains the `reps/` tree**; otherwise
run standalone with the rules inlined below. Standalone operation covers THIS skill's draft
outputs only (the draft profile and exploration summary — prose artifacts with no generator);
standalone mode never extends to reps-run's deliverables: its findings/improvements records or
the report are always produced by reps-run's canonical tooling, per that skill's own hard
invariant. If a prior draft for this agent exists only in an
external workbench, say where it is and continue fresh in the current project.

**Keyless.** Drive Okareo through the MCP tools (its own auth) — no local `OKAREO_API_KEY`.

## Inputs

- **target** — name (or id) of an agent already registered in Okareo. Fallback `$REPS_TARGET`;
  if neither, ask the operator. This is the only required input — no interview questions.

## Step 1 — Resolve the target and check for an existing profile

1. Confirm the target exists: `list_targets` / `get_target`. Compute the agent slug — local mode
   (a `reps/` tree in the current project root):
   `python -c "from reps.slug import agent_slug; print(agent_slug('<target>'))"`; standalone:
   lowercase the target name, spaces → `_`, and collapse every other run of non-`[a-z0-9_]`
   characters into a single `_` (e.g. "The Parts Store" → "the_parts_store" — the same rule the
   other reps skills use, so the overlay folder never forks).
2. Check for an existing profile at `results/<slug>/profile/agent-profile.yaml` in the current
   project root (in local mode `reps.paths.agent_profile_path` resolves the same location;
   standalone, create the directory on write if it does not exist). Never resolve this path
   against any other repo.
3. **If a profile already exists, NEVER silently overwrite it** (FR-012). Report its **status**,
   **version**, and **updated_at**, then ask the operator to choose:
   - **refresh** *(offered only when status is `draft`)* — re-explore and overwrite the draft.
   - **merge** — explore, but explored facts fill **only fields the existing profile lacks**;
     every existing value wins, and `provenance: operator` facts are untouchable (they are human
     truth — never overwrite the value or downgrade the label).
   - **keep** — stop; leave everything untouched.
   An **applied** profile is never offered "refresh" — merge or keep only.

## Step 2 — Resolve the discovery modality

No profile modality exists yet (first run), so derive from the target type. In local mode the
helper below applies the rule; standalone, apply it directly from `get_target`'s type:

```bash
python -c "from reps.trace import resolve_run_modality; \
print(resolve_run_modality(override=None, profile_modality=None, target_type='<target.type>'))"
```

Voice target → `voice`; `custom_endpoint` → `text`. Surface any warning; the conversation is held
in the target's own modality. What you resolve here is written into the draft as `modality:` with
provenance `observed`.

## Step 3 — Publish-or-reuse the exploration blocks

The committed baseline files are the source of truth (Constitution VII, read-only):

- driver `references/curious-onboarder.md` → platform name **`explore-curious-onboarder`**
- scenario `references/discovery.jsonl` → **one single-row platform scenario per
  angle** (a simulation runs every row of its scenario, so the angles must be separate blocks to
  keep one conversation per run): row 1 → **`explore-discovery-direct`**, row 2 →
  **`explore-discovery-task-first`**, row 3 → **`explore-discovery-limits-first`**; tags
  `reps, explore, standard, fp:<hash>` (fingerprint of that one row)

Bias to reuse (feature 003): fingerprint the committed file (local mode: helper
`reps.reuse.fingerprint`; standalone, a SHA-256 of the file's bytes), discover
by name (`list_drivers`+`get_driver` persona-hash; `list_scenarios` reading `fp:` tags), and
**reuse on a confirmed match; upload only when new or superseded** (`create_or_update_driver` —
pass voice fields for a voice run; `save_scenario` / `create_scenario_version`). Re-running
exploration must never create duplicates.

## Step 4 — Run the discovery conversation

One simulation, starting with the direct angle. Conversation mechanics follow the Step 2
modality (FR-019):

```
# voice target — the callee answers and greets first, budget for a full phone conversation:
run_simulation(target=<name>, driver=explore-curious-onboarder,
               scenario=explore-discovery-direct, checks=[task_completed],
               max_turns=20, first_turn=target, repeats=1)

# text target — the persona opens, shorter default:
run_simulation(target=<name>, driver=explore-curious-onboarder,
               scenario=explore-discovery-direct, checks=[task_completed],
               max_turns=8, first_turn=driver, repeats=1)
```

Voice gets a 15–20-turn budget (ceiling 20) because greetings, recorded-call disclosures, and
slow lookups eat turns — a natural close may still end the conversation earlier. The transcript
of a voice run opens with the target's own greeting; the driver responds to it.

The platform **requires at least one check** on a simulation (verified live: a check-free run
fails with a test-run error), so attach the lightweight built-in **task_completed** check and
**ignore its score** — nothing here is judged; the transcript is the product. Collect the
test-run id, then
`get_test_run_results` and `get_conversation_transcript` for the full conversation.

Then apply the **sufficiency test** and, only if it fails, run a bounded follow-up
(see "Bounded follow-up conversations" below — max 3 conversations total).

## Step 5 — Draft the profile from the transcript(s)

Derive each field from what the agent said or did. Shape it exactly like
`references/agent-profile.example.yaml` (feature-010 blocks included):

| Field | How to fill it |
|---|---|
| `domain` | The job-to-be-done the agent stated or demonstrated |
| `persona` | The role/voice it presented |
| `modality` | From Step 2 |
| **intents_supported** | Requests it said it handles or offered examples of |
| **intents_refused** | Requests it declined or said were out of scope |
| `tools` | Actions/lookups it claimed or visibly performed (name; args/authority only if stated) |
| `guardrails` | Prohibitions/verification rules it revealed |

**Provenance labels — every populated field gets one** (contract INV-D4):

- `observed` — stated or demonstrated in a transcript. Quoteable.
- `inferred` — your reasonable judgment from transcript evidence (e.g. the agent greeted as
  "Acme order support" ⇒ inferring commerce-adjacent intents it didn't list).
- `assumed` — gap-filling default with no direct evidence. Use sparingly; always flagged.

**Never fabricate** (INV-D6): fields exploration cannot know — **latency_budget**, `voice`,
**known_incidents**, **verbalization_values**, `reliability` — are **omitted entirely**, which is what
makes `reps-profile` interview for them on apply. `verification` and **ground_truth** are usually
unobservable too, but an agent sometimes states them outright (e.g. "I'd need your full name and
account reference before a lookup", or its own service list) — include such blocks ONLY when
directly stated, labeled `observed`, and still confirm them on apply. If the
agent's replies suggest two plausible domains, record the more specific one actually evidenced,
label it `inferred`, and note the ambiguity for the summary.

Add the audit block (INV-D7) with the **real** run ids:

```yaml
status: draft
exploration:
  explored_at: "<UTC ISO now>"
  conversations:
    - {test_run_id: "<id>", transcript: "<link-or-id>"}
  conversation_count: <n>            # 1..3
  confidence: high | medium | low    # low is REQUIRED when domain is not observed
```

## Step 6 — Sweep, validate, and write atomically

Assemble the profile **and** the exploration summary (see below) in the session scratchpad first.
Then:

1. **Secret/PII sweep** (FR-015): scan both documents for key-like strings, bearer tokens,
   card/SSN shapes, emails/phone numbers of real people, or verbatim sensitive disclosures the
   agent made. Replace each with `[REDACTED — <kind> observed in conversation]` and note the
   occurrence in the summary (it is likely Security-relevant signal for a later run) — never the
   content.
2. **Validate**: YAML parses; `status: draft` present; every populated field has a `provenance`
   entry; `exploration.conversations` carries every real test-run id; nothing fabricated.
3. **Write once, together** (INV-D9): only now write
   `results/<agent_slug>/profile/agent-profile.yaml` and
   `results/<agent_slug>/profile/exploration-summary.md`. **Any earlier failure — target
   unreachable, simulation error, empty transcript — means you write NOTHING** (FR-016): report
   the failure plainly and leave any pre-existing overlay untouched.
4. In local mode, prove the baseline is clean and show the operator:
   `git status --porcelain reps/` → no output. (Standalone: no local `reps/` tree — nothing to
   check.)

## Step 7 — Report back

Tell the operator, in this order: what the agent turned out to be (one sentence); the profile and
summary paths; confidence + anything assumed; the transcript id(s) for review; and the required
next steps — **`reps-profile` to apply the draft** (it auto-accepts these facts, asks only for
what's missing — e.g. latency budget — and generates the tuned rows), **then `reps-run`** to
execute. Until applied, `reps-run` will warn and offer only a baseline (untuned) run.

## Bounded follow-up conversations (only when needed)

**Sufficiency test** — after each conversation ask: can `domain`, `persona`, and at least one
**intents_supported** entry each be labeled **observed** from transcript evidence?

- **Yes** → stop conversing; draft the profile.
- **No** → run ONE more simulation using a **different angle's scenario** (the bank ships three:
  `explore-discovery-direct`, `explore-discovery-task-first`, `explore-discovery-limits-first` —
  pick one not yet used; publish it from the committed bank row if it isn't on the platform yet),
  with the same modality-matched parameters as Step 4 (voice: `first_turn=target`,
  `max_turns=20`; text: `first_turn=driver`, `max_turns=8`).
  Record its test-run id in `exploration.conversations` too.
- **Hard cap: 3 conversations total** (FR-004), even if still insufficient. At the cap, fill the
  remaining gaps with domain-consistent defaults labeled `assumed` (FR-008), set
  `confidence: low` whenever `domain` itself is not observed, and make the summary say plainly
  that confidence is low and recommend `reps-profile` for a human-supplied profile.

An agent that politely refuses to describe itself is **not an error** — it produces a
low-confidence draft, honestly labeled. A simulation that *fails* (no transcript) is an error →
Step 6 rule: write nothing.

## The exploration summary (written with the profile)

`results/<agent_slug>/profile/exploration-summary.md` — for an onboarding reviewer with no
workbench knowledge. Plain language, secret-free, and it must match the profile exactly (same
facts, same labels — the summary renders the profile, it is never a second source of truth).
Six sections, in order:

1. **What this agent is** — one paragraph naming the domain and job-to-be-done.
2. **What we learned** — a table: field · value · provenance. Make the `assumed` rows visually
   distinct (bold the label, e.g. `**assumed**`) so a reviewer can spot them at a glance.
3. **What we don't know yet** — the omitted/unknown fields (latency budget, verification factors,
   …) and any ambiguity you noted (e.g. two plausible domains — which you chose and why).
4. **Confidence** — the `exploration.confidence` value with a one-sentence rationale; when `low`,
   say so plainly and recommend the `reps-profile` interview.
5. **Review the conversation** — transcript link/id for each conversation, inviting verification.
6. **Next steps** — exactly: run `reps-profile` to apply (and optionally correct/deepen) this
   draft — that is where tuned scenario rows are generated; then `reps-run` to execute. Until
   applied, `reps-run` warns and offers a baseline (untuned) run only.

Redactions appear as `[REDACTED — <kind> observed in conversation]`. Never overstate: unknowns
and low confidence are stated, never padded over.

## Notes

- **Benign by contract** (INV-E3): the discovery persona never argues, tricks, pressures, or
  probes policy. If the target declines something, that is *data* (an **intents_refused** /
  `guardrails` observation), not an obstacle to push on.
- **Committed baseline is read-only**: never edit `reps/explore/…` (or anything under `reps/`)
  during exploration. To improve the discovery guidance itself, that is a baseline change — a
  committed edit outside any exploration run.
- **Per-agent isolation**: everything you write lands under `results/<agent_slug>/`; one agent's
  exploration never touches another's overlay.
- **Re-exploration**: re-invoking on the same agent goes through Step 1's existing-profile menu —
  refresh (draft only), merge, or keep. `operator` facts always survive.

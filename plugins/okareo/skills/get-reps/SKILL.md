---
name: get-reps
description: >-
  Get a local copy of the REPS agent-evaluation workbench (the reps/ baseline) into the current
  repo, or refresh an existing one. Use for "get the reps baseline", "download the workbench",
  "install reps locally", "set up the reps workbench", "refresh my reps tree". One bulk download,
  never per-file. Optional — the reps skills run without it.
argument-hint: "[status|install|update]"
---

# get-reps

Materialize the REPS workbench baseline (`reps/`) into the operator's own repo, or bring an existing
copy up to the latest release.

The reps skills read the baseline through the Okareo MCP (`get_reps_baseline`, always latest) by
default — this skill is the **opt-in local mode**: a working copy for operators who want to iterate
on the material, work offline, avoid per-run MCP reads, or pin a version. When a local `reps/`
exists, the skills prefer it.

## What this does

- **No argument** — detect and act: if `reps/` is absent, offer to install; if present, report
  installed vs latest version and offer to update when behind.
- **`status`** — report only: installed version (`reps/.workbench-version`), latest release tag, and
  whether the local baseline has uncommitted modifications. Writes nothing.
- **`install`** — vendor the latest release's `reps/` tree into the repo root.
- **`update`** — refresh an existing `reps/` to the latest release (guardrails below).

## Acquisition is one bulk download

The whole tree arrives in a **single bulk retrieval** — one release archive, ~91 files. Fetch the
baseline as a unit, **never file-by-file**: pulling it through per-file MCP reads to build a local
copy is prohibited. It is roughly 91 round trips for material the archive delivers in one, and it is
slow enough that operators abandon it mid-way.

The `get_reps_baseline` MCP tool remains the right way to *read* baseline artifacts during a run.
It is the wrong way to *materialize* a local tree.

## Pre-flight — check the two preconditions

Determine both by **observed behavior, never the surface** you think you are running on. Surface
identity is not a reliable signal; what matters is what the environment actually does.

1. **A writable working directory** — attempt the write. If it fails, stop and say so.
2. **Persistence** — `git rev-parse --is-inside-work-tree`. Inside a work tree ⇒ the copy persists;
   proceed silently.
3. **Bulk retrieval** — determined by the fetch's own exit status. No separate pre-flight probe: one
   network operation, and the failure reported is the real one.

**If the working directory cannot be confirmed to persist** — outside a git work tree, or
undeterminable — **warn and proceed**. Tell the operator the copy **will not survive the session**,
and that any agent-specific tuning stored alongside it under `results/` is lost with it. Then carry
on. Never refuse on this basis alone, and never install silently as though the copy were durable: a
false assurance of durability is the costlier error. Undeterminable is treated as non-persistent.

**If a precondition is genuinely unavailable**, stop and state plainly **which mechanism failed**,
what it means, and the alternative — the reps skills run with no local copy at all, reading the
baseline through `get_reps_baseline`. Never silently fall back to a per-file crawl.

## How

1. **Resolve the latest release tag** from
   `https://api.github.com/repos/okareo-ai/okareo-tools/releases/latest` (read `tag_name`). If the
   fetch fails — offline, rate-limited — say so plainly; never guess a version.
2. **Read the installed version** from `reps/.workbench-version`. If the file is absent, unreadable,
   or malformed, **report the version as unknown** rather than guessing — two runs against different
   baselines are not comparable, and a guessed version silently breaks that comparison.
3. **Install** (only when `reps/` is absent — if a `reps/` directory exists but is clearly not the
   workbench, STOP and ask the operator; **never overwrite**):
   ```bash
   tmp=$(mktemp -d) \
     && curl -fsSL https://github.com/okareo-ai/okareo-tools/archive/refs/tags/<TAG>.tar.gz \
        | tar -xz -C "$tmp" --strip-components=1 \
     && mv "$tmp/reps" ./reps && rm -rf "$tmp" \
     && echo "<TAG>" > reps/.workbench-version
   ```
   **Acquisition is all-or-nothing.** Extract to the temporary directory first and move into place
   only on complete success; remove the temporary directory on any failure. When this finishes,
   either **a complete workbench exists, or none does** — never a partial tree. A partial tree is
   indistinguishable from a complete one to every later session, and it silently changes which
   material an evaluation scores against.

   Then: ensure `results/` is in the repo's `.gitignore` (append if missing), and suggest committing
   `reps/` — it is the agent-agnostic baseline and belongs in the operator's history. Tuning never
   touches it (overlays live in the gitignored `results/`), so `git status --porcelain reps/` stays a
   valid cleanliness check.
4. **Update** (only when installed): first check the local baseline is clean —
   `git status --porcelain reps/` must print nothing. If it is dirty, STOP and show the modified
   files; **never discard** local edits by overwriting them. Baseline customization belongs in
   `results/<agent_slug>/tuned/` overlays anyway. When clean, re-run the install extraction with the
   newer tag — same all-or-nothing rule — and rewrite `reps/.workbench-version`.
5. **Route onward.** After install/update, point the operator at the skills that use the material:
   `reps-explore` (draft a profile from one discovery conversation), `reps-profile` (tune the suite
   to their agent), `reps-run` (run a pillar and produce the report).

## Notes

- Never `git clone` the okareo-tools repo into the operator's workspace: a nested repo confuses git
  and strands their artifacts in a foreign checkout.
- The reps skills do **not** require this. Without a local `reps/` they read the baseline via
  `get_reps_baseline` (latest release, zero setup). This skill is the explicit, operator-invoked
  path into local mode — setup, upgrades, and version checks.

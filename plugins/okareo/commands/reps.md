---
description: >-
  Set up or refresh a local copy of the REPS agent-evaluation workbench (the
  reps/ baseline) in the current repo so the reps skills can read, tune, and
  iterate on it locally — no git clone, no nested repo, no per-file MCP
  round-trips. With no argument, detects the current state and does the right
  thing; also supports explicit install / update / status.
argument-hint: "[status|install|update]"
---

# /okareo:reps

Materialize the REPS workbench baseline (`reps/`) into the operator's own repo, or bring an
existing copy up to the latest release. The reps skills read the baseline through the Okareo MCP
(`get_reps_baseline`, always latest) by default — this command is the **opt-in local mode**: a
working copy for operators who want to iterate on the material, work offline, avoid per-run MCP
reads, or (once supported) pin a version. When a local `reps/` exists, the skills prefer it.

## What this does

- **No argument** — detect and act: if `reps/` is absent, offer to install; if present, report
  installed vs latest version and offer to update when behind.
- **`status`** — report only: installed version (`reps/.workbench-version`), latest release tag,
  and whether the local baseline has uncommitted modifications.
- **`install`** — vendor the latest release's `reps/` tree into the repo root.
- **`update`** — refresh an existing `reps/` to the latest release (guardrails below).

## How

1. **Resolve the latest release tag** from
   `https://api.github.com/repos/okareo-ai/okareo-tools/releases/latest` (read `tag_name`).
   If the fetch fails — offline, rate-limited — say so plainly; never guess a version.
2. **Read the installed version** from `reps/.workbench-version` (absent file or absent `reps/`
   means not installed).
3. **Install** (only when `reps/` is absent — if a `reps/` directory exists but is clearly not
   the workbench, STOP and ask the operator; never overwrite):
   ```bash
   tmp=$(mktemp -d) \
     && curl -fsSL https://github.com/okareo-ai/okareo-tools/archive/refs/tags/<TAG>.tar.gz \
        | tar -xz -C "$tmp" --strip-components=1 \
     && mv "$tmp/reps" ./reps && rm -rf "$tmp" \
     && echo "<TAG>" > reps/.workbench-version
   ```
   Then: ensure `results/` is in the repo's `.gitignore` (append if missing), and suggest
   committing `reps/` — it is the agent-agnostic baseline and belongs in the operator's history.
   Tuning never touches it (overlays live in the gitignored `results/`), so
   `git status --porcelain reps/` stays a valid cleanliness check.
4. **Update** (only when installed): first check the local baseline is clean —
   `git status --porcelain reps/` must print nothing. If it is dirty, STOP and show the modified
   files: local edits to the baseline would be silently overwritten, and baseline customization
   belongs in `results/<agent_slug>/tuned/` overlays anyway. When clean, re-run the install
   extraction over `reps/` with the newer tag and rewrite `reps/.workbench-version`.
5. **Route onward.** After install/update, point the operator at the skills that use the
   material: `reps-explore` (draft a profile from one discovery conversation), `reps-profile`
   (tune the suite to their agent), `reps-run` (run a pillar and produce the report).

## Notes

- The bulk download always uses the release tarball — one fetch for the whole tree. Do not pull
  baseline files one-by-one through MCP tools for local materialization.
- Never `git clone` the okareo-tools repo into the operator's workspace: a nested repo confuses
  git and strands their artifacts in a foreign checkout.
- The reps skills do NOT require this: without a local `reps/` they read the baseline via the
  `get_reps_baseline` MCP tool (latest release, zero setup). This command is the explicit,
  operator-invoked path into local mode — setup, upgrades, and version checks.

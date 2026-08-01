---
name: update
description: >-
  Check whether a newer version of the Okareo plugin and skills is available and show exactly how to
  update, per surface — Claude Code, Claude Desktop, the Claude API, or claude.ai. Use for "update
  Okareo", "am I on the latest version", "how do I upgrade the plugin". None of the surfaces
  auto-upgrade by default.
argument-hint: ""
---

> **Canonical source**: this skill is developed in the private [`okareo-tools-dev`](https://github.com/okareo-ai/okareo-tools-dev) repository and published here by its publish pipeline. To propose a change, open an issue on okareo-tools — direct edits to this copy will be flagged as drift and blocked at the next publish.

# update

Check for a newer Okareo version and walk through updating to it.

## What this does

Compares the latest published Okareo plugin version against what is installed and gives the exact
steps to refresh. Plugin updates are pulled explicitly — no surface auto-upgrades on its own.

## How

1. **Find the latest published version.** Fetch the marketplace catalog from the source repo and
   read the plugin's version:
   `https://raw.githubusercontent.com/okareo-ai/okareo-tools/main/.claude-plugin/marketplace.json`
   (read `plugins[].version`). If the fetch fails — offline, repo private — say so plainly and
   continue with the manual steps below; do not guess a version.
2. **Note the installed version.** Claude cannot read the installed plugin version directly. Ask the
   user to open `/plugin` → **Installed** tab (Claude Code v2.1.144+ shows a **Last updated** date
   there), or just proceed if they only want the update steps.
3. **Show the update path for their surface.** Ask which surface if it is not obvious. State clearly
   that Claude cannot run the built-in `/plugin` commands for them — they paste these themselves.

## Update steps by surface

**Claude Code** (terminal):

```
/plugin marketplace update okareo-tools
/plugin install okareo@okareo-tools
```

There is no `/plugin update` command — the two lines above are the refresh. To stop doing this by
hand, mention the opt-in: turn on auto-update from the **Marketplaces** tab in `/plugin`, or set it
project-wide in `.claude/settings.json` with an `extraKnownMarketplaces` entry that sets `autoUpdate`
to true for `okareo-tools`.

**Claude Desktop**: the plugin installs and updates the same way as Claude Code — through `/plugin`
on the Code surface. Every Okareo capability ships as a skill, so all of them appear in the slash
menu once the plugin is installed. There is no separate per-skill installation step on Desktop.

**Claude API** (maintainers with this repo checked out):

```
./scripts/install.sh api
```

The Skills API versions each skill on upload; pin a version in production and use `latest` only in
development.

**claude.ai**: install the Okareo plugin if the surface supports it. Otherwise download the `.skill`
files from https://github.com/okareo-ai/okareo-tools/releases/latest, remove the previous versions
under **Settings → Capabilities → Skills**, and add the new ones. The Okareo MCP connector itself
does not need to be re-added.

## Report

State the latest version, whether an update appears to be available, and the one or two steps the
user should take. If already current, say so and stop — do not send them through a needless
reinstall.

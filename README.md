# okareo-tools

Official Okareo tooling for coding agents: the Okareo **MCP server** plus a set of **Agent Skills**
that teach an agent how to simulate, evaluate, and monitor LLM apps and agents with
[Okareo](https://okareo.com) — including the **REPS workbench**, a forkable harness that assesses an
agent across four pillars and produces an explainable report.

The MCP server gives the agent the *tools* (the callable actions against Okareo). The skills give it
the *method* — when to reach for those tools and how to run a real workflow with them. They are
designed to be installed together.

- Plugin & skill downloads: https://github.com/okareo-ai/okareo-tools/releases/latest
- Okareo docs: https://docs.okareo.com

## What's in the box

Fifteen skills, one MCP server, bundled as a single installable plugin.

### Skills

| Skill | What it does |
|---|---|
| `quickstart` | Onboard a new user; verify the connection; first run |
| `scenario-design` | Compose a synthetic test scenario set from scratch |
| `scenario-from-traces` | Turn production traces, logs, and incidents into a test set |
| `agent-simulation` | Stress-test a text agent with simulated multi-turn users |
| `voice-simulation` | Run simulated calls against a voice agent |
| `evaluation` | Score a model or prompt against a scenario set |
| `improve` | Iteratively improve an agent over N cycles; track the trend |
| `monitoring` | Monitor live text or voice traffic; catch regressions and drift |
| `reps-explore` | Hold one benign discovery conversation; draft an agent profile |
| `reps-profile` | Apply the profile; generate scenario rows tuned to your agent |
| `reps-run` | Execute a REPS pillar against a target and regenerate the report |
| `get-reps` | Install or refresh a local copy of the REPS baseline in your repo |
| `scenario` | Pick a scenario source and route to the right builder |
| `simulate` | Pick text vs voice and route to the right simulator |
| `update` | Check for a newer version and explain how to install it |

Every capability is a skill, invoked as `/okareo:<name>` — and available on **every** surface,
including Claude Desktop. (Through v0.6.5 some shipped as plugin *commands*, which Claude Desktop
does not surface; they were converted in v0.6.6.)

`quickstart` is the on-ramp. The rest compose into a lifecycle: build a scenario set
(`scenario-design` or `scenario-from-traces`), exercise an agent before release
(`agent-simulation`, `voice-simulation`), score it (`evaluation`), iteratively improve it until it
meets the bar (`improve`), and watch it in production (`monitoring`) — where any
failure flows back into a scenario set that is re-run on every change. More skills and commands are
planned — see [ROADMAP.md](ROADMAP.md).

## The REPS agent-evaluation workbench

REPS assesses an agent across four pillars and produces an assessment report that states plainly
what is working and what is not, with transcript evidence behind every finding.

| Pillar | What it probes |
|---|---|
| **R**easoning | Ambiguity handling, intent switching, constraint retention, contradiction detection |
| **E**xecution | Tool selection and arguments, compound requests, error recovery, hallucinated completions |
| **P**erformance | Turn latency, output consistency, late-turn degradation, barge-in and resume |
| **S**ecurity | OWASP Agentic-Security probes — goal hijack, tool misuse, privilege abuse, verification gates |

### Quick start

REPS runs from **your own repo**, not from a clone of this one. Register a target in Okareo, install
the plugin, then run `/okareo:get-reps` from your agent's workspace — it vendors the `reps/` baseline
into your repo (no clone, no nested git; commit it as your baseline). Then:

1. `reps-explore` — one benign discovery conversation; drafts an agent profile
2. `reps-profile` — applies the profile and generates rows tuned to your agent (optional)
3. `reps-run` — executes a pillar and regenerates the report

`reps-run` is the zero-setup entry point: pass a target name and a pillar letter (`R`/`E`/`P`/`S`)
and it produces a complete baseline report with no profiling Q&A.

Baseline artifacts live under `reps/<pillar>/` and are agent-agnostic — read-only to tuning flows.
Per-agent tuned overlays, findings, and reports land in the gitignored `results/<agent_slug>/`,
resolved overlay-first so your tuning never modifies the baseline.

See [`reps/README.md`](reps/README.md) for the artifact model.

## Installing

Skills do not sync between surfaces, so each has its own install path.

A `.skill` file is the portable, installable unit of an Agent Skill — a zip archive whose root
contains a single skill folder with `SKILL.md` inside it. One per skill is attached to every
[GitHub Release](https://github.com/okareo-ai/okareo-tools/releases/latest), and the same file
installs on all three Claude surfaces. `scripts/install.sh` automates the scriptable ones.

### Claude Code (recommended)

The plugin bundles the MCP server and all fifteen skills as one unit:

```
/plugin marketplace add okareo-ai/okareo-tools
/plugin install okareo@okareo-tools
```

The plugin connects to the hosted Okareo MCP server (`https://tools.okareo.com/mcp`). The first
Okareo tool call opens a browser for a one-time sign-in — no API key needs to be set. See
[Updating](#updating) to pull a newer version later.

**Approve the Okareo tools once.** The skills call many MCP tools, so by default Claude Code prompts
for each one. Run `/permissions` and add an **Allow** rule for:

```
mcp__okareo__*
```

That one rule covers every current and future Okareo tool. To share it with a team, commit it to the
project instead of setting it per-developer:

```json
// .claude/settings.json
{ "permissions": { "allow": ["mcp__okareo__*"] } }
```

A plugin cannot grant this for you — Claude Code requires the user to allow an MCP server's tools.
Skills still confirm in-chat before steps that cost money or are hard to undo (placing a real test
call, deleting a resource), so a server-wide allow rule does not mean silent billed actions.

### Claude Desktop

Claude Desktop installs the plugin the same way, from its **Code** surface — the marketplace
commands above work unchanged. Every Okareo capability ships as a skill, so all fifteen appear in
the slash menu once the plugin is installed. There is no separate per-skill installation step.

### Cursor

Cursor consumes the **MCP server** natively. Add it to `.cursor/mcp.json` in your project (or
`~/.cursor/mcp.json` to enable it everywhere):

```json
{
  "mcpServers": {
    "okareo": {
      "url": "https://tools.okareo.com/mcp"
    }
  }
}
```

Reload Cursor, then confirm the server is connected and its tools are enabled under
**Cursor Settings → MCP**. The first tool call opens a browser for the same one-time sign-in.

> Cursor's MCP config schema has changed across versions (some accept an explicit
> `"type": "http"`). If the server does not appear, check
> [Cursor's MCP docs](https://docs.cursor.com/context/model-context-protocol) for the form your
> version expects.

**On the skills**: `.skill` packages are installers for the Claude surfaces, so there is no
equivalent one-click install in Cursor. The MCP tools work fully; to give Cursor the *method* as
well, copy the relevant `SKILL.md` bodies into your project as Cursor rules (`.cursor/rules/`) or
into `AGENTS.md`. Native skill support in Cursor is not something this plugin provides today.

### claude.ai

Install the Okareo plugin if the surface offers it — that is the shortest path and keeps
every skill in step. Otherwise, per-user through the web UI: download the `.skill` files from the
[latest GitHub Release](https://github.com/okareo-ai/okareo-tools/releases/latest), add them under
**Settings → Capabilities → Skills**, and add the Okareo MCP server under **Settings → Connectors**.

Manual per-skill installation is the fallback, not the norm. Where the plugin installs directly —
Claude Code and Claude Desktop — use it.

### Claude API

Each skill is uploaded to your workspace via the Skills API and is then available to all workspace
members:

```
./scripts/install.sh api          # uploads every dist/*.skill
```

Attach the skills to a request via the `container` parameter, and pass the Okareo MCP server as an
`mcp_servers` entry. API requests are headless, so authenticate with a `Bearer ${OKAREO_API_KEY}`
header rather than the interactive browser sign-in.

## Updating

None of the surfaces auto-upgrade by default. Run `/okareo:update` for the exact steps for yours.
(Cursor needs no update: it consumes the hosted MCP server, which is updated server-side. If you
copied skill bodies into `.cursor/rules/` or `AGENTS.md`, re-copy them to pick up changes.)

**Claude Code** — refresh the marketplace metadata, then reinstall:

```
/plugin marketplace update okareo-tools
/plugin install okareo@okareo-tools
```

There is no `/plugin update` command. To see what's installed, run `/plugin` and check the
**Installed** tab — entries on Claude Code v2.1.144+ show a **Last updated** date. To stop doing
this by hand, opt in to auto-update from the **Marketplaces** tab in `/plugin`, or set it for the
whole project in `.claude/settings.json`:

```json
{ "extraKnownMarketplaces": { "okareo-tools": { "autoUpdate": true } } }
```

**claude.ai** — download the new `.skill` files from the latest release, remove the previous
versions under **Settings → Capabilities → Skills**, and add the new ones. The Okareo MCP server
connector does not need to be re-added.

**Claude API** — re-run `./scripts/install.sh api` to upload a new version of every skill. The
Skills API versions each skill on upload, so pin a specific version in production and use `latest`
only in development.

## Repository structure

```
okareo-tools/
│
├── .claude-plugin/
│   └── marketplace.json              Claude Code marketplace catalog. Lists the
│                                     okareo plugin and where to find it.
│
├── plugins/
│   └── okareo/                       ONE installable plugin = MCP + skills + commands.
│       ├── .claude-plugin/
│       │   └── plugin.json           Plugin manifest. The release version lives here.
│       ├── .mcp.json                 Okareo MCP server config. Auto-loaded by
│       │                             Claude Code when the plugin installs.
│       ├── commands/                 Slash commands (/okareo:<name>).
│       └── skills/                   One folder per skill; each has a SKILL.md at
│           │                         its top level, plus optional references/.
│           ├── improve/
│           ├── agent-simulation/
│           ├── evaluation/
│           ├── monitoring/
│           ├── quickstart/
│           ├── reps-explore/
│           ├── reps-profile/
│           ├── reps-run/
│           ├── scenario-design/
│           ├── scenario-from-traces/
│           └── voice-simulation/
│
├── reps/                             The agent-agnostic REPS baseline. Vendored into
│   │                                 your repo by /okareo:get-reps — start at reps/README.md.
│   ├── R-reasoning/                  One folder per pillar: drivers, scenario rows,
│   ├── E-execution/                  checks, and templates.
│   ├── P-performance/
│   ├── S-security/
│   ├── explore/                      Discovery driver and scenario for reps-explore.
│   ├── profile/                      Profiling aids for reps-profile.
│   ├── report/                       Capture, scoring, report generation, brand assets.
│   ├── shared/                       Canonical driver blocks shared across pillars.
│   └── targets/                      Target configuration examples.
│
├── contracts/                        Public contracts (e.g. get_reps_baseline).
├── dist/                             Built .skill packages, one per skill.
├── docs/                             Supporting design notes.
├── scripts/
│   ├── build.sh                      Packages each skill into a .skill file.
│   ├── release.sh                    Builds, then publishes to all 3 surfaces.
│   ├── install.sh                    Consumer-side installer.
│   └── validate_skills.py            Checks every skill before packaging.
│
├── .github/workflows/release.yml     CI: validate + build + publish on a v* tag.
├── skill-template/                   Copy-to-author scaffold for a new skill.
├── skill-ids.json                    Claude API skill ids.
├── CONTRIBUTING.md                   How to propose a change.
├── ROADMAP.md                        Shipping and planned skills.
├── CLAUDE.md.snippet                 Drop-in dependency hint for consuming repos.
├── LICENSE
└── README.md
```

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the shape of a
skill and how to propose a change.

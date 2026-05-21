# okareo-tools

Official Okareo tooling for Claude: the Okareo **MCP server** plus a set of
**Agent Skills** that teach Claude how to simulate, evaluate, and monitor
LLM apps and agents with Okareo.

The MCP server gives Claude the *tools* (the callable actions against
Okareo). The skills give Claude the *method* — when to reach for those
tools and how to run a real workflow with them. They are designed to be
installed together.

- Distribution site: https://tools.okareo.com
- Repository: https://github.com/okareo-ai/okareo-tools

## What's in the box

Four skills, one MCP server, bundled as a single installable plugin:

| Skill                        | What it does                                            |
| ---------------------------- | ------------------------------------------------------- |
| `okareo-agent-simulation`    | Stress-test an agent with simulated multi-turn users    |
| `okareo-evaluation`          | Design, run, and analyze evaluations                    |
| `okareo-monitoring`          | Monitor live traffic; alert on regressions and drift    |
| `okareo-scenario-from-traces`| Turn production traces and issues into a test set       |

The skills compose into one lifecycle: **simulation** finds failures before
release, **monitoring** catches them in production, **scenario-from-traces**
converts either kind of failure into a durable test set, and **evaluation**
runs that set on every change.

## Repository structure

```
okareo-tools/
│
├── .claude-plugin/
│   └── marketplace.json              Claude Code marketplace catalog. Lists
│                                     the okareo plugin and where to find it.
│
├── plugins/
│   └── okareo/                       ONE installable plugin = MCP + skills.
│       ├── .claude-plugin/
│       │   └── plugin.json           Plugin manifest. The release version
│       │                             (semver) lives here.
│       ├── .mcp.json                 Okareo MCP server config. Auto-loaded
│       │                             by Claude Code when the plugin installs.
│       └── skills/                   One folder per skill. Each is a
│           │                         self-contained Agent Skill.
│           ├── okareo-agent-simulation/
│           │   ├── SKILL.md          Instructions + YAML frontmatter.
│           │   └── references/       Extra docs, loaded only when needed
│           │       └── persona-design.md
│           ├── okareo-evaluation/
│           │   ├── SKILL.md
│           │   └── references/checks.md
│           ├── okareo-monitoring/
│           │   ├── SKILL.md
│           │   └── references/alert-design.md
│           └── okareo-scenario-from-traces/
│               ├── SKILL.md
│               └── references/trace-mapping.md
│
├── scripts/
│   ├── build.sh                      Packages each skill into a .skill file.
│   ├── release.sh                    Builds, then publishes to all 3 surfaces.
│   └── install.sh                    Consumer-side installer.
│
├── .github/
│   └── workflows/
│       └── release.yml               CI: build + publish when a v* tag is pushed.
│
├── dist/                             Build output (.skill files). Gitignored.
├── skill-ids.json                    Claude API skill ids, managed by release.sh.
├── CLAUDE.md.snippet                 Drop-in dependency hint for consuming repos.
├── LICENSE
├── .gitignore
└── README.md
```

Two structural rules to keep in mind:

- **`plugin.json` and `marketplace.json` go inside `.claude-plugin/`.**
  Everything else in a plugin (`skills/`, `.mcp.json`) sits in the plugin
  root, not in `.claude-plugin/`.
- **One skill = one folder with a `SKILL.md` at its top level.** Adding a
  skill is just adding a folder under `plugins/okareo/skills/`; the build and
  release scripts pick it up automatically.

## What a `.skill` package is

A `.skill` file is the portable, installable unit of an Agent Skill — a zip
archive whose root contains a single skill folder with `SKILL.md` inside it.
`build.sh` produces one per skill in `dist/`. The same file installs on all
three Claude surfaces.

## Installing

Skills do not sync between Claude surfaces, so each surface has its own
install path. `scripts/install.sh` automates the scriptable ones.

### Claude Code (recommended)

The plugin bundles the MCP server and all four skills as one unit:

```
/plugin marketplace add okareo-ai/okareo-tools
/plugin install okareo@okareo
```

Set `OKAREO_API_KEY` in your environment before starting Claude Code.
Update later with `/plugin marketplace update okareo`.

### Claude API

Each skill is uploaded to your workspace via the Skills API and is then
available to all workspace members:

```
./scripts/install.sh api          # uploads every dist/*.skill
```

Attach the skills to a request via the `container` parameter, and pass the
Okareo MCP server as an `mcp_servers` entry — API skills run sandboxed with
no network access, so they orchestrate the MCP tools rather than calling
Okareo directly.

### claude.ai

Per-user, through the web UI: download the `.skill` files from
https://tools.okareo.com, then add them under Settings → Capabilities →
Skills, and add the Okareo MCP server under Settings → Connectors.

## Creating the GitHub repository

One-time setup, using the GitHub CLI (`gh`):

```bash
# from the okareo-tools/ directory
git init -b main
git add .
git commit -m "Initial Okareo tools package"

gh repo create okareo-ai/okareo-tools --public --source=. --push
```

Then add the API key the release workflow needs:

```bash
gh secret set ANTHROPIC_API_KEY        # paste the workspace API key
```

That secret is read by `.github/workflows/release.yml` to publish skills to
the Claude API. Nothing else needs configuring — pushing a `v*` tag triggers
a release.

## Releasing a new version

```bash
# 1. Bump the version in BOTH manifests (keep them in sync):
#      plugins/okareo/.claude-plugin/plugin.json   -> "version"
#      .claude-plugin/marketplace.json             -> plugins[].version
#
# 2. Build + publish to all three surfaces:
./scripts/release.sh
#
# 3. Commit the (possibly updated) skill-ids.json and push:
git add skill-ids.json && git commit -m "release: vX.Y.Z" || true
git push origin main --tags
```

Pushing the tag also triggers `release.yml`, which rebuilds the packages,
publishes them to the Claude API, and creates a GitHub Release with the
`.skill` files attached. `release.sh` and the CI workflow do the same job —
run the script locally for a hands-on release, or just push a tag.

## Versioning

- **Claude API** has native version management. Each skill upload creates a
  new version; pin a specific version in production and use `latest` only in
  development.
- **Claude Code** versions through git tags plus the `version` field in
  `plugin.json`. Plugin updates are pulled explicitly by users, not
  automatically.
- `skill-ids.json` maps each skill name to its Claude API skill id. The first
  release of a skill creates the skill and records its id here; later
  releases add versions to that id. Commit it whenever it changes.

## Before your first release: align the MCP tool names

Each `SKILL.md` references Okareo MCP tools by name (`okareo_run_evaluation`,
`okareo_run_simulation`, `okareo_create_monitor`, `okareo_query_datapoints`,
and so on). These are illustrative placeholders. Replace them with the real
tool names your MCP server exposes, and keep the tool table in each
`SKILL.md` in sync with `.mcp.json` — they are a contract between the skills
and the server.

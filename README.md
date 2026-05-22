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
| `okareo-voice-quickstart`    | Onboard a voice agent and run a first voice simulation  |
| `okareo-agent-simulation`    | Stress-test an agent with simulated multi-turn users    |
| `okareo-monitoring`          | Monitor live traffic; alert on regressions and drift    |
| `okareo-scenario-from-traces`| Turn production traces and issues into a test set       |

`okareo-voice-quickstart` is the on-ramp — it onboards a voice agent end to
end and runs a first simulation against it. The other three compose into a
lifecycle: **simulation** finds failures before release, **monitoring**
catches them in production, and **scenario-from-traces** converts either kind
of failure into a durable test set you can re-run on every change. More
skills are planned — see [ROADMAP.md](ROADMAP.md).

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
│           │   └── references/       Extra docs, loaded only when needed.
│           ├── okareo-monitoring/
│           ├── okareo-scenario-from-traces/
│           └── okareo-voice-quickstart/
│
├── skill-template/                   Copy-to-author scaffold for a new
│                                     skill. Lives outside skills/ so it is
│                                     never packaged.
│
├── scripts/
│   ├── build.sh                      Packages each skill into a .skill file.
│   ├── release.sh                    Builds, then publishes to all 3 surfaces.
│   ├── install.sh                    Consumer-side installer.
│   └── validate_skills.py            Checks every skill before packaging.
│
├── .github/
│   └── workflows/
│       └── release.yml               CI: validate + build + publish on a v* tag.
│
├── dist/                             Build output (.skill files). Gitignored.
├── skill-ids.json                    Claude API skill ids, managed by release.sh.
├── CONTRIBUTING.md                   How to author a skill.
├── ROADMAP.md                        Shipping and planned skills.
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

The plugin connects to the hosted Okareo MCP server
(`https://tools.okareo.com/mcp`). The first Okareo tool call opens a browser
for a one-time sign-in — no API key needs to be set. Update later with
`/plugin marketplace update okareo`.

### Claude API

Each skill is uploaded to your workspace via the Skills API and is then
available to all workspace members:

```
./scripts/install.sh api          # uploads every dist/*.skill
```

Attach the skills to a request via the `container` parameter, and pass the
Okareo MCP server as an `mcp_servers` entry. API requests are headless, so
authenticate the MCP server with a `Bearer ${OKAREO_API_KEY}` header rather
than the interactive browser sign-in.

### claude.ai

Per-user, through the web UI: download the `.skill` files from
https://tools.okareo.com, then add them under Settings → Capabilities →
Skills, and add the Okareo MCP server under Settings → Connectors.

## Developing skills

To add or change a skill, see [CONTRIBUTING.md](CONTRIBUTING.md). In short:

```bash
cp -r skill-template plugins/okareo/skills/<skill-name>   # scaffold
# ...edit SKILL.md...
python3 scripts/validate_skills.py                        # check the contract
./scripts/build.sh                                        # package to dist/
```

`validate_skills.py` enforces the **tool-name contract**: every MCP tool a
skill references must be a real Okareo MCP tool (the canonical list is
`KNOWN_TOOLS` in that script). `build.sh` and CI run the validator first and
refuse to package a skill that fails it.

## Creating the GitHub repository

One-time setup, using the GitHub CLI (`gh`):

```bash
# from the okareo-tools/ directory (already a git repo on branch main)
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

Pushing the tag also triggers `release.yml`, which validates and rebuilds
the packages, publishes them to the Claude API, and creates a GitHub Release
with the `.skill` files attached. `release.sh` and the CI workflow do the
same job — run the script locally for a hands-on release, or just push a tag.

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

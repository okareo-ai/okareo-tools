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

Seven skills and four slash commands, one MCP server, bundled as a single
installable plugin:

| Skill                  | What it does                                             |
| ---------------------- | -------------------------------------------------------- |
| `quickstart`           | Onboard a new user; verify the connection; first run     |
| `scenario-design`      | Compose a synthetic test scenario set from scratch        |
| `scenario-from-traces` | Turn production traces and issues into a test set         |
| `agent-simulation`     | Stress-test a text agent with simulated multi-turn users  |
| `voice-simulation`     | Run simulated calls against a voice agent                 |
| `evaluation`           | Score a model or prompt against a scenario set            |
| `monitoring`           | Monitor live text or voice traffic; catch drift           |

The commands — `/okareo:quickstart`, `/okareo:scenario`, `/okareo:simulate`,
`/okareo:monitor` — are thin entry points that frame a task and route to the
skill that does the work.

`quickstart` is the on-ramp. The rest compose into a lifecycle: build a
scenario set (`scenario-design` or `scenario-from-traces`), exercise an agent
before release (`agent-simulation`, `voice-simulation`), score it
(`evaluation`), and watch it in production (`monitoring`) — where any failure
flows back into a scenario set that is re-run on every change. More skills
and commands are planned — see [ROADMAP.md](ROADMAP.md).

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
│       ├── commands/                 Slash commands (/okareo:<name>). Thin
│       │                             entry points that route to a skill.
│       └── skills/                   One folder per skill. Each is a
│           │                         self-contained Agent Skill.
│           ├── agent-simulation/
│           │   ├── SKILL.md          Instructions + YAML frontmatter.
│           │   └── references/       Extra docs, loaded only when needed.
│           ├── evaluation/
│           ├── monitoring/
│           ├── quickstart/
│           ├── scenario-design/
│           ├── scenario-from-traces/
│           └── voice-simulation/
│
├── skill-template/                   Copy-to-author scaffold for a new
│                                     skill. Lives outside skills/ so it is
│                                     never packaged.
├── command-template.md               Copy-to-author scaffold for a new
│                                     slash command.
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

The plugin bundles the MCP server, all seven skills, and the commands as
one unit:

```
/plugin marketplace add okareo-ai/okareo-tools
/plugin install okareo@okareo-tools
```

The plugin connects to the hosted Okareo MCP server
(`https://tools.okareo.com/mcp`). The first Okareo tool call opens a browser
for a one-time sign-in — no API key needs to be set. Update later with
`/plugin marketplace update okareo-tools`.

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

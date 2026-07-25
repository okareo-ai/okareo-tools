#!/usr/bin/env bash
#
# build.sh — package every skill into an installable .skill file.
#
# A .skill file is a zip archive whose root contains a single skill folder
# with SKILL.md at its top level. It is the portable, installable unit of an
# Agent Skill: drag it into claude.ai, upload it via the Claude API, or load
# it in Claude Code. The same file works on all three surfaces.
#
# Output: dist/<skill-name>-<version>.skill, one per skill.
#
# Usage:   ./scripts/build.sh
# Used by: release.sh and the GitHub Actions release workflow.
#
# Prerequisites: python3 (stdlib only), zip.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$ROOT/plugins/okareo/skills"
PLUGIN_JSON="$ROOT/plugins/okareo/.claude-plugin/plugin.json"
DIST="$ROOT/dist"

VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$PLUGIN_JSON")"

# Refuse to package a skill that fails validation (frontmatter, references,
# and — the contract that matters — only real Okareo MCP tool names).
echo "Validating skills"
python3 "$ROOT/scripts/validate_skills.py"

mkdir -p "$DIST"
rm -f "$DIST"/*.skill

count=0
for skill_path in "$SKILLS_DIR"/*/; do
  skill_name="$(basename "$skill_path")"
  if [[ ! -f "$skill_path/SKILL.md" ]]; then
    echo "  skip $skill_name (no SKILL.md)" >&2
    continue
  fi
  out="$DIST/${skill_name}-${VERSION}.skill"
  # Zip with the skill directory as the archive root, so SKILL.md sits one
  # level down — the layout every Claude surface expects.
  ( cd "$SKILLS_DIR" && zip -r -q "$out" "$skill_name" -x '*.DS_Store' )
  echo "  packaged ${skill_name}-${VERSION}.skill"
  count=$((count + 1))
done

if [[ $count -eq 0 ]]; then
  echo "No skills found under $SKILLS_DIR" >&2
  exit 1
fi
echo "Built $count skill package(s) for v$VERSION in dist/"

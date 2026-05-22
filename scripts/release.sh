#!/usr/bin/env bash
#
# release.sh — publish the Okareo skill packages to all three Claude
# surfaces: Claude Code (plugin marketplace), the Claude API (Skills API),
# and claude.ai (downloadable .skill files hosted on tools.okareo.com).
#
# One git repo is the single source of truth. release.sh first calls
# build.sh to produce the .skill packages, then ships them per surface.
#
# Usage:
#   ./scripts/release.sh                 # build + publish everything
#   ./scripts/release.sh --build-only    # just produce dist/*.skill
#   ./scripts/release.sh --skip-api      # skip the Claude API upload
#
# Prerequisites:
#   - python3                  (JSON parsing — stdlib only)
#   - zip, git
#   - ant CLI + ANTHROPIC_API_KEY   (for the Claude API upload; see
#     https://platform.claude.com/docs/en/build-with-claude/skills-guide)
#
# Claude API skill ids are tracked in skill-ids.json (committed). The first
# release of a skill creates it and records its id; later releases add
# versions to the recorded id.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_JSON="$ROOT/plugins/okareo/.claude-plugin/plugin.json"
DIST="$ROOT/dist"
SKILL_IDS_FILE="$ROOT/skill-ids.json"

BUILD_ONLY=false
SKIP_API=false
for arg in "$@"; do
  case "$arg" in
    --build-only) BUILD_ONLY=true ;;
    --skip-api)   SKIP_API=true ;;
    *) echo "Unknown flag: $arg" >&2; exit 1 ;;
  esac
done

VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$PLUGIN_JSON")"
echo "==> Releasing Okareo tools v$VERSION"

# --- 1. build the .skill packages ------------------------------------------
"$ROOT/scripts/build.sh"
mapfile -t PACKAGES < <(ls "$DIST"/*-"$VERSION".skill)

if $BUILD_ONLY; then
  echo "==> Build-only: packages are in $DIST"
  exit 0
fi

# --- helpers for the API skill-id map --------------------------------------
[[ -f "$SKILL_IDS_FILE" ]] || echo '{}' > "$SKILL_IDS_FILE"
get_id() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],""))' \
    "$SKILL_IDS_FILE" "$1"
}
set_id() {
  python3 - "$SKILL_IDS_FILE" "$1" "$2" <<'PY'
import json, sys
path, name, skill_id = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(path))
data[name] = skill_id
json.dump(data, open(path, "w"), indent=2, sort_keys=True)
open(path, "a").write("\n")
PY
}
title() { echo "$1" | tr '-' ' ' | python3 -c 'import sys; print(sys.stdin.read().title())'; }

# --- 2. Claude API: upload every skill via the Skills API ------------------
# Workspace-scoped: every workspace member gets the new versions.
if ! $SKIP_API; then
  echo "==> Publishing to the Claude API (Skills API)"
  for pkg in "${PACKAGES[@]}"; do
    skill_name="$(basename "$pkg" | sed "s/-${VERSION}\.skill$//")"
    existing_id="$(get_id "$skill_name")"
    if [[ -z "$existing_id" ]]; then
      echo "    $skill_name: no recorded id — creating a new skill"
      new_id="$(ant beta:skills create \
        --display-title "$(title "$skill_name")" \
        --file "$pkg" \
        --beta skills-2025-10-02 \
        --transform id --raw-output)"
      set_id "$skill_name" "$new_id"
      echo "    $skill_name: created $new_id (recorded in skill-ids.json)"
    else
      echo "    $skill_name: adding a version to $existing_id"
      new_version="$(ant beta:skills:versions create \
        --skill-id "$existing_id" \
        --file "$pkg" \
        --beta skills-2025-10-02 \
        --transform version --raw-output)"
      echo "    $skill_name: published version $new_version"
    fi
  done
  echo "    >>> commit skill-ids.json if it changed"
else
  echo "==> Skipping Claude API upload (--skip-api)"
fi

# --- 3. Claude Code: tag the release ---------------------------------------
# The repo itself is the marketplace. Consumers run
# `/plugin marketplace update okareo-tools` to pull the new version.
echo "==> Publishing to Claude Code (plugin marketplace)"
TAG="v$VERSION"
if git -C "$ROOT" rev-parse "$TAG" >/dev/null 2>&1; then
  echo "    tag $TAG already exists — bump version in plugin.json first" >&2
else
  git -C "$ROOT" tag -a "$TAG" -m "Okareo tools $TAG"
  echo "    created git tag $TAG  (push with: git push origin main --tags)"
fi

# --- 4. claude.ai: stage the downloadable .skill files ---------------------
# claude.ai has no upload API for custom skills — users download a .skill
# file and add it under Settings. Host these on tools.okareo.com.
echo "==> Staging claude.ai downloads — upload to tools.okareo.com:"
for p in "${PACKAGES[@]}"; do echo "      $p"; done

echo "==> Release v$VERSION complete"

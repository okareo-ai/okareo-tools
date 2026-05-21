#!/usr/bin/env bash
#
# install.sh — install the Okareo skills into Claude.
#
# Skills are delivered differently on each Claude surface, so this installer
# handles the two scriptable paths and prints instructions for the third.
#
#   ./scripts/install.sh code     Print Claude Code install instructions
#   ./scripts/install.sh api      Upload the skills to your Claude API workspace
#   ./scripts/install.sh          Show this help
#
# The Claude API path needs:  ant CLI + ANTHROPIC_API_KEY
# The hosted Okareo MCP server signs in via the browser on first use;
# OKAREO_API_KEY is only needed for headless/CI (Claude API) usage.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
REPO_SLUG="okareo-ai/okareo-tools"   # <-- edit if you rename the repo

usage() {
  cat <<EOF
Install the Okareo skills into Claude.

  ./scripts/install.sh code     Instructions for Claude Code (recommended)
  ./scripts/install.sh api      Upload skills to your Claude API workspace
  ./scripts/install.sh claude   Instructions for claude.ai

The hosted Okareo MCP server authenticates via a browser sign-in on first
use. OKAREO_API_KEY is only needed for the headless Claude API path below.
EOF
}

install_code() {
  cat <<EOF
==> Claude Code

Run these inside Claude Code. They add this repo as a plugin marketplace
and install the okareo plugin — the MCP server and all skills together:

  /plugin marketplace add ${REPO_SLUG}
  /plugin install okareo@okareo

The plugin connects to the hosted Okareo MCP server. The first Okareo tool
call opens a browser for a one-time sign-in — no API key required.

To update later:  /plugin marketplace update okareo
EOF
}

install_api() {
  echo "==> Claude API — uploading skills to your workspace"
  command -v ant >/dev/null || { echo "ant CLI not found — install it first" >&2; exit 1; }
  : "${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY first}"

  if ! ls "$DIST"/*.skill >/dev/null 2>&1; then
    echo "    no packages in dist/ — building them now"
    "$ROOT/scripts/build.sh"
  fi

  for pkg in "$DIST"/*.skill; do
    name="$(basename "$pkg" .skill)"
    echo "    uploading $name"
    ant beta:skills create \
      --display-title "$name" \
      --file "$pkg" \
      --beta skills-2025-10-02
  done
  echo "    done — attach these skills via the container parameter in your"
  echo "    API requests, and pass the Okareo MCP server as an mcp_servers entry."
}

install_claude_ai() {
  cat <<EOF
==> claude.ai

claude.ai installs skills per individual user, via the web UI:

  1. Download the .skill files from https://tools.okareo.com
  2. In claude.ai, open Settings -> Capabilities -> Skills
  3. Upload each .skill file
  4. Add the Okareo MCP server under Settings -> Connectors

Each teammate repeats this — claude.ai has no org-wide skill distribution.
EOF
}

case "${1:-}" in
  code)   install_code ;;
  api)    install_api ;;
  claude) install_claude_ai ;;
  *)      usage ;;
esac

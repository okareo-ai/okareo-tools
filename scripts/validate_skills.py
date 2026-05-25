#!/usr/bin/env python3
"""validate_skills.py — check every skill and command before it is packaged.

Run by scripts/build.sh (and CI) before producing any .skill file. A skill
that fails here must not ship. Stdlib only — no third-party YAML parser.

Checks, per directory under plugins/okareo/skills/:
  1. SKILL.md exists and has a YAML frontmatter block.
  2. frontmatter `name` equals the directory name.
  3. `description` is present and within DESCRIPTION_MAX_CHARS.
  4. every references/<file> linked from SKILL.md exists on disk.
  5. every snake_case `tool` token (backtick-quoted) is a real Okareo MCP
     tool — see KNOWN_TOOLS. Unknown names are the contract bug this catches.

Checks, per command file under plugins/okareo/commands/*.md:
  1. has a YAML frontmatter block with a non-empty `description`.
  2. every backtick-quoted snake_case tool token is a real Okareo MCP tool.

Usage:  python3 scripts/validate_skills.py
Exit:   0 = all skills and commands valid, 1 = one or more problems found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "plugins" / "okareo" / "skills"
COMMANDS_DIR = ROOT / "plugins" / "okareo" / "commands"

# Anthropic skills cap the frontmatter `description`; stay well under it.
DESCRIPTION_MAX_CHARS = 1024

# The canonical Okareo MCP tool surface. A tool table in any SKILL.md may
# only reference names from this set. Update this list when the MCP server's
# tools change — it is the single source of truth the skills are checked
# against.
KNOWN_TOOLS = {
    # scenarios
    "save_scenario", "list_scenarios", "get_scenario", "create_scenario_version",
    "preview_delete_scenario", "delete_scenario",
    # generation models
    "list_available_llms", "register_generation_model", "list_generation_models",
    "get_generation_model", "update_generation_model", "delete_generation_model",
    # tests & checks
    "list_checks", "run_test", "list_test_runs", "get_test_run_results",
    "get_conversation_transcript", "reevaluate_test_run", "create_or_update_check",
    "generate_check", "get_check", "delete_check",
    # simulations
    "create_or_update_target", "get_target", "list_targets", "delete_target",
    "create_or_update_driver", "get_driver", "list_drivers", "list_driver_voices",
    "run_simulation", "list_simulations",
    # voice monitoring
    "ingest_conversations", "connect_voice_integration", "list_voice_integrations",
    "get_voice_integration", "update_voice_integration",
    "rotate_voice_integration_secret", "delete_voice_integration",
    "get_voice_webhook_url",
    # analytics & dashboards
    "query_analytics", "list_dashboards", "get_dashboard", "save_dashboard",
    "reorder_dashboards", "delete_dashboard",
    # tenants
    "list_tenants", "switch_tenant",
    # documentation
    "get_docs", "get_templates",
}

# A backtick token that looks like an MCP tool: snake_case, lowercase, no
# slash or dot (those are paths, e.g. `references/checks.md`).
TOOL_TOKEN = re.compile(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`")
# A non-tool snake_case allowlist — identifiers that are not MCP tools
# (target-type and config-field names that legitimately appear in backticks).
NON_TOOL_TOKENS = {
    "next_message_params", "start_session_params", "end_session_params",
    "custom_endpoint", "auth_params", "max_parallel_requests",
    "sensitive_fields",
    # Voice target config field names (not MCP tools).
    "account_sid", "auth_token", "to_phone_number", "from_phone_number",
    "output_voice", "edge_type",
    # run_simulation kwargs (peer simulation_params knobs added by
    # specs/023-tool-fixes in okareo-mcp-beta).
    "max_turns", "turn_transition_time", "silence_timeout_ms",
    "checks_at_every_turn", "stop_check",
    # Augmentation strategy keys and field names (under the `augmentation`
    # kwarg on run_simulation). These appear in skill prose when copilots
    # need to reason about voice-simulation realism conditions.
    "directed_speech", "secondary_speaker", "barge_in",
    "noise_profile", "noise_snr_db",
    # Template names registered in src/tools/docs.py — referenced via
    # get_templates([...]); they are not MCP tools themselves.
    "voice_augmentations",
}
REF_LINK = re.compile(r"\(references/([^)]+)\)")


def split_frontmatter(text: str) -> dict[str, str] | None:
    """Return frontmatter as a flat key -> raw-value dict, or None if absent.

    Handles the simple shape every Okareo SKILL.md uses: top-level keys,
    plus YAML folded scalars (`key: >-`) whose value is the indented block
    that follows.
    """
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end].strip("\n").splitlines()

    fields: dict[str, str] = {}
    key: str | None = None
    folded: list[str] = []
    for line in block:
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m and not line.startswith(" "):
            if key is not None:
                fields[key] = " ".join(folded).strip()
            key, rest = m.group(1), m.group(2).strip()
            folded = []
            if rest in (">-", ">", "|", "|-", ""):
                continue
            folded = [rest]
        elif key is not None:
            folded.append(line.strip())
    if key is not None:
        fields[key] = " ".join(folded).strip()
    return fields


def validate_skill(skill_dir: Path) -> list[str]:
    """Return a list of problem strings for one skill (empty == valid)."""
    name = skill_dir.name
    problems: list[str] = []

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"{name}: no SKILL.md"]

    text = skill_md.read_text(encoding="utf-8")
    fm = split_frontmatter(text)
    if fm is None:
        return [f"{name}: SKILL.md has no YAML frontmatter block"]

    fm_name = fm.get("name", "")
    if fm_name != name:
        problems.append(
            f"{name}: frontmatter name {fm_name!r} != directory name {name!r}"
        )

    description = fm.get("description", "")
    if not description:
        problems.append(f"{name}: frontmatter has no description")
    elif len(description) > DESCRIPTION_MAX_CHARS:
        problems.append(
            f"{name}: description is {len(description)} chars "
            f"(max {DESCRIPTION_MAX_CHARS})"
        )

    for ref in REF_LINK.findall(text):
        if not (skill_dir / "references" / ref).is_file():
            problems.append(f"{name}: references/{ref} is linked but missing")

    for token in sorted(set(TOOL_TOKEN.findall(text))):
        if token in NON_TOOL_TOKENS:
            continue
        if token not in KNOWN_TOOLS:
            problems.append(
                f"{name}: `{token}` is not a known Okareo MCP tool "
                f"(see KNOWN_TOOLS in scripts/validate_skills.py)"
            )

    return problems


def validate_command(command_md: Path) -> list[str]:
    """Return a list of problem strings for one command file (empty == valid).

    Commands are thin Markdown files; the name comes from the filename. They
    must carry a `description` and may only reference real MCP tool names.
    """
    name = command_md.name
    problems: list[str] = []

    text = command_md.read_text(encoding="utf-8")
    fm = split_frontmatter(text)
    if fm is None:
        return [f"{name}: command has no YAML frontmatter block"]

    description = fm.get("description", "")
    if not description:
        problems.append(f"{name}: frontmatter has no description")
    elif len(description) > DESCRIPTION_MAX_CHARS:
        problems.append(
            f"{name}: description is {len(description)} chars "
            f"(max {DESCRIPTION_MAX_CHARS})"
        )

    for token in sorted(set(TOOL_TOKEN.findall(text))):
        if token in NON_TOOL_TOKENS:
            continue
        if token not in KNOWN_TOOLS:
            problems.append(
                f"{name}: `{token}` is not a known Okareo MCP tool "
                f"(see KNOWN_TOOLS in scripts/validate_skills.py)"
            )

    return problems


def main() -> int:
    if not SKILLS_DIR.is_dir():
        print(f"No skills directory at {SKILLS_DIR}", file=sys.stderr)
        return 1

    skill_dirs = sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir())
    if not skill_dirs:
        print(f"No skills found under {SKILLS_DIR}", file=sys.stderr)
        return 1

    all_problems: list[str] = []

    print("Skills:")
    for skill_dir in skill_dirs:
        problems = validate_skill(skill_dir)
        all_problems.extend(problems)
        status = "ok" if not problems else f"{len(problems)} problem(s)"
        print(f"  {skill_dir.name}: {status}")

    command_files = (
        sorted(COMMANDS_DIR.glob("*.md")) if COMMANDS_DIR.is_dir() else []
    )
    if command_files:
        print("Commands:")
        for command_md in command_files:
            problems = validate_command(command_md)
            all_problems.extend(problems)
            status = "ok" if not problems else f"{len(problems)} problem(s)"
            print(f"  {command_md.name}: {status}")

    if all_problems:
        print(f"\nValidation failed — {len(all_problems)} problem(s):",
              file=sys.stderr)
        for p in all_problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"\nAll {len(skill_dirs)} skill(s) and "
          f"{len(command_files)} command(s) valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

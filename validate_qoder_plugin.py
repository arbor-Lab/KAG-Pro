#!/usr/bin/env python3
"""Validate the kag-pro-edu Qoder plugin package structure.

Checks (stdlib only, no external deps):
  1. .qoder-plugin/plugin.json is valid JSON with required fields
  2. Paths referenced by the manifest exist (skills, mcp.json, commands, logo)
  3. mcp.json is valid and declares at least one runnable MCP server
  4. Every skills/<name>/SKILL.md has YAML frontmatter with name + description
  5. Every commands/*.md has frontmatter with name + description
  6. hooks/hooks.json (if present) is valid JSON

Exit code 0 = all checks pass, 1 = one or more failures.

Usage: python validate_qoder_plugin.py [plugin_dir]
"""

import json
import sys
from pathlib import Path

PLUGIN_DIR_DEFAULT = Path(__file__).resolve().parent / "kag-pro-edu"

errors: list[str] = []
warnings: list[str] = []
checks: list[str] = []


def ok(msg: str) -> None:
    checks.append(msg)


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def parse_frontmatter(text: str) -> dict | None:
    """Parse a minimal YAML frontmatter block (key: value) at file start."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fm: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fm
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return None  # no closing delimiter


def validate_json(path: Path) -> dict | None:
    if not path.is_file():
        err(f"missing file: {path}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ok(f"valid JSON: {path.name}")
        return data
    except json.JSONDecodeError as e:
        err(f"invalid JSON in {path.name}: {e}")
        return None


def validate_plugin_manifest(plugin_dir: Path) -> dict | None:
    manifest_path = plugin_dir / ".qoder-plugin" / "plugin.json"
    data = validate_json(manifest_path)
    if data is None:
        return None
    for key in ("name", "version"):
        if not data.get(key):
            err(f"plugin.json missing required field: {key}")
    if not (data.get("displayName") or data.get("description")):
        err("plugin.json needs at least one of displayName/description")
    # Referenced paths
    for ref_key in ("skills", "commands", "mcpServers", "logo"):
        ref = data.get(ref_key)
        if not ref:
            continue
        target = (plugin_dir / ref).resolve()
        if not target.exists():
            err(f"plugin.json '{ref_key}' -> missing path: {ref}")
        else:
            ok(f"path exists for '{ref_key}': {ref}")
    return data


def validate_mcp(plugin_dir: Path) -> None:
    data = validate_json(plugin_dir / "mcp.json")
    if data is None:
        return
    servers = data.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        err("mcp.json has no mcpServers entries")
        return
    for name, cfg in servers.items():
        if not cfg.get("command"):
            err(f"mcp server '{name}' missing 'command'")
        if "args" not in cfg:
            warn(f"mcp server '{name}' has no 'args'")
        ok(f"mcp server declared: {name}")


def validate_markdown_frontmatter(path: Path, require_name: bool = True) -> None:
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    rel = path.relative_to(path.parents[2]) if len(path.parents) >= 3 else path.name
    if fm is None:
        if require_name:
            err(f"{rel}: missing/!closed YAML frontmatter")
        else:
            warn(f"{rel}: no frontmatter")
        return
    if require_name and not fm.get("name"):
        err(f"{rel}: frontmatter missing 'name'")
    if not fm.get("description"):
        err(f"{rel}: frontmatter missing 'description'")
    if fm.get("name") and fm.get("description"):
        ok(f"frontmatter valid: {rel}")


def validate_skills(plugin_dir: Path) -> None:
    skills_dir = plugin_dir / "skills"
    if not skills_dir.is_dir():
        err("skills/ directory missing")
        return
    skill_files = sorted(skills_dir.glob("*/SKILL.md"))
    if not skill_files:
        err("no SKILL.md files found under skills/")
        return
    for sf in skill_files:
        validate_markdown_frontmatter(sf, require_name=True)
    ok(f"found {len(skill_files)} skill(s)")


def validate_commands(plugin_dir: Path) -> None:
    commands_dir = plugin_dir / "commands"
    if not commands_dir.is_dir():
        warn("commands/ directory missing (optional)")
        return
    cmd_files = sorted(commands_dir.glob("*.md"))
    for cf in cmd_files:
        validate_markdown_frontmatter(cf, require_name=True)
    ok(f"found {len(cmd_files)} command(s)")


def validate_hooks(plugin_dir: Path) -> None:
    hooks_path = plugin_dir / "hooks" / "hooks.json"
    if hooks_path.is_file():
        validate_json(hooks_path)


def main() -> int:
    plugin_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else PLUGIN_DIR_DEFAULT
    print(f"Validating Qoder plugin at: {plugin_dir}\n")

    if not plugin_dir.is_dir():
        print(f"ERROR: plugin directory not found: {plugin_dir}")
        return 1

    validate_plugin_manifest(plugin_dir)
    validate_mcp(plugin_dir)
    validate_skills(plugin_dir)
    validate_commands(plugin_dir)
    validate_hooks(plugin_dir)

    for c in checks:
        print(f"  [OK]   {c}")
    for w in warnings:
        print(f"  [WARN] {w}")
    for e in errors:
        print(f"  [FAIL] {e}")

    print()
    print(f"Summary: {len(checks)} passed, {len(warnings)} warning(s), {len(errors)} error(s)")
    if errors:
        print("RESULT: INVALID")
        return 1
    print("RESULT: VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

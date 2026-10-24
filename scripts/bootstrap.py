#!/usr/bin/env python3
"""SpecNovelist Bootstrapper for Host Projects.

Configures a host novel repository to use SpecNovelist as a toolkit or external dependency
WITHOUT copying or symlinking files:
  1. Configures `.agents/skills.json` to point the agent's skill discovery to SpecNovelist's skills.
  2. Injects an `@[SpecNovelist Guidelines](<path>/AGENTS.md)` include into the host's `AGENTS.md`.

Usage:
    python .specnovelist/scripts/bootstrap.py
    # or
    python third_party/specnovelist/scripts/bootstrap.py
"""
import json
import sys
from pathlib import Path


def find_host_root(specnovel_root: Path) -> Path:
    cur = specnovel_root.resolve().parent
    while cur != cur.parent:
        if (cur / ".git").exists():
            return cur
        cur = cur.parent
    return specnovel_root.resolve().parent


def bootstrap(specnovel_dir: Path) -> None:
    host_root = find_host_root(specnovel_dir)
    print(f"Configuring SpecNovelist in host project: {host_root}")

    # Relative path from host root to SpecNovelist folder (e.g. '.specnovelist')
    try:
        rel_specnovel = specnovel_dir.resolve().relative_to(host_root.resolve()).as_posix()
    except ValueError:
        rel_specnovel = ".specnovelist"

    rel_skills_path = f"{rel_specnovel}/.agents/skills"
    rel_agents_rule = f"@[SpecNovelist Guidelines]({rel_specnovel}/AGENTS.md)"

    # 1. Configure .agents/skills.json (Path-based skill registration)
    agents_dir = host_root / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    skills_json_path = agents_dir / "skills.json"

    skills_config = {"entries": []}
    if skills_json_path.exists():
        try:
            skills_config = json.loads(skills_json_path.read_text(encoding="utf-8"))
        except Exception:
            skills_config = {"entries": []}

    entries = skills_config.get("entries", [])
    existing_paths = [e.get("path") for e in entries if isinstance(e, dict)]

    if rel_skills_path not in existing_paths:
        entries.append({"path": rel_skills_path})
        skills_config["entries"] = entries
        skills_json_path.write_text(json.dumps(skills_config, indent=2) + "\n", encoding="utf-8")
        print(f"  [configured] .agents/skills.json -> added path '{rel_skills_path}'")
    else:
        print(f"  [verified] .agents/skills.json already contains '{rel_skills_path}'")

    # 2. Configure AGENTS.md (Include-based rule expansion)
    dst_agents = host_root / "AGENTS.md"
    if not dst_agents.exists():
        dst_agents.write_text(
            f"# Project Agent Guidelines\n\n{rel_agents_rule}\n",
            encoding="utf-8",
        )
        print(f"  [created] AGENTS.md with rule include: {rel_agents_rule}")
    else:
        content = dst_agents.read_text(encoding="utf-8")
        if rel_agents_rule not in content and "SpecNovelist" not in content:
            updated = content.rstrip() + f"\n\n{rel_agents_rule}\n"
            dst_agents.write_text(updated, encoding="utf-8")
            print(f"  [updated] AGENTS.md -> added rule include: {rel_agents_rule}")
        else:
            print("  [verified] AGENTS.md already references SpecNovelist guidelines")

    print("\nSpecNovelist configuration complete! Zero files copied or symlinked.")
    print("Your AI agents will automatically discover the SpecNovelist skills and rules.")


def main():
    specnovel_dir = Path(__file__).resolve().parent.parent
    bootstrap(specnovel_dir)


if __name__ == "__main__":
    main()

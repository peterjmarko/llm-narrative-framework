#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 [Your Name/Institution]
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Filename: src/finalize_release.py

"""
Automated Release Finalization Script.

This script automates all steps required to finalize a new release,
creating a single, non-interactive command for maintainers.

Workflow:
1.  **Determine Next Version**: Runs `cz bump --dry-run` to find the
    semantically correct next version number based on commit history.
2.  **Create Release Commit**: Executes `cz bump` to update pyproject.toml,
    create the initial release commit, and apply the Git tag.
3.  **Generate Detailed Changelog**: Gathers all commits since the last
    release, formats them (including full multi-line commit bodies), and
    prepends them to CHANGELOG.md.
4.  **Finalize Release**: Amends the release commit to include the detailed
    changelog and force-moves the Git tag to the final, amended commit,
    ensuring the tag points to the fully documented release.

Usage (via pdm script):
    pdm run release
"""

import subprocess
import sys
import re
import os
from datetime import datetime

# ANSI color codes for console output
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_CYAN = '\033[96m'
C_RESET = '\033[0m'

def run_command(command, description):
    """Runs a command, captures its output, and handles errors."""
    print(f"{C_CYAN}--- {description} ---{C_RESET}")
    print(f"Executing: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        print(result.stdout)
        if result.stderr:
            print(f"{C_YELLOW}Stderr: {result.stderr}{C_RESET}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"{C_RED}ERROR: Command failed with exit code {e.returncode}{C_RESET}")
        print(f"{C_RED}Stdout:{C_RESET}\n{e.stdout}")
        print(f"{C_RED}Stderr:{C_RESET}\n{e.stderr}")
        sys.exit(1)

def get_next_version():
    """Determines the next version using 'cz bump --dry-run'."""
    print(f"{C_CYAN}--- Determining next version... ---{C_RESET}")
    try:
        output = subprocess.check_output(
            ["pdm", "run", "cz", "bump", "--dry-run"],
            text=True,
            encoding='utf-8',
            stderr=subprocess.STDOUT
        )
        match = re.search(r"tag to create:\s*(v\d+\.\d+\.\d+)", output)
        if match:
            version = match.group(1)
            print(f"{C_GREEN}Detected next version: {version}{C_RESET}")
            return version
        if "[NO_COMMITS_TO_BUMP]" in output:
            print(f"{C_YELLOW}No new commits to bump. Nothing to release.{C_RESET}")
            return None
        raise RuntimeError(f"Could not parse next version from cz output:\n{output}")
    except subprocess.CalledProcessError as e:
        if "[NO_COMMITS_TO_BUMP]" in e.output:
            print(f"{C_YELLOW}No new commits to bump. Nothing to release.{C_RESET}")
            return None
        print(f"{C_RED}ERROR: Failed to determine next version.{C_RESET}\n{e.output}")
        sys.exit(1)

def generate_detailed_changelog(new_version):
    """Generates a detailed changelog entry and prepends it to the file."""
    print(f"{C_CYAN}--- Generating detailed changelog for {new_version}... ---{C_RESET}")
    try:
        # Get the previous tag to define the commit range
        previous_tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0", f"{new_version}^"],
            text=True
        ).strip()

        # Get commit logs in a parsable format
        commit_log = subprocess.check_output(
            ["git", "log", f"{previous_tag}..{new_version}", "--pretty=format:%s%n%b%n--END--"],
            text=True,
            encoding='utf-8'
        ).strip()

        # Group commits by type (feat, fix, etc.)
        commits_by_type = {}
        for commit_str in commit_log.split("--END--"):
            commit_str = commit_str.strip()
            if not commit_str:
                continue
            lines = commit_str.split('\n')
            header = lines[0]
            body = "\n".join(lines[1:]).strip()
            
            match = re.match(r"(\w+)(?:\(([\w,-]+)\))?:\s*(.+)", header)
            if not match:
                continue
            
            commit_type, _, subject = match.groups()
            
            if commit_type not in commits_by_type:
                commits_by_type[commit_type] = []
            
            entry = f"- **{subject}**"
            if body:
                indented_body = "\n".join([f"  {line}" for line in body.split('\n')])
                entry += f"\n{indented_body}"
            commits_by_type[commit_type].append(entry)

        # Build the new changelog section
        today = datetime.now().strftime("%Y-%m-%d")
        new_changelog_section = [f"## {new_version.lstrip('v')} ({today})\n"]
        type_map = {"feat": "Features", "fix": "Fixes", "docs": "Documentation", "chore": "Chore"}

        for commit_type, commits in sorted(commits_by_type.items()):
            heading = type_map.get(commit_type, commit_type.capitalize())
            new_changelog_section.append(f"### {heading}\n")
            new_changelog_section.extend(commits)
            new_changelog_section.append("") # Add a blank line

        # Read old changelog and prepend the new section
        changelog_path = 'CHANGELOG.md'
        with open(changelog_path, 'r', encoding='utf-8') as f:
            old_content = f.read()
        
        # Find the start of the existing content (after the title)
        header_match = re.search(r"(# Changelog\n\n)", old_content)
        if header_match:
            start_of_entries = header_match.end(1)
            new_content = old_content[:start_of_entries] + "\n".join(new_changelog_section) + old_content[start_of_entries:]
        else: # Fallback if header is missing
            new_content = "\n".join(new_changelog_section) + old_content

        with open(changelog_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"{C_GREEN}Successfully updated {changelog_path}.{C_RESET}")

    except Exception as e:
        print(f"{C_RED}ERROR: Failed to generate changelog: {e}{C_RESET}")
        sys.exit(1)

def main():
    """Orchestrates the entire release finalization process."""
    print(f"\n{C_GREEN}Starting automated release process...{C_RESET}")
    
    # Step 1: Determine the next version
    new_version = get_next_version()
    if not new_version:
        print(f"\n{C_GREEN}Process finished. Nothing to release.{C_RESET}")
        return

    # Step 2: Run the initial bump (without detailed changelog)
    run_command(
        ["pdm", "run", "cz", "bump", new_version.lstrip('v')],
        "Step 1/4: Bumping version and creating initial commit/tag"
    )

    # Step 3: Generate the detailed changelog
    generate_detailed_changelog(new_version)

    # Step 4: Finalize by amending the commit and moving the tag
    run_command(
        ["git", "add", "CHANGELOG.md"],
        "Step 2/4: Staging detailed changelog"
    )
    run_command(
        ["git", "commit", "--amend", "--no-edit"],
        "Step 3/4: Amending release commit"
    )
    run_command(
        ["git", "tag", "-f", new_version],
        f"Step 4/4: Moving tag {new_version} to final commit"
    )
    
    print(f"\n{C_GREEN}Release {new_version} finalized successfully!{C_RESET}")

if __name__ == "__main__":
    main()

# === End of src/finalize_release.py ===
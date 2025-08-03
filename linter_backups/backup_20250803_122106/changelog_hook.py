#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Filename: scripts/changelog_hook.py
"""
Commitizen hook to correctly format the changelog.

This script is called by commitizen during the `cz bump` process. It receives
the new changelog entry, ensures it is followed by exactly one blank line,
and then prepends it to the existing CHANGELOG.md.

This fixes an issue where the default `keep_a_changelog` format does not
insert a blank line between release entries.
"""
import sys

def main():
    """Reads, formats, and writes the changelog."""
    changelog_file = sys.argv[1]
    new_entry = sys.argv[2]

    try:
        with open(changelog_file, "r", encoding="utf-8") as f:
            existing_content = f.read()
    except FileNotFoundError:
        existing_content = ""

    # Ensure the new entry ends with two newlines for a blank line separator.
    formatted_entry = new_entry.strip() + "\n\n"
    
    final_content = formatted_entry + existing_content

    with open(changelog_file, "w", encoding="utf-8") as f:
        f.write(final_content)

if __name__ == "__main__":
    main()
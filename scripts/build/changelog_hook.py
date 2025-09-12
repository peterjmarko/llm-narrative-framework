#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 Peter J. Marko
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
# Filename: scripts/build/changelog_hook.py

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

# === End of scripts/build/changelog_hook.py ===

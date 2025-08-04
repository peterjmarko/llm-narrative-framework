#!/usr/bin/env python3
#-*- coding: utf-8 -*-
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
# Filename: scripts/validate_import_file.py

"""
Validates the content of the generated Solar Fire import file.

This utility script compares the list of people in the programmatically
generated import file (`sf_data_import.txt`) against a manually curated
ground-truth list to ensure they contain the exact same set of individuals.
"""

import csv
from pathlib import Path

# --- File Paths ---
# Construct paths relative to this script's location for robustness.
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
TEMP_DIR = ROOT_DIR / "data" / "temp"
MANUAL_FILE = TEMP_DIR / "manual_output.txt"
PROGRAMMATIC_FILE = TEMP_DIR / "programmatic_output.txt"


def load_list_from_file(filepath: Path) -> set:
    """Loads and normalizes a 'Name (Year)' list from a text file into a set."""
    if not filepath.exists():
        print(f"ERROR: File not found at '{filepath.resolve()}'")
        return set()
        
    normalized_set = set()
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                # Normalize whitespace and smart quotes for robust comparison
                normalized_line = ' '.join(line.strip().split())
                normalized_line = normalized_line.replace("’", "'")
                normalized_set.add(normalized_line)
    return normalized_set


def main():
    """Main function to compare the two lists and report differences."""
    print(f"Loading manual list from '{MANUAL_FILE}'...")
    manual_set = load_list_from_file(MANUAL_FILE)
    
    print(f"Loading programmatic list from '{PROGRAMMATIC_FILE}'...")
    programmatic_set = load_list_from_file(PROGRAMMATIC_FILE)

    if not manual_set or not programmatic_set:
        print("Could not proceed with comparison due to one or both files being empty/not found.")
        return

    print(f"\nManual list contains {len(manual_set)} unique entries.")
    print(f"Programmatic list contains {len(programmatic_set)} unique entries.")

    missing_from_programmatic = manual_set - programmatic_set
    extra_in_programmatic = programmatic_set - manual_set

    print("-" * 40)
    if not missing_from_programmatic and not extra_in_programmatic:
        print("✅ SUCCESS: The lists match perfectly.")
    else:
        print("❌ MISMATCH FOUND:")
        if missing_from_programmatic:
            print("\nEntries in MANUAL list but MISSING from Programmatic list:")
            for person in sorted(list(missing_from_programmatic)):
                print(f"  - {person}")
        
        if extra_in_programmatic:
            print("\nEXTRA entries in Programmatic list that are NOT in Manual list:")
            for person in sorted(list(extra_in_programmatic)):
                print(f"  - {person}")
    print("-" * 40)


if __name__ == "__main__":
    main()

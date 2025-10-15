#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
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
# Filename: scripts/testing/inspect_special_chars.py

import re
from collections import defaultdict
from pathlib import Path

def analyze_names(file_path):
    """Analyzes a tab-separated file of names for special characters."""
    
    char_counts = defaultdict(int)
    char_examples = defaultdict(str)

    # CORRECTED REGEX: Removed the erroneous spaces between 0- and 9.
    special_char_regex = re.compile(r"[^a-zA-Z0-9\s,\.'\t-]")

    print(f"Analyzing names in '{file_path}'...\n")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    last_name, first_name = line.split('\t')
                    full_name_for_analysis = f"{last_name}, {first_name}"
                except ValueError:
                    print(f"Warning: Skipping malformed line {i}: '{line}'")
                    continue
                
                found_chars = special_char_regex.findall(full_name_for_analysis)
                
                for char in found_chars:
                    char_counts[char] += 1
                    if not char_examples[char]:
                        char_examples[char] = full_name_for_analysis

    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'")
        return

    if not char_counts:
        print("No special characters found. All names use standard characters.")
        return

    # --- Generate the Report ---
    print("--- Special Character Analysis Report ---")
    print(f"{'Character':<12} | {'Count':<10} | {'Example Name'} (truncated)")
    print("-" * 60)

    sorted_chars = sorted(char_counts.items(), key=lambda item: item[1], reverse=True)

    for char, count in sorted_chars:
        example = (char_examples[char][:50] + '...') if len(char_examples[char]) > 50 else char_examples[char]
        print(f"{repr(char):<12} | {count:<10} | {example}")

if __name__ == "__main__":
    script_dir = Path(__file__).parent
    names_file = script_dir / 'adb_names.txt'
    
    analyze_names(names_file)

# === End of scripts/testing/inspect_special_chars.py ===

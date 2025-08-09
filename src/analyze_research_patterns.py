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
# Filename: src/analyze_research_patterns.py

"""
A diagnostic tool to help maintain the list of Astro-Databank 'Research' categories.

This script analyzes the `adb_validation_report.csv` to find entries that
failed specifically because no Wikipedia link could be found. For these
failures, it applies a heuristic to identify potential new Research categories:
it looks for names that contain a colon but no comma (e.g., 'Event: Plane Crash').

The script then prints a summary of the most common category prefixes it
discovers and provides a formatted list of suggestions (for prefixes that
appear two or more times) that can be directly copied into the
`data/config/adb_research_categories.json` configuration file.

This helps improve the accuracy of the `is_research_entry` function over
time by identifying new patterns in the data as the Astro-Databank evolves.
"""

import csv
import json
import re
from pathlib import Path
from collections import Counter

# --- ANSI Color Codes ---
class Colors:
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    RESET = '\033[0m'

def analyze_failures(report_path: Path = Path("data/reports/adb_validation_report.csv")):
    """Analyzes failed entries to identify patterns."""
    
    if not report_path.exists():
        print(f"{Colors.RED}Report file not found: {report_path}{Colors.RESET}")
        return
    
    no_wiki_entries = []
    potential_research = []
    
    with open(report_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Use a more general substring to catch all "no link" failure notes.
            if "No Wikipedia link" in row.get('Notes', ''):
                name = row['ADB_Name']
                no_wiki_entries.append(name)
                
                # Check for potential research patterns
                if ':' in name and ',' not in name:
                    prefix = name.split(':', 1)[0] + ':'
                    potential_research.append(prefix)
    
    print(f"\nAnalysis of {len(no_wiki_entries)} entries with no Wikipedia link:")
    print("-" * 50)
    
    # Count prefix patterns
    prefix_counts = Counter(potential_research)
    
    if prefix_counts:
        print("\nPotential Research Category Prefixes:")
        for prefix, count in prefix_counts.most_common(20):
            print(f"  {prefix:<30} ({count} entries)")
    else:
        print("\nNo new potential Research Category prefixes were detected among the failures.")
    
    # Check for other patterns
    print("\nSample entries without colons (first 20):")
    non_colon = [name for name in no_wiki_entries if ':' not in name and ',' not in name]
    for name in non_colon[:20]:
        print(f"  - {name}")
    
    # Suggest additions
    print("\n" + "="*50)
    print("SUGGESTED ADDITIONS TO adb_research_categories.json:")
    print("="*50)
    
    new_prefixes = [p for p, c in prefix_counts.most_common() if c >= 2]
    if new_prefixes:
        print(f'{Colors.YELLOW}\n"prefixes": [')
        for prefix in sorted(new_prefixes):
            print(f'  "{prefix}",')
        print(f']{Colors.RESET}')
    else:
        print(f"(none)")
        print(f"{Colors.GREEN}\nNo new prefixes met the threshold for suggestion (>= 2 entries).\n{Colors.RESET}")

if __name__ == "__main__":
    analyze_failures()

# === End of src/analyze_research_patterns.py ===

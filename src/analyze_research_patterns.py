#!/usr/bin/env python3
"""
Analyzes validation failures to identify potential new Research categories.
"""

import csv
import json
import re
from pathlib import Path
from collections import Counter

def analyze_failures(report_path: Path = Path("data/reports/adb_validation_report.csv")):
    """Analyzes failed entries to identify patterns."""
    
    if not report_path.exists():
        print(f"Report file not found: {report_path}")
        return
    
    no_wiki_entries = []
    potential_research = []
    
    with open(report_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "No Wikipedia link found on ADB page" in row.get('Notes', ''):
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
            print(f"  {prefix:<30} ({count} occurrences)")
    
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
        print('\n"prefixes": [')
        for prefix in new_prefixes:
            print(f'  "{prefix}",')
        print(']')

if __name__ == "__main__":
    analyze_failures()
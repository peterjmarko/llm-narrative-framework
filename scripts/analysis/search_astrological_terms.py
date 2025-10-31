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
# Filename: scripts/analysis/search_astrological_terms.py

import sys
import csv
import re
from pathlib import Path
from collections import defaultdict

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "reports"
DATA_DIR = PROJECT_ROOT / "data" / "foundational_assets" / "neutralized_delineations"

# Hardcoded input file
INPUT_FILE = PROJECT_ROOT / "data" / "reports" / "sf_astrological_terms.txt"

def create_report(found_words, searched_files_count, output_dir):
    """Creates a report from the search results, listing Row AND Column."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / "astrological_terms_report.txt"

    with open(report_file, "w") as f:
        f.write("Astrological Terms Search Report\n")
        f.write("=" * 35 + "\n\n")
        f.write(f"Total files searched: {searched_files_count}\n")
        f.write(f"Source word list: {INPUT_FILE.name}\n\n")

        if not found_words:
            f.write("No occurrences of the specified words were found in the targeted columns.\n")
            return

        for word, file_locations in sorted(found_words.items()):
            f.write(f"'{word}':\n")
            for file_path, matches in sorted(file_locations.items()):
                f.write(f"  - Found in: {file_path.name}\n")
                # Matches is now a list of tuples: (row_number, column_number)
                # We sort them to ensure neat output order (by row, then by column)
                for row_num, col_num in sorted(matches):
                    f.write(f"    - Row {row_num}, Column {col_num}\n")
            f.write("\n")
    print(f"Report successfully generated at: {report_file}")


def search_words_in_files(word_list, data_dir):
    """
    Searches for a list of whole words in ONLY the second column of all CSV files.
    Records both row and column number upon finding a match.
    """
    found_words = defaultdict(lambda: defaultdict(list))
    searched_files_count = 0

    # Define which column index to target (0-based index).
    # Index 1 = The second column.
    TARGET_COL_IDX = 1

    if not data_dir.is_dir():
        print(f"Error: Data directory not found at '{data_dir}'", file=sys.stderr)
        sys.exit(1)

    for file_path in data_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() == '.csv':
            searched_files_count += 1
            try:
                with open(file_path, "r", encoding="utf-8", newline='') as f:
                    reader = csv.reader(f)
                    for row_num, row in enumerate(reader, 1):
                        # Ensure the row actually HAS a second column before trying to read it
                        if len(row) > TARGET_COL_IDX:
                            cell_content = row[TARGET_COL_IDX]

                            for word in word_list:
                                # Whole word, case-insensitive search using Regex
                                if re.search(r'\b' + re.escape(word) + r'\b', cell_content, re.IGNORECASE):
                                    # Record matches as a tuple: (row_number, column_number)
                                    # We add +1 to TARGET_COL_IDX so the report says "Column 2" instead of "Column 1"
                                    found_words[word][file_path].append((row_num, TARGET_COL_IDX + 1))

            except csv.Error as e:
                print(f"CSV Error reading file {file_path} near line {reader.line_num}: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Could not read file {file_path}: {e}", file=sys.stderr)

    return found_words, searched_files_count


def main():
    """Main function to run the word search and report generation."""
    if not INPUT_FILE.is_file():
        print(f"Error: Input file not found at '{INPUT_FILE}'", file=sys.stderr)
        sys.exit(1)

    try:
        with open(INPUT_FILE, "r") as f:
            words_to_search = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading word file: {e}", file=sys.stderr)
        sys.exit(1)

    if not words_to_search:
        print("The provided word file is empty. No words to search.", file=sys.stderr)
        return

    print(f"Reading words from: {INPUT_FILE}")
    print(f"Searching for WHOLE WORDS in column 2 of CSV files in: {DATA_DIR}")
    print("Starting search...")
    found_words, searched_files_count = search_words_in_files(words_to_search, DATA_DIR)
    print("Search complete. Generating report...")
    create_report(found_words, searched_files_count, OUTPUT_DIR)


if __name__ == "__main__":
    main()

# === End of scripts/analysis/search_astrological_terms.py ===

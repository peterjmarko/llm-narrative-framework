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
# Filename: src/create_subject_database.py

"""
Creates a master subject database by flattening and enriching chart data.

This script acts as a crucial data integration and validation step. It reads
the multi-line chart data from Solar Fire (`sf_chart_export.csv`), flattens
it into one row per subject, and enriches it by cross-referencing multiple
source files to add Rank, ARN, and Eminence Score. The final output is a
clean, sorted `subject_db.csv` file, which serves as the primary input for
the final database generation script.
"""

import argparse
import csv
import logging
import re
import sys
from pathlib import Path

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- Helper Functions ---

def normalize_name(name: str) -> str:
    """Normalizes a name for robust cross-referencing."""
    if ',' in name:
        parts = name.split(',', 1)
        name = f"{parts[1].strip()} {parts[0].strip()}"
    return ' '.join(name.lower().split())

def load_lookup_data(filepath: Path, key_col: str, val_col: str) -> dict:
    """Generic function to load a lookup dictionary from a CSV."""
    lookup = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                lookup[row[key_col]] = row[val_col]
        return lookup
    except FileNotFoundError:
        logging.error(f"Lookup file not found: {filepath}")
        sys.exit(1)
    except KeyError as e:
        logging.error(f"Missing expected column '{e}' in {filepath}")
        sys.exit(1)

def load_chart_data_map(filepath: Path) -> dict:
    """Parses sf_chart_export.csv and returns a dictionary keyed by normalized name."""
    chart_map = {}
    try:
        with open(filepath, 'r', encoding='latin-1') as f:
            lines = [line.strip() for line in f]
    except FileNotFoundError:
        logging.error(f"Chart export file not found: {filepath}")
        sys.exit(1)

    chart_points_order = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven"]

    for i in range(0, len(lines), 14):
        block = lines[i:i+14]
        if len(block) < 14: continue

        person_info = next(csv.reader([block[0]]))
        name = person_info[0]
        norm_name = normalize_name(name)

        placements_raw = {next(csv.reader([line]))[0]: next(csv.reader([line]))[2] for line in block[2:]}
        placements = {p: placements_raw.get(p, '') for p in chart_points_order}

        chart_map[norm_name] = {
            "Name": name,
            "Date": person_info[1], "Time": person_info[2], "ZoneAbbrev": person_info[3],
            "ZoneTime": person_info[4], "Place": person_info[5], "Country": person_info[6],
            "Latitude": person_info[7], "Longitude": person_info[8],
            **placements
        }
    return chart_map


def main():
    parser = argparse.ArgumentParser(description="Create a master subject database.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--chart-export", default="data/foundational_assets/sf_chart_export.csv")
    parser.add_argument("--filtered-5000", default="data/adb_filtered_5000.txt")
    parser.add_argument("--eminence-scores", default="data/eminence_scores.csv")
    parser.add_argument("--raw-export", default="data/sources/adb_raw_export.txt")
    parser.add_argument("--output-file", default="data/subject_db.csv")
    args = parser.parse_args()

    # --- Load all necessary lookup tables ---
    logging.info("Loading lookup data...")
    eminence_scores = load_lookup_data(Path(args.eminence_scores), 'ARN', 'EminenceScore')
    
    arn_map = {}
    for line in Path(args.raw_export).read_text(encoding='utf-8').splitlines():
        parts = line.split('\t')
        if len(parts) > 1 and parts[0].isdigit():
            name_no_slug = re.sub(r'\(.*\)', '', parts[1]).strip()
            arn_map[normalize_name(name_no_slug)] = parts[0]

    # --- Pre-process the chart export into a searchable map ---
    logging.info(f"Loading and parsing chart data from {args.chart_export}...")
    chart_data_map = load_chart_data_map(Path(args.chart_export))

    # --- Assemble final list using the filtered list as the source of truth ---
    logging.info(f"Assembling master database from primary list: {args.filtered_5000}")
    all_subjects = []
    header = ["Rank", "ARN", "Name", "Date", "Time", "ZoneAbbrev", "ZoneTime", "Place", "Country", "Latitude", "Longitude", 
              "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven", "EminenceScore"]
    
    try:
        with open(args.filtered_5000, 'r', encoding='utf-8') as f:
            filtered_lines = f.readlines()
    except FileNotFoundError:
        logging.error(f"Filtered list not found: {args.filtered_5000}")
        sys.exit(1)

    subjects_not_in_chart_export = 0
    for line in filtered_lines:
        parts = line.strip().split('\t')
        rank, name_from_filter = parts[0], parts[1]
        norm_name = normalize_name(name_from_filter)

        chart_data = chart_data_map.get(norm_name)
        if not chart_data:
            subjects_not_in_chart_export += 1
            logging.warning(f"Rank {rank}: '{name_from_filter}' not found in chart export file. Skipping.")
            continue

        arn = arn_map.get(norm_name)
        if not arn:
            logging.warning(f"Could not find ARN for '{name_from_filter}'. Skipping.")
            continue

        subject_data = {
            "Rank": int(rank),
            "ARN": int(arn),
            "EminenceScore": float(eminence_scores.get(arn, 0.0)),
            **chart_data
        }
        all_subjects.append(subject_data)

    if subjects_not_in_chart_export > 0:
        logging.warning(f"A total of {subjects_not_in_chart_export} subjects from the filtered list were missing from the chart export.")
    
    # --- Write final output (no sorting needed) ---
    logging.info(f"Writing {len(all_subjects)} records to {args.output_file}...")
    try:
        with open(args.output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(all_subjects)
        logging.info("Master subject database created successfully. ✨")
    except IOError as e:
        logging.error(f"Failed to write to output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

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
# Filename: src/generate_personalities_db.py

"""
Generates the final personality database for the main experiments.

This script is the final step in the data preparation pipeline. It orchestrates
the assembly of the final `personalities_db.txt` file.

The process involves:
1.  Loading the master subject list from `data/processed/subject_db.csv`.
2.  Loading the core classification logic from `point_weights.csv` and
    `balance_thresholds.csv`.
3.  Loading the sanitized, non-esoteric description snippets from the
    `neutralized_delineations/` directory.
4.  For each subject, it calculates scores for various astrological factors
    (elements, modes, etc.), classifies them as strong or weak based on
    configurable thresholds, and looks up the corresponding text snippets.
5.  It then assembles these snippets into a single, cohesive personality
    description.
6.  The final output is a tab-delimited text file with the columns:
    `Index`, `idADB`, `Name`, `BirthYear`, `DescriptionText`.
"""

import argparse
import csv
import logging
import math
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from colorama import Fore, init

# Ensure the src directory is in the Python path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config_loader import get_path  # noqa: E402
from utils.file_utils import backup_and_remove # noqa: E402

# Initialize colorama
init(autoreset=True, strip=False)

# --- Constants based on the supplementary material ---
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ELEMENTS_MAP = {"Fire": SIGNS[0::4], "Earth": SIGNS[1::4], "Air": SIGNS[2::4], "Water": SIGNS[3::4]}
MODES_MAP = {"Cardinal": SIGNS[0::3], "Fixed": SIGNS[1::3], "Mutable": SIGNS[2::3]}
# The static QUADRANTS_MAP and HEMISPHERES_MAP have been removed as they are 
# replaced by a dynamic calculation based on the chart's angles.

logging.basicConfig(level=logging.INFO, format='%(message)s')

def load_point_weights(file_path: Path) -> dict:
    """Loads point weights from a CSV file."""
    weights = {}
    if not file_path.exists():
        logging.error(f"Point weights file not found: {file_path}")
        sys.exit(1)
    with open(file_path, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            weights[row['Point']] = int(row['Weight'])
    return weights

def load_thresholds(file_path: Path) -> dict:
    """Loads balance thresholds from a CSV file."""
    thresholds = {}
    if not file_path.exists():
        logging.error(f"Balance thresholds file not found: {file_path}")
        sys.exit(1)
    with open(file_path, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            thresholds[row['Category']] = {
                "weak_ratio": float(row['WeakRatio']),
                "strong_ratio": float(row['StrongRatio'])
            }
    return thresholds

def load_delineations(delineations_dir: Path) -> dict:
    """Loads delineations from a specific, required set of CSV files."""
    delineations = {}
    required_files = [
        "balances_elements.csv",
        "balances_modes.csv",
        "balances_hemispheres.csv",
        "balances_quadrants.csv",
        "balances_signs.csv",
        "points_in_signs.csv",
    ]

    if not delineations_dir.exists():
        logging.error(f"Delineations directory not found: {delineations_dir}")
        sys.exit(1)

    for filename in required_files:
        filepath = delineations_dir / filename
        if not filepath.exists():
            # This is a critical error in the assembly logic test.
            if os.environ.get("PROJECT_SANDBOX_PATH"):
                 logging.error(f"FATAL: Required delineation file '{filename}' not found in sandbox.")
                 sys.exit(1)
            logging.warning(f"Delineation file not found, skipping: {filepath}")
            continue

        with open(filepath, "r", encoding="utf-8") as infile:
            reader = csv.reader(infile)
            for row in reader:
                if len(row) == 2:
                    delineations[row[0]] = row[1]
    return delineations

def get_sign(longitude):
    return SIGNS[math.floor(longitude / 30)]

def calculate_classifications(placements: dict, point_weights: dict, thresholds: dict, points_to_process: list) -> list:
    
    classifications = []
    
    # --- Elements, Modes, and Signs (Zodiac-based) ---
    sign_scores = {sign: 0 for sign in SIGNS}
    for point in points_to_process:
        if point in placements:
            sign_scores[get_sign(placements[point])] += point_weights.get(point, 0)

    # --- Quadrants and Hemispheres (Angle-based) ---
    def is_between(longitude, start_angle, end_angle):
        # Handles the circular nature of the zodiac (e.g., 350 to 20 degrees)
        if start_angle < end_angle:
            return start_angle <= longitude < end_angle
        return longitude >= start_angle or longitude < end_angle

    asc = placements.get('Ascendant', 0)
    mc = placements.get('Midheaven', 0)
    ic = (mc + 180) % 360
    dsc = (asc + 180) % 360

    quadrant_scores = {"1": 0, "2": 0, "3": 0, "4": 0}
    # Per astrological rules, Quadrant/Hemisphere balances exclude the angles themselves.
    points_for_angles = [p for p in points_to_process if p not in ['Ascendant', 'Midheaven']]
    
    for point in points_for_angles:
        if point in placements:
            lon = placements[point]
            weight = point_weights.get(point, 0)
            if is_between(lon, asc, ic): quadrant_scores["1"] += weight
            elif is_between(lon, ic, dsc): quadrant_scores["2"] += weight
            elif is_between(lon, dsc, mc): quadrant_scores["3"] += weight
            elif is_between(lon, mc, asc): quadrant_scores["4"] += weight
    
    hemisphere_scores = {
        "Eastern": quadrant_scores["4"] + quadrant_scores["1"],
        "Northern": quadrant_scores["1"] + quadrant_scores["2"],
        "Western": quadrant_scores["2"] + quadrant_scores["3"],
        "Southern": quadrant_scores["3"] + quadrant_scores["4"]
    }

    # --- Combine all scores for final classification ---
    category_scores = {
        "Elements": {k: sum(sign_scores[s] for s in v) for k, v in ELEMENTS_MAP.items()},
        "Modes": {k: sum(sign_scores[s] for s in v) for k, v in MODES_MAP.items()},
        "Quadrants": quadrant_scores,
        "Hemispheres": hemisphere_scores,
        "Signs": sign_scores
    }

    for category, scores in category_scores.items():
        total_score = sum(scores.values())
        if total_score == 0: continue
        
        avg_score = total_score / len(scores)
        weak_thresh = avg_score * thresholds[category]["weak_ratio"]
        strong_thresh = avg_score * thresholds[category]["strong_ratio"]
        
        # Iterate through the dictionary items in their natural order
        for division, score in scores.items():
            if score >= strong_thresh:
                key = f"{division} Strong" if category == "Signs" else f"{category.rstrip('s')} {division} Strong"
                classifications.append(key)
            elif weak_thresh > 0 and score < weak_thresh:
                key = f"{division} Weak" if category == "Signs" else f"{category.rstrip('s')} {division} Weak"
                classifications.append(key)

    # --- Append Point in Sign classifications at the end ---
    for point in points_to_process:
        if point in placements:
            sign = get_sign(placements[point])
            classifications.append(f"{point} in {sign}")

    return classifications

from config_loader import APP_CONFIG, get_config_value

def main():
    parser = argparse.ArgumentParser(description="Generate final personalities DB.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--sandbox-path",
        type=str,
        help="Path to the sandbox directory for testing.",
    )
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file if it exists.")
    parser.add_argument("--test-record-number", type=int, help="Run for a single record number for focused testing.")
    parser.add_argument("-o", "--output", help="Path to the output personalities database file.")
    args = parser.parse_args()

    if args.sandbox_path:
        os.environ["PROJECT_SANDBOX_PATH"] = args.sandbox_path

    subject_db_path = Path(get_path("data/processed/subject_db.csv"))
    delineations_dir = Path(get_path("data/foundational_assets/neutralized_delineations"))
    output_path = Path(get_path("data/personalities_db.txt"))

    # Define all configuration and data input files for the stale check
    point_weights_path = Path(get_path("data/foundational_assets/point_weights.csv"))
    thresholds_path = Path(get_path("data/foundational_assets/balance_thresholds.csv"))
    
    input_files = [subject_db_path, point_weights_path, thresholds_path]
    if delineations_dir.exists():
        input_files.extend(delineations_dir.glob("*.csv"))

    # --- Intelligent Startup Logic ---
    is_stale = False
    if not args.force and output_path.exists():
        output_mtime = os.path.getmtime(output_path)
        is_stale = any(p.exists() and os.path.getmtime(p) > output_mtime for p in input_files)

        if is_stale:
            print(f"{Fore.YELLOW}\nInput file(s) are newer than the existing output. Stale data detected.")
            print("Automatically re-running database generation...")
            args.force = True

    if not args.force and output_path.exists() and not is_stale:
        print(f"\n{Fore.YELLOW}WARNING: The database at '{output_path}' is already up to date. ✨")
        print(f"{Fore.YELLOW}If you decide to go ahead with the update, a backup of the existing file will be created first.{Fore.RESET}")
        confirm = input("Do you wish to proceed? (Y/N): ").lower().strip()
        if confirm == 'y':
            args.force = True
        else:
            print(f"\n{Fore.YELLOW}Operation cancelled by user.{Fore.RESET}\n")
            sys.exit(0)

    if args.force and output_path.exists():
        backup_and_remove(output_path)

    print("\nLoading configuration and delineation files...")
    point_weights = load_point_weights(point_weights_path)
    thresholds = load_thresholds(thresholds_path)
    delineations = load_delineations(delineations_dir)

    # This debug checkpoint is no longer needed and has been removed.

    print(f"Processing subjects from {subject_db_path.name}...")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(
                outfile,
                delimiter='\t',
                quoting=csv.QUOTE_MINIMAL,
                quotechar='|' # An unlikely character
            )
            writer.writerow(['Index', 'idADB', 'Name', 'BirthYear', 'DescriptionText'])
            
            with open(subject_db_path, 'r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                # Load the list of points to process from the config file.
                points_str = get_config_value(
                    APP_CONFIG, "DataGeneration", "points_for_neutralization"
                )
                points_to_process = [p.strip() for p in points_str.split(',')]
                
                # If a test record number is specified, filter the reader
                all_rows = list(reader)
                if args.test_record_number is not None:
                    # Find the specific row by its 1-based record number in the sorted list
                    if 1 <= args.test_record_number <= len(all_rows):
                         # Map the 1-based record number to the 0-based list index
                        row_to_process = all_rows[args.test_record_number - 1]
                        rows_to_process = [row_to_process]
                    else:
                        rows_to_process = []
                else:
                    rows_to_process = all_rows

                for row in rows_to_process:
                    placements = {p: float(row[p]) for p in points_to_process if row.get(p)}
                    classifications = calculate_classifications(placements, point_weights, thresholds, points_to_process)
                    desc_parts = [delineations.get(c, "") for c in classifications]

                    # --- UNIFIED DEBUG CHECKPOINT ---
                    # In test mode, always print the details for the selected subject.
                    if args.test_record_number is not None:
                        print(f"\n--- DEBUG: Processing Subject: {row['Name']} ---")
                        print("--- DEBUG: Key Generation & Text Snippet Assembly ---")
                        print("Classifications generated and their corresponding text snippets:")
                        for i, key in enumerate(classifications):
                            part = desc_parts[i]
                            snippet = (part[:70] + '..') if len(part) > 70 else part
                            print(f"  {i+1:2d}. Key: {repr(key):<28} -> Snippet: '{snippet}'")
                        print("-----------------------------------------------------------------")
                        sys.stdout.flush()

                    # Standardize joining: join all parts, normalize characters,
                    # and then normalize all internal whitespace to a single space.
                    raw_desc = " ".join(part for part in desc_parts if part)
                    normalized_desc = raw_desc.replace("’", "'") # Normalize apostrophes
                    full_desc = " ".join(normalized_desc.split()).strip()
                    
                    # Extract year correctly, handling different date formats
                    year_match = re.search(r'\b(\d{4})\b', row['Date'])
                    birth_year = year_match.group(1) if year_match else row['Date']
                    
                    writer.writerow([row['Index'], row['idADB'], row['Name'], birth_year, full_desc])
        
        # Count the number of records processed
        with open(subject_db_path, 'r', encoding='utf-8') as infile:
            num_records = sum(1 for line in infile) - 1 # Subtract header
        
        from config_loader import PROJECT_ROOT

        # Determine display path (relative to project root if possible)
        try:
            display_path = output_path.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = output_path  # Fallback to absolute if not in project
            
        # Standardize path separators for consistent output
        display_path = str(display_path).replace('\\', '/')

        print(f"\n{Fore.YELLOW}--- Final Output ---")
        print(f"{Fore.CYAN} - Personalities database saved to: {display_path}{Fore.RESET}")
        key_metric = f"Final Count: {num_records} subjects"
        print(
            f"\n{Fore.GREEN}SUCCESS: {key_metric}. Personalities database "
            f"created successfully.\n"
        )

    except KeyError as e:
        logging.error(f"Missing column {e} in '{subject_db_path}'. Please ensure the file is correctly formatted.\n")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred during database generation: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/generate_personalities_db.py ===

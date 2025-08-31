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

# Initialize colorama
init(autoreset=True)

# --- Constants based on the supplementary material ---
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ELEMENTS_MAP = {"Fire": SIGNS[0::4], "Earth": SIGNS[1::4], "Air": SIGNS[2::4], "Water": SIGNS[3::4]}
MODES_MAP = {"Cardinal": SIGNS[0::3], "Fixed": SIGNS[1::3], "Mutable": SIGNS[2::3]}
QUADRANTS_MAP = {"1": SIGNS[0:3], "2": SIGNS[3:6], "3": SIGNS[6:9], "4": SIGNS[9:12]}
HEMISPHERES_MAP = {"Eastern": SIGNS[9:12] + SIGNS[0:3], "Western": SIGNS[3:9], "Northern": SIGNS[0:6], "Southern": SIGNS[6:12]}

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
    delineations = {}
    if not delineations_dir.exists():
        logging.error(f"Delineations directory not found: {delineations_dir}")
        sys.exit(1)
    for f in delineations_dir.glob("*.csv"):
        with open(f, 'r', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            for row in reader:
                if len(row) == 2:
                    delineations[row[0]] = row[1]
    return delineations

def get_sign(longitude):
    return SIGNS[math.floor(longitude / 30)]

def calculate_classifications(placements: dict, point_weights: dict, thresholds: dict) -> list:
    points_for_balances = list(point_weights.keys())
    points_for_quad_hemi = [p for p in points_for_balances if p not in ['Ascendant', 'Midheaven']]
    
    classifications = []
    for point, lon in placements.items():
        # All 12 points get a "Point in Sign" delineation, regardless of their weight.
        sign = get_sign(lon)
        classifications.append(f"{point} in {sign}")

    def get_category_scores(use_all_points=True):
        points_to_consider = points_for_balances if use_all_points else points_for_quad_hemi
        scores = {sign: 0 for sign in SIGNS}
        for point, lon in placements.items():
            if point in points_to_consider:
                scores[get_sign(lon)] += point_weights.get(point, 0)
        return scores

    sign_scores_all = get_category_scores(True)
    sign_scores_no_angles = get_category_scores(False)

    category_scores = {
        "Signs": sign_scores_all,
        "Elements": {k: sum(sign_scores_all[s] for s in v) for k, v in ELEMENTS_MAP.items()},
        "Modes": {k: sum(sign_scores_all[s] for s in v) for k, v in MODES_MAP.items()},
        "Quadrants": {k: sum(sign_scores_no_angles[s] for s in v) for k, v in QUADRANTS_MAP.items()},
        "Hemispheres": {k: sum(sign_scores_no_angles[s] for s in v) for k, v in HEMISPHERES_MAP.items()}
    }

    for category, scores in category_scores.items():
        total_score = sum(scores.values())
        if total_score == 0: continue
        avg_score = total_score / len(scores)
        weak_thresh = avg_score * thresholds[category]["weak_ratio"]
        strong_thresh = avg_score * thresholds[category]["strong_ratio"]
        for division, score in scores.items():
            # Correctly format the key to match the delineation library's structure.
            if weak_thresh > 0 and score < weak_thresh:
                if category == "Signs":
                    classifications.append(f"{division} Weak")
                else:
                    classifications.append(f"{category.rstrip('s')} Weak {division}")
            
            if score >= strong_thresh:
                if category == "Signs":
                    classifications.append(f"{division} Strong")
                else:
                    classifications.append(f"{category.rstrip('s')} Strong {division}")
    return classifications

def main():
    parser = argparse.ArgumentParser(description="Generate final personalities DB.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--sandbox-path",
        type=str,
        help="Path to the sandbox directory for testing.",
    )
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file if it exists.")
    args = parser.parse_args()

    if args.sandbox_path:
        os.environ["PROJECT_SANDBOX_PATH"] = args.sandbox_path

    subject_db_path = Path(get_path("data/processed/subject_db.csv"))
    delineations_dir = Path(get_path("data/foundational_assets/neutralized_delineations"))
    output_path = Path(get_path("personalities_db.txt"))

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
        try:
            backup_dir = Path(get_path('data/backup'))
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{output_path.stem}.{timestamp}{output_path.suffix}.bak"
            shutil.copy2(output_path, backup_path)
            print(f"{Fore.CYAN}Created backup of existing file at: {backup_path}{Fore.RESET}")
        except (IOError, OSError) as e:
            logging.error(f"{Fore.RED}Failed to create backup file: {e}")
            sys.exit(1)

    print("\nLoading configuration and delineation files...")
    point_weights = load_point_weights(point_weights_path)
    thresholds = load_thresholds(thresholds_path)
    delineations = load_delineations(delineations_dir)

    print(f"Processing subjects from {subject_db_path.name}...")
    try:
        with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile, delimiter='\t')
            writer.writerow(['Index', 'idADB', 'Name', 'BirthYear', 'DescriptionText'])
            
            with open(subject_db_path, 'r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                # Define the 12 points to ensure Uranus, Neptune, and Pluto are always included.
                points_to_process = [
                    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", 
                    "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven"
                ]
                for row in reader:
                    placements = {p: float(row[p]) for p in points_to_process if row.get(p)}
                    classifications = calculate_classifications(placements, point_weights, thresholds)
                    desc_parts = [delineations.get(c, "") for c in classifications]
                    full_desc = " ".join(part for part in desc_parts if part).strip()
                    
                    # Extract year correctly, handling different date formats
                    year_match = re.search(r'\b(\d{4})\b', row['Date'])
                    birth_year = year_match.group(1) if year_match else row['Date']
                    
                    writer.writerow([row['Index'], row['idADB'], row['Name'], birth_year, full_desc])
        
        # Count the number of records processed
        with open(subject_db_path, 'r', encoding='utf-8') as infile:
            num_records = sum(1 for line in infile) - 1 # Subtract header
        
        print(f"\n{Fore.YELLOW}--- Final Output ---")
        print(f"{Fore.CYAN} - Personalities database saved to: {output_path}")
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

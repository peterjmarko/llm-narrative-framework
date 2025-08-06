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
Generates the final personality database from a pre-processed master file.

This script is the final step in the data preparation pipeline. It reads the
clean, flattened `subject_db.csv` and a library of neutralized delineations.
For each person, it calculates scores for astrological factors, classifies them,
and assembles a sanitized personality description. The final output is the
`personalities_db.txt` file used in the main experiments.
"""

import argparse
import csv
import logging
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path

# --- Constants based on the supplementary material ---
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ELEMENTS_MAP = {"Fire": SIGNS[0::4], "Earth": SIGNS[1::4], "Air": SIGNS[2::4], "Water": SIGNS[3::4]}
MODES_MAP = {"Cardinal": SIGNS[0::3], "Fixed": SIGNS[1::3], "Mutable": SIGNS[2::3]}
QUADRANTS_MAP = {"1": SIGNS[0:3], "2": SIGNS[3:6], "3": SIGNS[6:9], "4": SIGNS[9:12]}
HEMISPHERES_MAP = {"Eastern": SIGNS[9:12] + SIGNS[0:3], "Western": SIGNS[3:9], "Northern": SIGNS[0:6], "Southern": SIGNS[6:12]}

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class bcolors:
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

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
        if point_weights.get(point, 0) > 0:
            sign = get_sign(lon)
            classifications.append(f"{point} In {sign}")

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
            key_name = f"{category.rstrip('s')} {division}" if category != "Signs" else division
            if weak_thresh > 0 and score < weak_thresh:
                classifications.append(f"{key_name} Weak")
            if score >= strong_thresh:
                classifications.append(f"{key_name} Strong")
    return classifications

def main():
    parser = argparse.ArgumentParser(description="Generate final personalities DB.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--subject-db", default="data/processed/subject_db.csv", help="Path to the master subject database CSV.")
    parser.add_argument("--delineations-dir", default="data/foundational_assets/neutralized_delineations", help="Directory with neutralized delineation CSVs.")
    parser.add_argument("--output-file", default="data/personalities_db.txt", help="Path for the final output database.")
    args = parser.parse_args()

    output_path = Path(args.output_file)
    backup_dir = output_path.parent / 'backup'

    # Check if output file exists and prompt user to overwrite
    if output_path.exists():
        print("")
        print(f"{bcolors.WARNING}WARNING: The output file '{output_path}' already exists and will be overwritten.{bcolors.ENDC}")
        confirm = input("Do you want to continue? (Y/N): ").lower().strip()
        if confirm != 'y':
            print("")
            logging.info("Operation cancelled by user.\n")
            sys.exit(0)

        # Create backup directory if it doesn't exist
        backup_dir.mkdir(exist_ok=True)

        # Create timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{output_path.stem}_backup_{timestamp}{output_path.suffix}"
        backup_path = backup_dir / backup_filename
        
        shutil.copy2(output_path, backup_path)
        print("")
        logging.info(f"Backup of existing file created at: {backup_path}")

    data_dir = Path(args.output_file).parent
    point_weights_path = data_dir / "foundational_assets" / "point_weights.csv"
    thresholds_path = data_dir / "foundational_assets" / "balance_thresholds.csv"

    logging.info("Loading configuration and delineation files...")
    point_weights = load_point_weights(point_weights_path)
    thresholds = load_thresholds(thresholds_path)
    delineations = load_delineations(Path(args.delineations_dir))

    logging.info(f"Processing subjects from {args.subject_db}...")
    try:
        with open(args.output_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile, delimiter='\t')
            writer.writerow(['Index', 'Name', 'BirthYear', 'DescriptionText'])
            
            with open(args.subject_db, 'r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    placements = {p: float(row[p]) for p in point_weights if row.get(p)}
                    classifications = calculate_classifications(placements, point_weights, thresholds)
                    desc_parts = [delineations.get(c, "") for c in classifications]
                    full_desc = " ".join(part for part in desc_parts if part).strip()
                    writer.writerow([row['Rank'], row['Name'], row['Date'].split()[-1], full_desc])
        
        print("")
        print(f"{bcolors.OKGREEN}INFO: Database generation complete. Final file at: {args.output_file} ✨{bcolors.ENDC}")
        print("")

    except Exception as e:
        import traceback
        print("")
        print(f"{bcolors.FAIL}ERROR: An error occurred during database generation.{bcolors.ENDC}")
        print(f"{bcolors.FAIL}{e}{bcolors.ENDC}\n")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/generate_personalities_db.py ===

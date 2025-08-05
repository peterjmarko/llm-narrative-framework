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
# Filename: src/generate_database.py

"""
Generates the final personality database from processed astrological data.

This script is the final step in the data preparation pipeline. It takes the
chart export from third-party software (`sf_chart_export.csv`) and a library
of neutralized delineations. For each person, it calculates scores for
astrological factors (e.g., elemental balances, modes), classifies them, and
uses these classifications to assemble a sanitized, narrative personality
description from the delineation library. The final output is the
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

class BColors:
    """A helper class for terminal colors."""
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'

# --- Constants based on the supplementary material ---
POINT_WEIGHTS = {
    "Sun": 3, "Moon": 3, "Ascendant": 3, "Midheaven": 3,
    "Mercury": 2, "Venus": 2, "Mars": 2,
    "Jupiter": 1, "Saturn": 1,
    "Uranus": 0, "Neptune": 0, "Pluto": 0
}
POINTS_FOR_BALANCES = list(POINT_WEIGHTS.keys())
POINTS_FOR_QUAD_HEMI = [p for p in POINTS_FOR_BALANCES if p not in ['Ascendant', 'Midheaven']]

THRESHOLDS = {
    "Signs": {"weak_ratio": 0, "strong_ratio": 2.0},
    "Elements": {"weak_ratio": 0.5, "strong_ratio": 1.5},
    "Modes": {"weak_ratio": 0.5, "strong_ratio": 1.5},
    "Quadrants": {"weak_ratio": 0, "strong_ratio": 1.5},
    "Hemispheres": {"weak_ratio": 0, "strong_ratio": 1.4}
}

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ELEMENTS_MAP = {"Fire": ["Aries", "Leo", "Sagittarius"], "Earth": ["Taurus", "Virgo", "Capricorn"], "Air": ["Gemini", "Libra", "Aquarius"], "Water": ["Cancer", "Scorpio", "Pisces"]}
MODES_MAP = {"Cardinal": ["Aries", "Cancer", "Libra", "Capricorn"], "Fixed": ["Taurus", "Leo", "Scorpio", "Aquarius"], "Mutable": ["Gemini", "Virgo", "Sagittarius", "Pisces"]}
QUADRANTS_MAP = {"1": SIGNS[0:3], "2": SIGNS[3:6], "3": SIGNS[6:9], "4": SIGNS[9:12]}
HEMISPHERES_MAP = {"Eastern": SIGNS[0:3] + SIGNS[9:12], "Western": SIGNS[3:9], "Northern": SIGNS[0:6], "Southern": SIGNS[6:12]}


# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- Helper Functions ---
def load_delineations(delineations_dir: Path) -> dict:
    """Loads all neutralized delineation text from CSV files."""
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
    """Determines the zodiac sign for a given longitude."""
    return SIGNS[math.floor(longitude / 30)]

def parse_chart_data(filepath):
    """Parses the 14-line blocks from sf_chart_export.csv using a generator."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f]
    except FileNotFoundError:
        logging.error(f"Chart export file not found: {filepath}")
        sys.exit(1)

    for i in range(0, len(lines), 14):
        block = lines[i:i+14]
        if len(block) < 14:
            continue

        person_data = {}
        person_info = next(csv.reader([block[0]]))
        person_data['name'] = person_info[0]
        person_data['birth_year'] = person_info[1].split()[-1]

        longitudes = {}
        for line in block[2:]:
            point_info = next(csv.reader([line]))
            point_name = point_info[0]
            if point_name in POINT_WEIGHTS:
                longitudes[point_name] = float(point_info[2])
        person_data['longitudes'] = longitudes
        yield person_data

def calculate_classifications(longitudes: dict) -> list:
    """Calculates all 'strong'/'weak' classifications for a single person."""
    classifications = []

    # 1. Direct "Point in Sign" classifications
    for point, lon in longitudes.items():
        if POINT_WEIGHTS.get(point, 0) > 0:
            sign = get_sign(lon)
            classifications.append(f"*{point} In {sign}")

    # 2. Calculate scores for all categories
    def get_category_scores(use_all_points=True):
        points_to_consider = POINTS_FOR_BALANCES if use_all_points else POINTS_FOR_QUAD_HEMI
        scores = {sign: 0 for sign in SIGNS}
        for point, lon in longitudes.items():
            if point in points_to_consider:
                sign = get_sign(lon)
                scores[sign] += POINT_WEIGHTS.get(point, 0)
        return scores

    sign_scores_all = get_category_scores(use_all_points=True)
    sign_scores_no_angles = get_category_scores(use_all_points=False)

    category_scores = {
        "Signs": sign_scores_all,
        "Elements": {k: sum(sign_scores_all[s] for s in v) for k, v in ELEMENTS_MAP.items()},
        "Modes": {k: sum(sign_scores_all[s] for s in v) for k, v in MODES_MAP.items()},
        "Quadrants": {k: sum(sign_scores_no_angles[s] for s in v) for k, v in QUADRANTS_MAP.items()},
        "Hemispheres": {k: sum(sign_scores_no_angles[s] for s in v) for k, v in HEMISPHERES_MAP.items()}
    }

    # 3. Apply thresholds to get final weak/strong classifications
    for category, scores in category_scores.items():
        total_score = sum(scores.values())
        if total_score == 0: continue
        
        avg_score = total_score / len(scores)
        weak_thresh = avg_score * THRESHOLDS[category]["weak_ratio"]
        strong_thresh = avg_score * THRESHOLDS[category]["strong_ratio"]
        
        for division, score in scores.items():
            key_name = f"{category.rstrip('s')} {division}" if category != "Signs" else division
            if weak_thresh > 0 and score < weak_thresh:
                classifications.append(f"*{key_name} Weak")
            if score >= strong_thresh:
                classifications.append(f"*{key_name} Strong")
                
    return classifications

def main():
    """Main function to generate the personalities database."""
    parser = argparse.ArgumentParser(description="Generate the final personalities database from Solar Fire exports.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--chart-export", default="data/sources/sf_chart_export.csv", help="Path to the chart data exported from Solar Fire.")
    parser.add_argument("--delineations-dir", default="data/neutralized_delineations", help="Directory containing the neutralized delineation CSV files.")
    parser.add_argument("--output-file", default="data/personalities_db.txt", help="Path for the final output database.")
    args = parser.parse_args()

    print("")
    output_path = Path(args.output_file)
    if output_path.exists():
        print(f"{BColors.YELLOW}WARNING: The output file '{output_path}' already exists and will be overwritten.{BColors.ENDC}")
        confirm = input("Are you sure you want to continue? (y/n): ").lower()
        if confirm != 'y':
            print("Operation cancelled by user.")
            sys.exit(0)
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = output_path.with_name(f"{output_path.stem}.{timestamp}{output_path.suffix}.bak")
            shutil.copy2(output_path, backup_path)
            logging.info(f"Created backup of existing file at: {backup_path}")
        except (IOError, OSError) as e:
            logging.error(f"Failed to create backup file: {e}")
            sys.exit(1)

    logging.info("Loading neutralized delineations...")
    delineations = load_delineations(Path(args.delineations_dir))

    logging.info(f"Processing chart data from {args.chart_export}...")
    try:
        with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile, delimiter='\t')
            # No header for the final db file
            
            idx = 0
            for person in parse_chart_data(args.chart_export):
                idx += 1
                classifications = calculate_classifications(person['longitudes'])
                
                desc_parts = [delineations.get(c, "") for c in classifications]
                full_desc = " ".join(part for part in desc_parts if part).strip()

                writer.writerow([idx, person['name'], person['birth_year'], full_desc])
        
        print(f"{BColors.GREEN}Successfully generated {output_path} with {idx} entries.{BColors.ENDC}")
        print("")

    except Exception as e:
        print(f"{BColors.RED}An error occurred during database generation: {e}{BColors.ENDC}")
        print("")
        sys.exit(1)

if __name__ == "__main__":
    main()

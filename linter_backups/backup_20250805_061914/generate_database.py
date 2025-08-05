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
import sys
from pathlib import Path

# --- Constants based on the supplementary material ---
POINT_WEIGHTS = {"Sun": 3, "Moon": 3, "Ascendant": 3, "Midheaven": 3, "Mercury": 2, "Venus": 2, "Mars": 2, "Jupiter": 1, "Saturn": 1, "Uranus": 0, "Neptune": 0, "Pluto": 0}
POINTS_FOR_BALANCES = list(POINT_WEIGHTS.keys())
POINTS_FOR_QUAD_HEMI = [p for p in POINTS_FOR_BALANCES if p not in ['Ascendant', 'Midheaven']]
THRESHOLDS = {"Signs": {"weak_ratio": 0, "strong_ratio": 2.0}, "Elements": {"weak_ratio": 0.5, "strong_ratio": 1.5}, "Modes": {"weak_ratio": 0.5, "strong_ratio": 1.5}, "Quadrants": {"weak_ratio": 0, "strong_ratio": 1.5}, "Hemispheres": {"weak_ratio": 0, "strong_ratio": 1.4}}
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ELEMENTS_MAP = {"Fire": SIGNS[0::4], "Earth": SIGNS[1::4], "Air": SIGNS[2::4], "Water": SIGNS[3::4]}
MODES_MAP = {"Cardinal": SIGNS[0::3], "Fixed": SIGNS[1::3], "Mutable": SIGNS[2::3]}
QUADRANTS_MAP = {"1": SIGNS[0:3], "2": SIGNS[3:6], "3": SIGNS[6:9], "4": SIGNS[9:12]}
HEMISPHERES_MAP = {"Eastern": SIGNS[9:12] + SIGNS[0:3], "Western": SIGNS[3:9], "Northern": SIGNS[0:6], "Southern": SIGNS[6:12]}

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

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

def calculate_classifications(placements: dict) -> list:
    classifications = []
    for point, lon in placements.items():
        if POINT_WEIGHTS.get(point, 0) > 0:
            sign = get_sign(lon)
            classifications.append(f"*{point} In {sign}")

    def get_category_scores(use_all_points=True):
        points_to_consider = POINTS_FOR_BALANCES if use_all_points else POINTS_FOR_QUAD_HEMI
        scores = {sign: 0 for sign in SIGNS}
        for point, lon in placements.items():
            if point in points_to_consider:
                scores[get_sign(lon)] += POINT_WEIGHTS.get(point, 0)
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
    parser = argparse.ArgumentParser(description="Generate final personalities DB.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--subject-db", default="data/subject_db.csv", help="Path to the master subject database CSV.")
    parser.add_argument("--delineations-dir", default="data/neutralized_delineations", help="Directory with neutralized delineation CSVs.")
    parser.add_argument("--output-file", default="data/personalities_db.txt", help="Path for the final output database.")
    args = parser.parse_args()

    logging.info("Loading neutralized delineations...")
    delineations = load_delineations(Path(args.delineations_dir))

    logging.info(f"Processing subjects from {args.subject_db}...")
    try:
        with open(args.output_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile, delimiter='\t')
            
            with open(args.subject_db, 'r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    placements = {p: float(row[p]) for p in POINT_WEIGHTS if row.get(p)}
                    classifications = calculate_classifications(placements)
                    desc_parts = [delineations.get(c, "") for c in classifications]
                    full_desc = " ".join(part for part in desc_parts if part).strip()
                    writer.writerow([row['Rank'], row['Name'], row['Date'].split()[-1], full_desc])
        
        logging.info(f"Database generation complete. Final file at: {args.output_file} ✨")

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
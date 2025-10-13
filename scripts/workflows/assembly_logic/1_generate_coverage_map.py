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
# Filename: scripts/workflows/assembly_logic/1_generate_coverage_map.py

"""
Generates a map of which delineation keys each subject triggers.

This utility script processes the full subject database and, for each person,
calculates the complete list of delineation keys their astrological placements
would trigger in the final assembly script.

The output is a CSV file that serves as a pre-computed lookup table, which
is essential for algorithmically selecting a minimal "gold standard" set
of subjects that provides maximum coverage of all delineation components.
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

from colorama import Fore
from tqdm import tqdm

# Add the 'src' directory to the Python path to allow for module imports
sys.path.append(str(Path(__file__).resolve().parents[3]))

from generate_personalities_db import (  # noqa: E402
    calculate_classifications,
    load_point_weights,
    load_thresholds,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    """Main function to generate the delineation coverage map."""
    parser = argparse.ArgumentParser(
        description="Generate a map of delineation key coverage for each subject."
    )
    parser.add_argument(
        "--subject-db",
        default=None,
        help="Path to the master subject database.",
    )
    parser.add_argument(
        "--point-weights",
        default="data/foundational_assets/point_weights.csv",
        help="Path to the point weights configuration file.",
    )
    parser.add_argument(
        "--thresholds",
        default="data/foundational_assets/balance_thresholds.csv",
        help="Path to the balance thresholds configuration file.",
    )
    parser.add_argument(
        "-o",
        "--output-file",
        default="data/reports/delineation_coverage_map.csv",
        help="Path to write the output coverage map CSV.",
    )
    args = parser.parse_args()

    # --- Load all necessary configuration and data files ---
    print(f"\n{Fore.YELLOW}--- Generating Delineation Coverage Map ---{Fore.RESET}")
    print("\nLoading configuration and subject data...")

    # Determine subject DB path: use test asset if it exists, otherwise use production path
    subject_db_path = args.subject_db
    if not subject_db_path:
        test_prereq_path = Path("tests/assets/assembly_logic/prerequisites/subject_db.csv")
        prod_path = Path("data/processed/subject_db.csv")
        if test_prereq_path.exists():
            subject_db_path = test_prereq_path
        else:
            subject_db_path = prod_path
    
    logging.info(f"Reading subject data from: {subject_db_path}")
    point_weights = load_point_weights(Path(args.point_weights))
    thresholds = load_thresholds(Path(args.thresholds))

    try:
        with open(subject_db_path, "r", encoding="utf-8") as f:
            subjects = list(csv.DictReader(f))
    except FileNotFoundError:
        logging.error(
            f"\n{Fore.RED}FAILURE: Subject database not found at: "
            f"{args.subject_db}{Fore.RESET}\n"
        )
        sys.exit(1)

    # --- Process each subject and generate the map ---
    print(f"Processing {len(subjects):,} subjects to generate coverage map...")
    coverage_map = []
    from config_loader import APP_CONFIG, get_config_value
    points_str = get_config_value(
        APP_CONFIG, "DataGeneration", "points_for_neutralization"
    )
    points_to_check = [p.strip() for p in points_str.split(',')]

    for i, subject in enumerate(
        tqdm(subjects, desc="Mapping Delineations", ncols=80)
    ):
        placements = {
            p: float(subject[p]) for p in points_to_check if subject.get(p)
        }
        if not placements:
            continue

        triggered_keys = calculate_classifications(
            placements, point_weights, thresholds, points_to_check
        )
        coverage_map.append(
            {
                "Index": i + 1,
                "idADB": subject["idADB"],
                "TriggeredKeys": ";".join(sorted(triggered_keys)),
            }
        )

    # --- Write the final output file ---
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["Index", "idADB", "TriggeredKeys"]
            )
            writer.writeheader()
            writer.writerows(coverage_map)

        print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
        print(f"{Fore.CYAN} - Coverage map saved to: {output_path}{Fore.RESET}")
        key_metric = f"Mapped {len(coverage_map)} subjects"
        print(
            f"\n{Fore.GREEN}SUCCESS: {key_metric}. Coverage map generation "
            f"completed successfully.{Fore.RESET}\n"
        )
    except IOError as e:
        logging.error(
            f"\n{Fore.RED}FAILURE: Failed to write output file: {e}{Fore.RESET}\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

# === End of scripts/workflows/assembly_logic/1_generate_coverage_map.py ===

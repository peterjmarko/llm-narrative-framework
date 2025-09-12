#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
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
# Filename: scripts/workflows/assembly_logic/2_select_assembly_logic_subjects.py

"""
Selects an optimal, minimal set of subjects for the assembly logic test.

This utility script uses a greedy algorithm to create the smallest possible
"assembly logic" subject set that provides the maximum achievable coverage of all
delineation components.

It works by iteratively selecting the subject who adds the most new, previously
uncovered delineation keys to the set, stopping when a full pass through all
remaining subjects adds no new keys.

The final output is the `subject_db.gold_standard.csv` file, which will be
used for manual processing in Solar Fire, and a `coverage_report.txt` that
documents the final coverage statistics.
"""

import argparse
import csv
import logging
import re
import shutil
import sys
from pathlib import Path

from colorama import Fore
from tqdm import tqdm

# Add the 'src' directory to the Python path to allow for module imports
sys.path.append(str(Path(__file__).resolve().parents[3] / "src"))

from neutralize_delineations import parse_llm_response  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    """Main function to select the assembly logic test subjects."""
    parser = argparse.ArgumentParser(
        description="Select an optimal set of subjects for assembly logic testing."
    )
    parser.add_argument(
        "--coverage-map",
        default="data/reports/delineation_coverage_map.csv",
        help="Path to the pre-computed delineation coverage map.",
    )
    parser.add_argument(
        "--delineation-library",
        default="data/foundational_assets/sf_delineations_library.txt",
        help="Path to the original Solar Fire delineation library.",
    )
    parser.add_argument(
        "--subject-db",
        default="data/processed/subject_db.csv",
        help="Path to the full master subject database.",
    )
    args = parser.parse_args()

    print(f"\n{Fore.YELLOW}--- Selecting Assembly Logic Subjects ---{Fore.RESET}")
    
    # --- Setup the sandbox environment ---
    sandbox_dir = Path("temp_assembly_logic_validation")
    print(f"\nCreating clean sandbox at: {sandbox_dir.resolve()}")
    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir)
    
    # Define output paths within the sandbox, mirroring the project structure
    output_path = sandbox_dir / "data/processed/subject_db.assembly_logic.csv"
    report_path = sandbox_dir / "data/reports/assembly_logic_coverage_report.txt"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Load all necessary input files ---
    print("\nLoading input files...")
    logging.info(f"Reading coverage map from: {args.coverage_map}")
    logging.info(f"Reading delineation library from: {args.delineation_library}")
    logging.info(f"Reading subject database from: {args.subject_db}")
    try:
        # Load all keys, then filter them to match our specific assembly logic.
        all_source_keys = set(
            parse_llm_response(Path(args.delineation_library)).keys()
        )
        
        # Define the patterns for keys that are actually used in our algorithm
        # Define the exact lists of signs and points used in our algorithm
        signs = "(Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces)"
        points = "(Sun|Moon|Mercury|Venus|Mars|Jupiter|Saturn|Uranus|Neptune|Pluto|Ascendant|Midheaven)"

        valid_patterns = [
            r"^Quadrant (?:Strong|Weak) [1-4]$",
            r"^Hemisphere (?:Strong|Weak) (?:East|West|North|South)$",
            r"^Element (?:Strong|Weak) (?:Fire|Earth|Air|Water)$",
            r"^Mode (?:Strong|Weak) (?:Cardinal|Fixed|Mutable)$",
            r"^\w+ Strong$",  # Correctly matches "Aries Strong", etc.
            rf"^{points} in {signs}$",
        ]
        
        all_possible_keys = {
            key for key in all_source_keys 
            if any(re.match(pattern, key) for pattern in valid_patterns)
        }

        with open(args.coverage_map, "r", encoding="utf-8") as f:
            coverage_map = {
                row["idADB"]: set(row["TriggeredKeys"].split(";"))
                for row in csv.DictReader(f)
            }
        with open(args.subject_db, "r", encoding="utf-8") as f:
            full_subject_db = {row["idADB"]: row for row in csv.DictReader(f)}
    except FileNotFoundError as e:
        logging.error(f"Input file not found: {e.filename}")
        sys.exit(1)

    # --- Iteratively select subjects using a greedy algorithm ---
    print("Running greedy algorithm to find optimal subject set...")
    selected_subject_ids = []
    covered_keys = set()

    coverage_threshold = 0.95
    target_coverage_count = int(len(all_possible_keys) * coverage_threshold)

    # Create the set of all keys that are actually achievable in our dataset
    all_achievable_keys = set()
    for key_set in coverage_map.values():
        all_achievable_keys.update(key_set)
    
    # The true total for our progress bar and percentages is the achievable set
    total_keys_to_cover = len(all_achievable_keys)
    if total_keys_to_cover == 0:
        print(f"{Fore.YELLOW}Warning: No achievable keys found in the coverage map.{Fore.RESET}")
        sys.exit(0)

    # Set the target coverage to 100% of all achievable keys.
    coverage_threshold_percent = 100
    target_coverage_count = int(
        total_keys_to_cover * (coverage_threshold_percent / 100.0)
    )

    with tqdm(total=total_keys_to_cover, desc="Coverage", ncols=80) as pbar:
        while len(covered_keys) < target_coverage_count:
            best_candidate_id = None
            best_candidate_new_keys = set()

            # Find the subject who adds the most new keys in this pass
            for subject_id in list(coverage_map.keys()):
                keys = coverage_map[subject_id]
                new_keys = keys - covered_keys
                if len(new_keys) > len(best_candidate_new_keys):
                    best_candidate_id = subject_id
                    best_candidate_new_keys = new_keys

            # If a full pass adds no new keys, we have reached maximum possible coverage.
            if not best_candidate_id or not best_candidate_new_keys:
                tqdm.write(f"{Fore.YELLOW}Warning: Maximum possible coverage reached before hitting the 95% target.{Fore.RESET}")
                
                # --- START DEBUG BLOCK ---
                print("\n--- DEBUG: Why did the loop stop? ---")
                uncovered_keys = all_possible_keys - covered_keys
                print(f"There are {len(uncovered_keys)} keys left to cover.")
                
                found_a_match = False
                for subject_id, keys in coverage_map.items():
                    if not uncovered_keys.isdisjoint(keys):
                        print(f"ERROR: Subject {subject_id} could have covered a key, but was missed.")
                        found_a_match = True
                        break # Only need to find one to prove the bug
                
                if not found_a_match:
                    print("CONFIRMED: No remaining subject in the coverage map can cover any of the remaining keys.")
                print("--- END DEBUG BLOCK ---\n")
                # --- END DEBUG BLOCK ---

                break

            # Add the best candidate to our set
            selected_subject_ids.append(best_candidate_id)
            newly_covered_count = len(best_candidate_new_keys)
            covered_keys.update(best_candidate_new_keys)
            pbar.update(newly_covered_count)
            tqdm.write(
                f" -> Selected subject {best_candidate_id}: "
                f"Added {newly_covered_count} new keys. "
                f"Total coverage: {len(covered_keys)}"
            )

            # Remove the selected subject from the pool
            del coverage_map[best_candidate_id]

    tqdm.write(f"\nOptimal subject set found with {len(selected_subject_ids)} subjects.")

    # --- Generate the final output files ---
    print("\nWriting final output files...")

    # Write the assembly logic subject database
    assembly_logic_subjects = [
        full_subject_db[id] for id in selected_subject_ids
    ]

    # --- Prepare data for output ---
    # 1. Sort by Index to ensure a consistent, comparable order.
    assembly_logic_subjects.sort(key=lambda x: int(x['Index']))
    
    # 2. Blank out the ZoneAbbrev field to match the format of the comparison file.
    for subject in assembly_logic_subjects:
        subject['ZoneAbbrev'] = ''

    try:
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=assembly_logic_subjects[0].keys())
            writer.writeheader()
            writer.writerows(assembly_logic_subjects)
        print(f" - {Fore.CYAN}Assembly logic subject DB saved to: {output_path}{Fore.RESET}")
    except (IOError, IndexError) as e:
        logging.error(f"Failed to write assembly logic subject DB: {e}")
        sys.exit(1)

    # Write the coverage report
    uncovered_achievable_keys = all_achievable_keys - covered_keys
    impossible_keys = all_possible_keys - all_achievable_keys
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("--- Assembly Logic Coverage Report ---\n\n")
            f.write(f"Total Subjects Selected: {len(selected_subject_ids)}\n\n")
            f.write(f"--- COVERAGE OF ACHIEVABLE KEYS ---\n")
            f.write(f"Total Achievable Keys: {len(all_achievable_keys)}\n")
            f.write(f"Keys Covered: {len(covered_keys)}\n")
            f.write(
                f"Coverage Percentage: "
                f"{len(covered_keys) / len(all_achievable_keys):.1%}\n\n"
            )
            f.write("--- UNCOVERED (BUT ACHIEVABLE) KEYS ---\n")
            if uncovered_achievable_keys:
                for key in sorted(uncovered_achievable_keys):
                    f.write(f"- {key}\n")
            else:
                f.write("None. All achievable keys were covered.\n")
            
            f.write("\n\n--- IMPOSSIBLE KEYS (Not in dataset) ---\n")
            if impossible_keys:
                for key in sorted(impossible_keys):
                    f.write(f"- {key}\n")
            else:
                f.write("None. All possible keys were covered.\n")
        print(f" - {Fore.CYAN}Coverage report saved to: {report_path}{Fore.RESET}")
    except IOError as e:
        logging.error(f"Failed to write coverage report: {e}")
        sys.exit(1)

    print(
        f"\n{Fore.GREEN}SUCCESS: Assembly logic subject selection complete."
        f"{Fore.RESET}\n"
    )


if __name__ == "__main__":
    main()

# === End of scripts/workflows/assembly_logic/2_select_assembly_logic_subjects.py ===



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
# Filename: tests/assembly_logic/step_3_prepare_assembly_logic_import.py

"""
Prepares the Solar Fire import file for the assembly logic subject set.

This utility script is a wrapper around the main `prepare_sf_import.py`
logic. It is used specifically to create the import file needed for the
manual assembly logic generation process in Solar Fire.

It works by:
1.  Reading the list of assembly logic subject IDs from
    `subject_db.gold_standard.csv`.
2.  Filtering the main `adb_final_candidates.txt` list to include only
    these specific subjects.
3.  Calling the refactored `format_for_solar_fire` function to generate
    the final CQD-formatted file.
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

from colorama import Fore

# Add the 'src' directory to the Python path to allow for module imports
sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))

from prepare_sf_import import format_for_solar_fire  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")


def prepare_and_format(final_candidates_source_path, sandbox_dir):
    """
    Filters candidates and formats them for Solar Fire import.
    
    Args:
        final_candidates_source_path (Path): Path to the source adb_final_candidates.txt.
        sandbox_dir (Path): Path to the sandbox directory.
        
    Returns:
        tuple: (number_of_processed_subjects, output_file_path)
    """
    if not sandbox_dir.exists():
        logging.error(f"Sandbox directory not found at '{sandbox_dir}'. Please run select_assembly_logic_subjects.py first.")
        sys.exit(1)
        
    assembly_logic_db_path = sandbox_dir / "data/processed/subject_db.assembly_logic.csv"
    output_path = sandbox_dir / "data/intermediate/sf_data_import.assembly_logic.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("\nLoading and filtering subject data...")
    try:
        with open(assembly_logic_db_path, "r", encoding="utf-8") as f:
            assembly_logic_ids = {row["idADB"] for row in csv.DictReader(f)}

        with open(final_candidates_source_path, "r", encoding="utf-8") as f:
            final_candidates = list(csv.DictReader(f, delimiter="\t"))

        assembly_logic_subjects = [
            s for s in final_candidates if s["idADB"] in assembly_logic_ids
        ]
        logging.info(f"Filtered to {len(assembly_logic_subjects)} assembly logic subjects.")

    except FileNotFoundError as e:
        logging.error(f"Input file not found: {e.filename}")
        sys.exit(1)

    logging.info(f"Writing Solar Fire import file to: {output_path}")
    num_processed = format_for_solar_fire(assembly_logic_subjects, output_path)
    
    return num_processed, output_path


def main():
    """Main function to prepare the assembly logic import file."""
    parser = argparse.ArgumentParser(
        description="Prepare Solar Fire import file for assembly logic subjects."
    )
    parser.add_argument(
        "--final-candidates-source",
        default="data/intermediate/adb_final_candidates.txt",
        help="Path to the source list of final candidates.",
    )
    args = parser.parse_args()

    print(
        f"\n{Fore.YELLOW}--- Preparing Assembly Logic Solar Fire Import File ---"
        f"{Fore.RESET}"
    )

    sandbox_dir = Path("temp_assembly_logic_validation")
    project_root = Path(__file__).resolve().parents[2]
    final_candidates_path = project_root / args.final_candidates_source
    
    num_processed, output_path = prepare_and_format(final_candidates_path, sandbox_dir)

    if num_processed:
        print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
        print(
            f"{Fore.CYAN} - Assembly logic import file saved to: {output_path}"
            f"{Fore.RESET}"
        )
        key_metric = f"Final Count: {num_processed} subjects"
        print(
            f"\n{Fore.GREEN}SUCCESS: {key_metric}. Assembly logic import file "
            f"created successfully.{Fore.RESET}\n"
        )
    else:
        logging.error(
            f"\n{Fore.RED}FAILURE: No records were processed. "
            f"Output file not created.{Fore.RESET}\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

# === End of tests/assembly_logic/step_3_prepare_assembly_logic_import.py ===

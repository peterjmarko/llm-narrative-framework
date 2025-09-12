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
# Filename: scripts/workflows/assembly_logic/5_validate_assembly_logic_subjects.py

"""
Validates the integrity of the assembly logic subject data round-trip.

This utility script performs a critical validation step in the assembly logic
workflow. It takes the chart data exported from Solar Fire and processes it
back into our standard `subject_db` format. It then compares this newly
generated file to the original `subject_db.gold_standard.csv` that was used
to start the process.

If the two files are identical, it provides definitive proof that our Base58
ID encoding/decoding mechanism and the manual Solar Fire processing step
worked perfectly, ensuring the integrity of our assembly logic data.
"""

import argparse
import csv
import logging
import os
import shutil
import sys
from pathlib import Path

import pandas as pd
from colorama import Fore

# Add the 'src' directory to the Python path to allow for module imports
sys.path.append(str(Path(__file__).resolve().parents[3] / "src"))

from create_subject_db import main as create_subject_db_main  # noqa: E402
from pandas.testing import assert_frame_equal  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    """Main function to validate the assembly logic data round-trip."""
    parser = argparse.ArgumentParser(
        description="Validate the assembly logic subject data round-trip."
    )
    parser.add_argument(
        "--final-candidates-source",
        default="data/intermediate/adb_final_candidates.txt",
        help="Path to the source list of final candidates to be filtered.",
    )
    args = parser.parse_args()

    print(
        f"\n{Fore.YELLOW}--- Validating Assembly Logic Data Round-Trip ---{Fore.RESET}"
    )
    
    sandbox_dir = Path("temp_assembly_logic_validation")
    if not sandbox_dir.exists():
        logging.error(f"Sandbox directory not found at '{sandbox_dir}'. Please run the previous scripts first.")
        sys.exit(1)

    # Define paths to files within the sandbox
    sf_export_source_path = sandbox_dir / "data/foundational_assets/sf_chart_export.assembly_logic.csv"
    # This is the generic name that create_subject_db.py expects to find.
    sf_export_dest_path = sandbox_dir / "data/foundational_assets/sf_chart_export.csv"
    original_db_path = sandbox_dir / "data/processed/subject_db.assembly_logic.csv"
    
    # Define the explicit name for the file that will be generated.
    from_sf_output_path = sandbox_dir / "data/processed/subject_db.assembly_logic.from_sf.csv"
    
    # Define the path for the filtered candidates file we will create
    final_candidates_dest = sandbox_dir / "data/intermediate/adb_final_candidates.txt"
    final_candidates_dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        # --- Create a filtered adb_final_candidates.txt for the worker script ---
        # First, we need to load the original assembly logic DB to know which IDs to filter for.
        original_df_for_filtering = pd.read_csv(original_db_path)
        print(f"\nCreating a filtered candidates file for the {len(original_df_for_filtering)} assembly logic subjects...")
        with open(args.final_candidates_source, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            header = reader.fieldnames
            # Convert the pandas Series of ints to a set of strings for correct comparison.
            assembly_logic_ids = set(original_df_for_filtering["idADB"].astype(str))
            assembly_logic_candidates = [
                row for row in reader if row["idADB"] in assembly_logic_ids
            ]
        
        with open(final_candidates_dest, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header, delimiter="\t")
            writer.writeheader()
            writer.writerows(assembly_logic_candidates)
        print("Filtered candidates file created successfully.")

        # Copy the source export file to the generic name the worker script expects,
        # preserving the original file in the sandbox.
        print(f"\nCopying '{sf_export_source_path.name}' to '{sf_export_dest_path.name}' for processing...")
        shutil.copy(sf_export_source_path, sf_export_dest_path)
        print("Copy complete.")

        # --- Step 1: Convert the Solar Fire export back to our format ---
        print(f"\nConverting '{sf_export_dest_path.name}' back to subject_db format...")
        
        original_argv = sys.argv
        sys.argv = [
            "create_subject_db.py",
            "--sandbox-path",
            str(sandbox_dir),
            "--force",
        ]
        # Rename the hardcoded output of create_subject_db.py to our target name
        create_subject_db_main()
        
        # Ensure the destination for the rename doesn't exist from a previous run
        if from_sf_output_path.exists():
            from_sf_output_path.unlink()
        (sandbox_dir / "data/processed/subject_db.csv").rename(from_sf_output_path)
        print("Conversion complete.")

        # --- Step 2: Compare the original and converted files ---
        print(f"\nComparing original and converted files...")
        
        original_df = pd.read_csv(original_db_path, dtype=str)
        converted_df = pd.read_csv(from_sf_output_path, dtype=str)
        original_df.fillna("", inplace=True)
        converted_df.fillna("", inplace=True)
        original_df = original_df.sort_values(by="Index").reset_index(drop=True)
        converted_df = converted_df.sort_values(by="Index").reset_index(drop=True)

        assert_frame_equal(original_df, converted_df)

        print(
            f"\n{Fore.GREEN}SUCCESS: The round-trip data is identical. "
            f"Assembly logic data integrity is confirmed.{Fore.RESET}\n"
        )

    except FileNotFoundError as e:
        logging.error(f"File not found during comparison: {e.filename}")
        sys.exit(1)
    except AssertionError as e:
        logging.error(
            f"\n{Fore.RED}FAILURE: The data is NOT identical. "
            "There is an issue with the data round-trip process.{Fore.RESET}"
        )
        logging.error(f"Please compare the two files inside '{sandbox_dir}':")
        logging.error(f"  - Original: {original_db_path.name}")
        logging.error(f"  - Generated: {from_sf_output_path.name}")
        logging.error(f"Details:\n{e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred during comparison: {e}")
        sys.exit(1)
    finally:
        # Always restore sys.argv
        if 'original_argv' in locals():
            sys.argv = original_argv


if __name__ == "__main__":
    main()

# === End of scripts/workflows/assembly_logic/5_validate_assembly_logic_subjects.py ===



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
# Filename: src/validate_country_codes.py

"""
Validates and diagnoses the country_codes.csv lookup file and its source data.

This script operates in two modes:

1.  **Validation (default):**
    Ensures that every country/state abbreviation present in the raw data
    (`adb_raw_export_fetched.txt`) exists in the `country_codes.csv` lookup file.

2.  **Diagnostic (`--diagnose` flag):**
    Analyzes the distribution of country codes in the raw data to debug
    potential scraping issues. It compares the diversity of codes on the
    first page of results to all subsequent pages.
"""

import os
import pandas as pd
import sys
import argparse

# --- ANSI Color Codes ---
class Colors:
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'

def run_validation(raw_df, country_codes_path):
    """Performs the standard validation of country codes."""
    num_records_checked = len(raw_df)
    rel_country_codes_path = os.path.relpath(country_codes_path).replace(os.sep, '/')

    try:
        codes_df = pd.read_csv(country_codes_path)
    except FileNotFoundError:
        print(f"{Colors.RED}ERROR: Country codes file not found at '{rel_country_codes_path}'{Colors.ENDC}")
        return 1

    source_codes = raw_df['CountryState'].dropna().astype(str).str.strip().unique()
    defined_codes = set(codes_df['Abbreviation'].unique())

    source_codes_set = set(filter(None, source_codes))
    missing_codes = sorted(list(source_codes_set - defined_codes))

    if not missing_codes:
        print(f"{Colors.GREEN}Validation successful! All {len(source_codes_set)} unique codes from {num_records_checked} records are defined.{Colors.ENDC}\n")
        return 0
    else:
        print(f"\n{Colors.RED}Validation FAILED. Found {len(source_codes_set)} unique codes from {num_records_checked} records.{Colors.ENDC}")
        print(f"{Colors.RED}The following {len(missing_codes)} code(s) are missing from `{os.path.basename(country_codes_path)}`:{Colors.ENDC}")
        for code in missing_codes:
            print(f"  - {code}")
        print(f"\n{Colors.YELLOW}Please manually add the missing entries to '{rel_country_codes_path}' and re-run this script.{Colors.ENDC}\n")
        return 1

def run_diagnostic(raw_df):
    """Analyzes the diversity of country codes across paginated results."""
    page_size = 100  # Based on the fetch_adb_data.py script

    print(f"\n{Colors.YELLOW}Running Country Code Diversity Diagnostic...{Colors.ENDC}")
    print(f"Assuming page size of: {page_size}\n")

    page1_df = raw_df.head(page_size)
    rest_df = raw_df.iloc[page_size:]

    total_unique_codes = set(raw_df['CountryState'].dropna().unique())
    page1_unique_codes = set(page1_df['CountryState'].dropna().unique())
    rest_unique_codes = set(rest_df['CountryState'].dropna().unique())

    print(f"{Colors.CYAN}--- Diagnostic Report ---{Colors.ENDC}")
    print(f"{'Total Records Analyzed:':<25} {len(raw_df)}")
    print(f"{'Total Unique Codes:':<25} {len(total_unique_codes)}")
    print("-" * 28)
    print(f"{Colors.YELLOW}Analysis of Page 1 (first {page_size} records):{Colors.ENDC}")
    print(f"{'  Records on Page 1:':<25} {len(page1_df)}")
    print(f"{'  Unique Codes on Page 1:':<25} {len(page1_unique_codes)}")
    print(f"{Colors.YELLOW}Analysis of Subsequent Pages:{Colors.ENDC}")
    print(f"{'  Records on Pages 2+:':<25} {len(rest_df)}")
    print(f"{'  Unique Codes on Pages 2+:':<25} {len(rest_unique_codes)}")
    print("-" * 28)

    if len(page1_unique_codes) > 20 and len(rest_unique_codes) < 5:
        print(f"{Colors.RED}Conclusion: The data strongly suggests a pagination bug.{Colors.ENDC}")
        print("A high diversity of codes appears on the first page, but disappears on subsequent pages.")
    elif len(page1_unique_codes) > len(rest_unique_codes) + 10:
        print(f"{Colors.YELLOW}Conclusion: The data suggests a possible pagination bug.{Colors.ENDC}")
        print("The first page is significantly more diverse than subsequent pages.")
    else:
        print(f"{Colors.GREEN}Conclusion: The low diversity appears consistent across all pages.{Colors.ENDC}")
        print("The issue likely lies in the initial search query parameters, not pagination.")

    print("\nDiagnostic complete.\n")
    return 0

def main():
    """Main function to run the validation or diagnostic."""
    parser = argparse.ArgumentParser(description="Validate or diagnose the country codes data.")
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Run a diagnostic to check for pagination-related data corruption."
    )
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    raw_data_path = os.path.join(project_root, 'data', 'sources', 'adb_raw_export_fetched.txt')
    country_codes_path = os.path.join(project_root, 'data', 'foundational_assets', 'country_codes.csv')
    rel_raw_data_path = os.path.relpath(raw_data_path, project_root).replace(os.sep, '/')

    if not args.diagnose:
        rel_country_codes_path = os.path.relpath(country_codes_path, project_root).replace(os.sep, '/')
        print(f"\n{Colors.YELLOW}Validating '{rel_country_codes_path}' against '{rel_raw_data_path}'...{Colors.ENDC}")

    try:
        raw_df = pd.read_csv(raw_data_path, sep='\t', low_memory=False)
    except FileNotFoundError:
        print(f"{Colors.RED}ERROR: Raw data file not found at '{rel_raw_data_path}'{Colors.ENDC}")
        return 1
    except Exception as e:
        print(f"{Colors.RED}ERROR: Could not read or process '{rel_raw_data_path}': {e}{Colors.ENDC}")
        return 1

    if 'CountryState' not in raw_df.columns:
        print(f"{Colors.RED}ERROR: The 'CountryState' column was not found in '{rel_raw_data_path}'. Cannot proceed.{Colors.ENDC}")
        return 1

    if args.diagnose:
        return run_diagnostic(raw_df)
    else:
        return run_validation(raw_df, country_codes_path)

if __name__ == "__main__":
    sys.exit(main())

# === End of src/validate_country_codes.py ===
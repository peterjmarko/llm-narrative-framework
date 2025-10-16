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
# Filename: src/generate_ocean_scores.py

"""
Generates OCEAN personality scores for all eligible candidates.

This script is the second main component in the "LLM-based Candidate Selection"
stage. It reads the full, rank-ordered list of eligible candidates from the
eminence scores file and queries an LLM to generate OCEAN personality scores
for every subject.

Key Features:
-   **Bypass Aware**: If the `bypass_candidate_selection` flag is true in the
    `config.ini`, the script will issue a warning and prompt for confirmation
    before running, as its output may be ignored by the downstream pipeline.
-   **Robust & Resumable**: Safely resumes interrupted runs without
    reprocessing already-scored subjects.
-   **Comprehensive Reporting**: Generates a detailed summary report with
    descriptive statistics for the scored population.

The output of this script is a complete set of OCEAN scores, which is then
used by the `select_final_candidates.py` script to determine the optimal
final cohort size.
"""

import argparse
import configparser
import csv
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set
from collections import deque

# --- Dependency Check for pandas ---
try:
    import pandas as pd
except ImportError:
    print("FATAL ERROR: The 'pandas' library is required for this script.")
    print("Please install it by running: pdm install pandas")
    sys.exit(1)

from colorama import Fore, init
from tqdm import tqdm

# --- Pre-emptive Path Correction ---
# This must be done before any local imports to ensure modules are found.
try:
    from config_loader import APP_CONFIG
except ImportError:
    current_script_dir = Path(__file__).parent
    src_dir = current_script_dir.parent
    sys.path.insert(0, str(src_dir))

# Initialize colorama
init(autoreset=True, strip=False)

# Ensure the src directory is in the Python path for nested imports
from utils.file_utils import backup_and_remove  # noqa: E402

# --- Constants ---
OCEAN_FIELDNAMES = ["Index", "idADB", "Name", "BirthYear", "Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism"]

# --- Prompt Template ---
OCEAN_PROMPT_TEMPLATE = """
Your task is to act as an expert psychologist and estimate the Big Five OCEAN personality traits for a list of individuals based on their public personas and life histories.

**Rating Scale:**
Rate each trait on a scale from **1.0 (very low) to 7.0 (very high)**. Your scores should be floats with one decimal place.

**Output Format:**
You MUST provide your response as a single, valid JSON array of objects. Each object must contain the following keys: "idADB", "Name", "Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism".

Do not add any commentary, explanations, or text before or after the JSON array.

**Example Response Format:**
[
  {{
    "idADB": "5069",
    "Name": "John F. Kennedy",
    "Openness": 6.5,
    "Conscientiousness": 5.0,
    "Extraversion": 7.0,
    "Agreeableness": 5.5,
    "Neuroticism": 4.0
  }},
  {{
    "idADB": "1234",
    "Name": "Another Person",
    "Openness": 4.0,
    "Conscientiousness": 6.8,
    "Extraversion": 3.1,
    "Agreeableness": 5.0,
    "Neuroticism": 2.5
  }}
]

List of Individuals to Rate:
{subject_list}
"""

# --- Config Loader ---
from config_loader import APP_CONFIG, get_config_value

# Configure logging
logging.basicConfig(level=logging.INFO, format=f"{Fore.YELLOW}%(levelname)s:{Fore.RESET} %(message)s")


def backup_and_overwrite_related_files(output_path: Path):
    """Backs up the main output file and its related summary/report files."""
    summary_path = output_path.parent.parent / "reports" / f"{output_path.stem}_summary.txt"
    missing_report_path = output_path.parent.parent / "reports" / "missing_ocean_scores.txt"
    files_to_back_up = [output_path, summary_path, missing_report_path]
    
    print() # Add a blank line for better spacing
    for p in files_to_back_up:
        backup_and_remove(p)

def load_processed_ids(filepath: Path) -> Set[str]:
    """Reads an existing output file to find which idADBs have been processed."""
    if not filepath.exists() or filepath.stat().st_size == 0:
        return set()
    
    processed_ids = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'idADB' in row and row['idADB']:
                    processed_ids.add(row['idADB'])
    except (IOError, csv.Error) as e:
        logging.error(f"Could not read existing scores file {filepath}: {e}")
        sys.exit(1)
    
    return processed_ids

def load_subjects_to_process(eminence_path: Path, processed_ids: Set[str]) -> List[Dict]:
    """
    Loads subjects from eminence_scores.csv, sorts by eminence, and filters
    out those that have already been processed.
    """
    try:
        eminence_df = pd.read_csv(eminence_path)

        # Sort by eminence score
        sorted_df = eminence_df.sort_values(by="EminenceScore", ascending=False)

        # Filter out subjects that have already been processed
        sorted_df["idADB"] = sorted_df["idADB"].astype(str)
        unprocessed_df = sorted_df[~sorted_df["idADB"].isin(processed_ids)]

        return unprocessed_df.to_dict("records")

    except FileNotFoundError:
        logging.error(f"Required data file not found: {eminence_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error loading subject data: {e}")
        sys.exit(1)

def parse_batch_response(response_text: str) -> List[Dict]:
    """Parses the LLM JSON response to extract score data."""
    try:
        # Find the start of the JSON array
        json_start = response_text.find('[')
        # Find the end of the JSON array
        json_end = response_text.rfind(']')
        if json_start == -1 or json_end == -1:
            logging.warning("Could not find a JSON array in the LLM response.")
            return []
            
        json_string = response_text[json_start:json_end+1]
        parsed_data = json.loads(json_string)
        if isinstance(parsed_data, list):
            return parsed_data
        else:
            logging.warning("Parsed JSON is not a list.")
            return []
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON from LLM response: {e}")
        return []

def save_scores_to_csv(filepath: Path, scores: List[Dict]):
    """Appends a list of scores to the CSV file, enforcing column order."""
    if not scores:
        return

    try:
        file_is_new = not filepath.exists() or filepath.stat().st_size == 0
        file_mode = 'w' if file_is_new else 'a'
        with open(filepath, file_mode, encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=OCEAN_FIELDNAMES)
            if file_is_new:
                writer.writeheader()
            writer.writerows(scores)
    except IOError as e:
        logging.error(f"Failed to write scores to {filepath}: {e}")

import re
def generate_summary_report(filepath: Path, total_subjects_overall: int):
    """Generates a summary report from the final scores file."""
    if not filepath.exists() or filepath.stat().st_size == 0:
        print("\n--- Summary Report ---")
        print("Output file is empty. No summary to generate.")
        return

    summary_path = filepath.parent.parent / "reports" / f"{filepath.stem}_summary.txt"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df = pd.read_csv(filepath)
        report_cols = [field for field in OCEAN_FIELDNAMES if field not in ["Index", "idADB", "Name"]]
        personality_cols = ["Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism"]
        stats_raw = df[report_cols].describe()
        stats_raw['Overall'] = stats_raw[personality_cols].mean(axis=1)
        stats_raw.loc[['count', 'min', 'max'], 'Overall'] = [stats_raw.loc['count', 'Openness'], stats_raw.loc['min', personality_cols].min(), stats_raw.loc['max', personality_cols].max()]
        all_cols_with_overall = ['Overall'] + report_cols
        stats_raw = stats_raw[all_cols_with_overall]

        def format_with_custom_precision(raw_stats_df):
            formatted_df = pd.DataFrame(index=raw_stats_df.index, columns=raw_stats_df.columns)
            for idx in raw_stats_df.index:
                if idx == 'count': formatted_df.loc[idx] = raw_stats_df.loc[idx].map('{:,.0f}'.format)
                elif idx == 'std': formatted_df.loc[idx] = raw_stats_df.loc[idx].map('{:,.4f}'.format)
                else: formatted_df.loc[idx] = raw_stats_df.loc[idx].map('{:,.2f}'.format)
            return formatted_df
        
        stats_formatted = format_with_custom_precision(stats_raw)

        def format_stats_table(stats_df):
            max_header_len = max(len(col) for col in stats_df.columns)
            max_value_len = max(stats_df[col].str.len().max() for col in stats_df.columns)
            col_width = max(max_header_len, max_value_len) + 2
            index_width = max(len(s) for s in stats_df.index) + 2
            header = f"{'':<{index_width}}" + "".join([col.center(col_width) for col in stats_df.columns])
            table_width = len(header)
            lines = [header] + [f"{index:<{index_width}}" + "".join([row[col].center(col_width) for col in stats_df.columns]) for index, row in stats_df.iterrows()]
            return "\n".join(lines), table_width

        stats_string, table_width = format_stats_table(stats_formatted)
        divider = "=" * table_width
        title = "OCEAN Scores Generation Summary".center(table_width)
        total_scored = len(df)

        report_header = [divider, title, divider, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", f"Total Scored:     {total_scored:,}", f"Total in Source:  {total_subjects_overall:,}", "\n--- Descriptive Statistics ---", stats_string]
        
        report_quintiles = ["\n\n" + "--- Quintile Analysis (Degradation of Variance) ---".center(table_width)]
        quintile_size = len(df) // 5
        if quintile_size > 0:
            for i in range(5):
                start, end = i * quintile_size, ((i + 1) * quintile_size if i < 4 else len(df))
                quintile_df = df.iloc[start:end]
                if quintile_df.empty: continue
                q_stats_raw = quintile_df[report_cols].describe().loc[['count', 'mean', 'std']]
                q_stats_raw['Overall'] = q_stats_raw[personality_cols].mean(axis=1)
                q_stats_raw.loc['count', 'Overall'] = q_stats_raw.loc['count', 'Openness']
                q_stats_formatted = format_with_custom_precision(q_stats_raw[all_cols_with_overall])
                q_table_string, _ = format_stats_table(q_stats_formatted)
                report_quintiles.extend([f"\n\n--- Quintile {i+1} ({['Top 20%', '80-60%', '60-40%', '40-20%', 'Bottom 20%'][i]}) (Entries {start+1}-{end}) ---".center(table_width), q_table_string])

        completion_pct = (total_scored / total_subjects_overall) * 100 if total_subjects_overall > 0 else 0
        status_line = f"Completion: {total_scored}/{total_subjects_overall} ({completion_pct:.2f}%)"
        if total_scored == total_subjects_overall: status_msg = f"\n{Fore.GREEN}SUCCESS - {status_line}"
        elif completion_pct >= 95.0: status_msg = f"\n{Fore.YELLOW}WARNING - {status_line}"
        else: status_msg = f"\n{Fore.RED}ERROR - {status_line} - Significantly incomplete."
        report_footer = ["\n" + divider, status_msg]

        summary_content_for_file = "\n".join(report_header + report_quintiles + report_footer)
        summary_content_for_console = "\n".join(report_header + report_footer)
        
        summary_path.write_text(summary_content_for_file, encoding='utf-8')
        print(f"\n{summary_content_for_console}\n")
        
    except Exception as e:
        logging.error(f"Could not generate summary report: {e}")

# Removed load_cutoff_state and perform_pre_flight_check functions as they are no longer needed.

def main():
    """Main function to orchestrate the OCEAN score generation."""
    os.system('')
    # This must be the first action to ensure the config is loaded correctly,
    # especially in a sandboxed test environment.
    from config_loader import APP_CONFIG, get_config_value
    # --- Load Defaults from Config ---
    default_input = get_config_value(APP_CONFIG, 'DataGeneration', 'eminence_scores_output', 'data/foundational_assets/eminence_scores.csv')
    default_output = get_config_value(APP_CONFIG, 'DataGeneration', 'ocean_scores_output', 'data/foundational_assets/ocean_scores.csv')
    default_model = get_config_value(APP_CONFIG, 'DataGeneration', 'ocean_model', 'anthropic/claude-3.5-sonnet')
    default_batch_size = get_config_value(APP_CONFIG, 'DataGeneration', 'ocean_batch_size', 50, value_type=int)
    default_cutoff_pct = get_config_value(APP_CONFIG, 'DataGeneration', 'variance_cutoff_percentage', 0.40, value_type=float)
    default_check_win = get_config_value(APP_CONFIG, 'DataGeneration', 'variance_check_window', 5, value_type=int)
    default_trigger_count = get_config_value(APP_CONFIG, 'DataGeneration', 'variance_trigger_count', 4, value_type=int)
    default_analysis_win = get_config_value(APP_CONFIG, 'DataGeneration', 'variance_analysis_window', 100, value_type=int)
    default_benchmark_pop = get_config_value(APP_CONFIG, 'DataGeneration', 'benchmark_population_size', 500, value_type=int)
    default_cutoff_start = get_config_value(APP_CONFIG, 'DataGeneration', 'cutoff_start_point', 600, value_type=int)

    parser = argparse.ArgumentParser(
        description="Generate OCEAN scores for ADB subjects with a variance-based cutoff.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--sandbox-path", help="Specify a sandbox directory for all file operations.")
    parser.add_argument("--model", default=default_model, help="Name of the LLM to use for scoring.")
    parser.add_argument("--batch-size", type=int, default=default_batch_size, help="Number of subjects per API call.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file, starting from scratch.")
    parser.add_argument("--no-summary", action="store_true", help="Suppress the final summary report output.")
    parser.add_argument("--no-api-warning", action="store_true", help="Suppress the API cost warning.")
    parser.add_argument("--regenerate-summary", action="store_true", help="Regenerate the summary report from existing data without making API calls.")
    args = parser.parse_args()

    # If a sandbox path is provided, set the environment variable.
    if args.sandbox_path:
        os.environ['PROJECT_SANDBOX_PATH'] = os.path.abspath(args.sandbox_path)
    
    # Now that the environment is set, we can safely load modules that depend on it.
    from config_loader import get_path, APP_CONFIG, get_config_value

    # Load bypass_candidate_selection AFTER sandbox is established
    if args.sandbox_path:
        sandbox_config_path = Path(args.sandbox_path) / "config.ini"
        if sandbox_config_path.exists():
            sandbox_config = configparser.ConfigParser()
            sandbox_config.read(sandbox_config_path)
            bypass_candidate_selection = sandbox_config.get("DataGeneration", "bypass_candidate_selection", fallback="false").lower() == 'true'
        else:
            bypass_candidate_selection = False
    else:
        bypass_candidate_selection = get_config_value(APP_CONFIG, "DataGeneration", "bypass_candidate_selection", "false").lower() == 'true'

    # --- Setup Paths & Worker ---
    script_dir = Path(__file__).parent
    input_path = Path(get_path(default_input))
    
    # --- Configure Logging ---
    log_level = logging.INFO
    if os.environ.get('DEBUG_OCEAN', '').lower() == 'true':
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format=f"{Fore.YELLOW}%(levelname)s:{Fore.RESET} %(message)s")
    output_path = Path(get_path(default_output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path = output_path.parent.parent / "reports" / f"{output_path.stem}_summary.txt"
    missing_report_path = output_path.parent.parent / "reports" / "missing_ocean_scores.txt"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = script_dir / "temp_ocean_worker"
    temp_dir.mkdir(exist_ok=True)
    temp_query_file = temp_dir / "query.txt"
    temp_response_file = temp_dir / "response.txt"
    temp_error_file = temp_dir / "error.txt"
    temp_config_file = temp_dir / "temp_config.ini"

    print(f"\n{Fore.YELLOW}--- Starting OCEAN Score Generation ---{Fore.RESET}")
    
    # --- Handle Summary Regeneration Mode ---
    if args.regenerate_summary:
        print("\nRegenerating summary report from existing data...")
        if not output_path.exists():
            logging.error(f"Cannot regenerate summary: The output file '{output_path}' does not exist.")
            sys.exit(1)
        
        try:
            total_subjects_overall = len(pd.read_csv(input_path))
        except (FileNotFoundError, pd.errors.EmptyDataError):
            logging.warning(f"Could not read input file '{input_path}' to get total count. Using count from output file.")
            total_subjects_overall = len(pd.read_csv(output_path))
            
        generate_summary_report(output_path, total_subjects_overall)
        print(f"\n{Fore.GREEN}Summary regeneration complete.{Fore.RESET}\n")
        sys.exit(0)

    # --- Intelligent Startup Logic (Stale Check) ---
    # The following block was removed because it was too aggressive. It incorrectly
    # triggered a full re-run when the input file was merely appended to, which is
    # a valid state during pipeline resumption. The script's standard resumption logic
    # (comparing subject IDs) correctly handles this scenario without needing a
    # timestamp-based check.
    #
    # if not args.force and output_path.exists() and input_path.exists():
    #     if os.path.getmtime(input_path) > os.path.getmtime(output_path):
    #         print(f"{Fore.YELLOW}\nInput file '{input_path.name}' is newer than the existing output. Stale data detected.")
    #         print("Automatically re-running full scoring process..." + Fore.RESET)
    #         backup_and_overwrite_related_files(output_path)
    #         args.force = True

    if args.force and any(p.exists() for p in [output_path, summary_path, missing_report_path]):
        print(f"\n{Fore.YELLOW}--force flag detected. Backing up and removing existing output files...{Fore.RESET}")
        backup_and_overwrite_related_files(output_path)

    # --- Load Data and Determine Scope ---
    processed_ids = load_processed_ids(output_path)
    subjects_to_process = load_subjects_to_process(input_path, processed_ids)
    
    # --- Create Temporary Config for Worker ---
    temp_config = configparser.ConfigParser()
    if APP_CONFIG.has_section('LLM'): temp_config['LLM'] = APP_CONFIG['LLM']
    if APP_CONFIG.has_section('API'): temp_config['API'] = APP_CONFIG['API']
    if not temp_config.has_section('LLM'): temp_config.add_section('LLM')
    temp_config.set('LLM', 'model_name', args.model)
    with open(temp_config_file, 'w') as f: temp_config.write(f)

    # --- Main Batch Processing Loop ---
    all_scores_df = pd.DataFrame()
    if output_path.exists() and output_path.stat().st_size > 0:
        all_scores_df = pd.read_csv(output_path)

    # Pre-flight check is no longer needed with the simplified design.
    
    # If resuming, check if there's anything to do
    # --- Main Logic Branching ---
    # First, handle the bypass case.
    if bypass_candidate_selection and not args.force:
        print(f"\n{Fore.RED}BYPASS ACTIVE: The 'bypass_candidate_selection' flag is set to true in config.ini.{Fore.RESET}")
        print(f"{Fore.YELLOW}The scores generated by this script will be IGNORED by the downstream 'select_final_candidates.py' script.{Fore.RESET}")
        if sys.stdout.isatty():
            confirm = input("Do you wish to proceed anyway? (y/n): ").lower().strip()
            if confirm != 'y':
                print(f"\n{Fore.YELLOW}Operation cancelled by user.{Fore.RESET}\n")
                sys.exit(0)

    # If not bypassing, check if the file is already up-to-date.
    elif not subjects_to_process and not args.force:
        print(f"\n{Fore.YELLOW}Scores file at '{output_path.name}' is already up to date. ✨")
        print("Regenerating summary report...")
        total_possible_subjects = len(processed_ids)
        generate_summary_report(output_path, total_possible_subjects)
        sys.exit(0)

    total_to_process = len(subjects_to_process)
    total_possible_subjects = len(processed_ids) + total_to_process
    bypass_candidate_selection = get_config_value(APP_CONFIG, "DataGeneration", "bypass_candidate_selection", "false").lower() == 'true'

    # Display a non-interactive warning if the script is proceeding automatically
    if not args.no_api_warning and total_to_process > 0 and not (output_path.exists() and not args.force and not 'is_stale' in locals()):
        print(f"\n{Fore.YELLOW}WARNING: This process will make LLM calls incurring API transaction costs which could take some time to complete (1.5 hours or more for a set of 6,000 records).{Fore.RESET}")
        
        if bypass_candidate_selection:
            print(f"{Fore.RED}BYPASS ACTIVE: The 'bypass_candidate_selection' flag is set to true in config.ini.{Fore.RESET}")
            print(f"{Fore.YELLOW}The scores generated by this script will be IGNORED by the downstream 'select_final_candidates.py' script.{Fore.RESET}")
            if sys.stdout.isatty():
                confirm = input("Do you wish to proceed anyway? (y/n): ").lower().strip()
                if confirm != 'y':
                    print(f"\n{Fore.YELLOW}Operation cancelled by user.{Fore.RESET}\n")
                    sys.exit(0)

    print(f"\n{Fore.YELLOW}--- Processing Scope ---{Fore.RESET}")
    print(f"Found {len(processed_ids):,} existing scores.")
    total_batches = (total_to_process + args.batch_size - 1) // args.batch_size
    print(f"Processing {total_to_process:,} new subjects (out of {total_possible_subjects:,} total) in {total_batches} batches of {args.batch_size} subjects each.")

    llm_missed_subjects = []
    consecutive_failures = 0
    max_consecutive_failures = 3
    cutoff_start_subject_count = 0
    stop_reason = "Completed all available subjects."
    was_interrupted = False
    
    try:
        total_batches = (total_to_process + args.batch_size - 1) // args.batch_size
        with tqdm(total=total_to_process, desc="Processing Batches", unit="subject", ncols=80) as pbar:
            for i in range(0, total_to_process, args.batch_size):
                batch = subjects_to_process[i:i + args.batch_size]
                batch_num = (i // args.batch_size) + 1
                pbar.set_description(f"Processing Batch {batch_num}/{total_batches}")

                # 1. Construct prompt
                subject_list_str = "\n".join([f'{s["Name"]} ({s["BirthYear"]}), ID {s["idADB"]}' for s in batch])
                prompt_text = OCEAN_PROMPT_TEMPLATE.format(subject_list=subject_list_str)
                temp_query_file.write_text(prompt_text, encoding='utf-8')

                # 2. Call LLM worker (always in quiet mode for this script)
                worker_cmd = [
                    sys.executable, str(script_dir / "llm_prompter.py"), f"ocean_batch_{batch_num}",
                    "--input_query_file", str(temp_query_file), "--output_response_file", str(temp_response_file),
                    "--output_error_file", str(temp_error_file), "--config_path", str(temp_config_file), "--quiet"
                ]
                subprocess.run(worker_cmd, check=False)
                pbar.refresh()  # Force redraw of the main progress bar

                # 3. Process response
                if temp_error_file.exists() and temp_error_file.stat().st_size > 0:
                    error_msg = temp_error_file.read_text().strip()
                    
                    # Check if this is a network-related error that can be retried
                    is_network_error = any(keyword in error_msg.lower() for keyword in [
                        "connection", "timeout", "chunked encoding", "incomplete", "network", "dns", "ssl"
                    ])
                    
                    if is_network_error:
                        tqdm.write(f"{Fore.YELLOW}Network error for batch {batch_num}. Error: {error_msg}")
                        tqdm.write(f"{Fore.YELLOW}This is a temporary issue and can be retried.{Fore.RESET}")
                    else:
                        tqdm.write(f"{Fore.RED}Worker failed for batch {batch_num}. Error: {error_msg}")
                    
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        tqdm.write(f"{Fore.RED}Halting after {max_consecutive_failures} consecutive batch failures.")
                        stop_reason = "Halted due to consecutive API errors."
                        break
                    continue
                
                consecutive_failures = 0
                response_text = temp_response_file.read_text(encoding='utf-8')
                parsed_scores = parse_batch_response(response_text)

                if not parsed_scores:
                    tqdm.write(f"{Fore.RED}Failed to parse any scores from response for batch {batch_num}.")
                    continue
                
                # --- START: New Hardened Validation Logic ---
                # Create a lookup dictionary from the original batch for fast, accurate validation.
                batch_lookup = {str(s['idADB']): s['Name'] for s in batch}
                validated_scores = []
                
                for score_dict in parsed_scores:
                    llm_id = str(score_dict.get('idADB', ''))
                    llm_name = score_dict.get('Name', '')
                    
                    # 1. Validate ID (Strict): Check if the ID returned by the LLM was in our original request.
                    if llm_id not in batch_lookup:
                        # DISCARD: LLM hallucinated an ID or returned an ID from a different batch.
                        continue
                    
                    # 2. Validate Name (Lenient): Clean the LLM's name output by removing any trailing (YYYY)
                    # before comparing. This handles a common LLM formatting artifact without generating noise.
                    cleaned_llm_name = re.sub(r'\s*\(\d{4}\)$', '', llm_name).strip()

                    original_name_norm = batch_lookup[llm_id].lower().strip()
                    llm_name_norm = cleaned_llm_name.lower().strip()
                    
                    if original_name_norm != llm_name_norm:
                        # Only warn if the names still don't match after cleaning.
                        tqdm.write(f"{Fore.YELLOW}Warning: Name mismatch for idADB {llm_id}. "
                                   f"Expected: '{batch_lookup[llm_id]}', Got: '{llm_name}'. "
                                   f"Accepting record based on matching ID.")
                    
                    # If the ID check passes, the record is considered valid.
                    validated_scores.append(score_dict)

                # Report any discrepancies found during ID validation.
                if len(validated_scores) < len(parsed_scores):
                    num_discarded = len(parsed_scores) - len(validated_scores)
                    tqdm.write(f"{Fore.YELLOW}Warning: Discarded {num_discarded} invalid records from batch {batch_num} due to incorrect or missing IDs.")
                
                # The final, clean list of scores to be saved.
                parsed_scores = validated_scores
                
                if not parsed_scores:
                    tqdm.write(f"{Fore.RED}Error: No valid scores with matching IDs were found in the response for batch {batch_num}.")
                    continue
                # --- END: New Hardened Validation Logic ---

                id_to_birth_year = {str(s["idADB"]): s["BirthYear"] for s in batch}
                start_index = len(all_scores_df) + 1
                for idx, score_dict in enumerate(parsed_scores):
                    score_dict["Index"] = start_index + idx
                    score_dict["BirthYear"] = id_to_birth_year.get(str(score_dict["idADB"]), "")
                save_scores_to_csv(output_path, parsed_scores)
                
                sent_ids = {str(s['idADB']) for s in batch}
                received_ids = {str(p['idADB']) for p in parsed_scores}
                missed_ids = sent_ids - received_ids
                if missed_ids:
                    missed_in_batch = [s for s in batch if str(s['idADB']) in missed_ids]
                    llm_missed_subjects.extend(missed_in_batch)
                    tqdm.write(f"{Fore.YELLOW}Warning: LLM did not return scores for {len(missed_in_batch)} subjects in batch {batch_num}.")

                # Update master dataframe and progress bar
                batch_df = pd.DataFrame(parsed_scores)
                all_scores_df = pd.concat([all_scores_df, batch_df], ignore_index=True)
                pbar.update(len(batch))

    except KeyboardInterrupt:
        was_interrupted = True
        stop_reason = "Process interrupted by user."
        tqdm.write(f"\n\n{Fore.YELLOW}{stop_reason} Exiting gracefully.{Fore.RESET}")
    finally:
        # --- Finalization ---
        tqdm.write(f"\n{Fore.YELLOW}--- Finalizing ---{Fore.RESET}")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        # Correctly calculate the total number of subjects from the single source of truth.
        try:
            total_possible_subjects = len(pd.read_csv(input_path))
        except Exception:
            total_possible_subjects = len(subjects_to_process) + len(processed_ids) # Fallback

        # Always generate reports. They will reflect the final state of the CSV file.
        if not args.no_summary:
            generate_summary_report(output_path, total_possible_subjects)
        # Reconcile final data to ensure completeness before exiting.
        # Read the final state from the disk for the most accurate check.
        final_df_from_disk = pd.read_csv(output_path) if output_path.exists() and output_path.stat().st_size > 0 else pd.DataFrame()
        final_processed_ids = set(final_df_from_disk['idADB'].astype(str)) if not final_df_from_disk.empty else set()
        
        initial_ids = {str(s['idADB']) for s in subjects_to_process} | processed_ids
        missing_ids = initial_ids - final_processed_ids

        generate_missing_scores_report(
            missing_report_path, llm_missed_subjects, subjects_to_process, final_df_from_disk
        )

        # Calculate completion metrics
        completion_rate = (len(final_processed_ids) / len(initial_ids)) * 100 if initial_ids else 0
        missing_count = len(missing_ids)
        
        # Always write completion info to pipeline JSON
        completion_info = {
            'step_name': 'Generate OCEAN Scores',
            'completion_rate': completion_rate,
            'missing_count': missing_count,
            'missing_report_path': str(missing_report_path) if missing_count > 0 else None
        }
        
        completion_info_path = output_path.parent.parent / "reports" / "pipeline_completion_info.json"
        completion_info_path.parent.mkdir(parents=True, exist_ok=True)
        
        if completion_info_path.exists():
            with open(completion_info_path, 'r') as f:
                all_completion_info = json.load(f)
        else:
            all_completion_info = {}
        
        all_completion_info['ocean_scores'] = completion_info
        
        with open(completion_info_path, 'w') as f:
            json.dump(all_completion_info, f, indent=2)
        
        # Handle tiered warnings/errors based on completion rate
        if missing_ids:
            # Tiered approach based on completion rate
            if completion_rate < 95.0:
                # Critical: Stop the pipeline
                tqdm.write(f"{Fore.RED}CRITICAL: Failed to retrieve scores for {len(missing_ids)} subject(s) ({completion_rate:.1f}% completion).{Fore.RESET}")
                from config_loader import PROJECT_ROOT
                display_path = os.path.relpath(missing_report_path, PROJECT_ROOT).replace('\\', '/')
                tqdm.write(f"See '{display_path}' for details.")
                tqdm.write(f"{Fore.RED}The pipeline will be halted. Please re-run the script to automatically retry the missing subjects.{Fore.RESET}")
                sys.exit(1)
            elif completion_rate < 99.0:
                # Warning: Continue but with prominent warning
                tqdm.write(f"{Fore.YELLOW}WARNING: Failed to retrieve scores for {len(missing_ids)} subject(s) ({completion_rate:.1f}% completion).{Fore.RESET}")
                from config_loader import PROJECT_ROOT
                display_path = os.path.relpath(missing_report_path, PROJECT_ROOT).replace('\\', '/')
                tqdm.write(f"See '{display_path}' for details.")
                tqdm.write("The pipeline will continue, but consider re-running to retrieve missing subjects for better results.")
                tqdm.write("")
                tqdm.write(f"{Fore.CYAN}{'='*60}")
                tqdm.write(f"{'RECOMMENDED ACTION':^60}")
                tqdm.write(f"{'='*60}")
                tqdm.write(f"To retry missing subjects, simply re-run the pipeline.")
                tqdm.write(f"It will automatically resume and process the missing data:")
                tqdm.write(f"  pdm run prep-data")
                tqdm.write(f"{'='*60}{Fore.RESET}")
            else:
                # Minor: Continue with simple notification
                tqdm.write(f"{Fore.CYAN}NOTE: Failed to retrieve scores for {len(missing_ids)} subject(s) ({completion_rate:.1f}% completion).{Fore.RESET}")
                from config_loader import PROJECT_ROOT
                display_path = os.path.relpath(missing_report_path, PROJECT_ROOT).replace('\\', '/')
                tqdm.write(f"See '{display_path}' for details. This is within acceptable limits.")

        # Print final status message based on the exit condition
        if was_interrupted:
            tqdm.write(f"\n{Fore.YELLOW}OCEAN score generation terminated by user. ✨\n{Fore.RESET}")
        elif stop_reason.startswith("Halted"):
            tqdm.write(f"\n{Fore.YELLOW}OCEAN score generation halted due to recoverable API errors. ✨\n{Fore.RESET}")
            tqdm.write(f"{Fore.CYAN}Re-run the pipeline to automatically resume and process the missing subjects.{Fore.RESET}\n")
        else:
            final_df = pd.read_csv(output_path) if output_path.exists() and output_path.stat().st_size > 0 else pd.DataFrame()
            
            from config_loader import PROJECT_ROOT
            display_output_path = os.path.relpath(output_path, PROJECT_ROOT).replace('\\', '/')
            display_summary_path = os.path.relpath(summary_path, PROJECT_ROOT).replace('\\', '/')
            display_missing_path = os.path.relpath(missing_report_path, PROJECT_ROOT).replace('\\', '/')

            print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
            print(f"{Fore.CYAN} - OCEAN scores saved to: {display_output_path}{Fore.RESET}")
            print(f"{Fore.CYAN} - Missing scores report saved to: {display_missing_path}{Fore.RESET}")
            print(f"{Fore.CYAN} - Summary report saved to: {display_summary_path}{Fore.RESET}")

            final_count = len(final_df)
            key_metric = f"Final Count: {final_count:,} subjects"
            
            if final_count == 0:
                print(f"\n{Fore.RED}FAILURE: {key_metric}. No OCEAN scores were generated.{Fore.RESET}\n")
            else:
                # Check if we have missing subjects to determine if this was truly successful
                missing_count = total_possible_subjects - final_count
                if missing_count > 0:
                    completion_rate = (final_count / total_possible_subjects) * 100
                    if completion_rate < 95.0:
                        print(f"\n{Fore.RED}PARTIAL: {key_metric}. OCEAN scoring is incomplete ({completion_rate:.1f}% complete).{Fore.RESET}\n")
                    else:
                        print(f"\n{Fore.YELLOW}PARTIAL: {key_metric}. OCEAN scoring is mostly complete ({completion_rate:.1f}% complete).{Fore.RESET}\n")
                else:
                    print(f"\n{Fore.GREEN}SUCCESS: {key_metric}. OCEAN score generation completed as designed. ✨{Fore.RESET}\n")

def generate_missing_scores_report(
    filepath: Path,
    llm_missed_subjects: List[Dict],
    initial_subjects_to_process: List[Dict],
    final_scores_df: pd.DataFrame
):
    """Generates a structured report of all subjects who did not receive a score."""
    try:
        # Determine which subjects were not attempted at all (not just those missed by the LLM)
        initial_ids = {str(s['idADB']) for s in initial_subjects_to_process}
        processed_ids = set(final_scores_df['idADB'].astype(str)) if not final_scores_df.empty else set()
        missed_in_batch_ids = {str(s['idADB']) for s in llm_missed_subjects}
        
        unattempted_ids = initial_ids - processed_ids - missed_in_batch_ids
        unattempted_subjects = [s for s in initial_subjects_to_process if str(s['idADB']) in unattempted_ids]
        
        total_scored = len(processed_ids)
        total_missing = len(llm_missed_subjects) + len(unattempted_subjects)
        total_eligible = total_scored + total_missing
        completion_pct = (total_scored / total_eligible * 100) if total_eligible > 0 else 100

        banner = "=" * 80
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{banner}\n")
            f.write(f"{'Missing OCEAN Scores Report'.center(80)}\n")
            f.write(f"{banner}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("--- Summary ---\n")
            f.write(f"Total Eligible:      {total_eligible:,}\n")
            f.write(f"Total Scored:        {total_scored:,}\n")
            f.write(f"Total Missing:       {total_missing:,} ({100-completion_pct:.1f}%)\n\n")
            
            # --- Section 1: Missed by LLM ---
            f.write(f"{banner}\n")
            f.write(f"CATEGORY 1: Subjects Missed During LLM Processing ({len(llm_missed_subjects)})\n")
            f.write(f"{banner}\n")
            f.write("- The LLM was queried for these subjects but failed to return a valid score.\n\n")
            
            if llm_missed_subjects:
                f.write(f"{'idADB':<10} {'Eminence':<10} {'Name'}\n")
                f.write(f"{'-'*10} {'-'*10} {'-'*50}\n")
                for s in sorted(llm_missed_subjects, key=lambda x: x['Name']):
                    eminence_score = f"{s.get('EminenceScore', 0):.2f}"
                    f.write(f"{s['idADB']:<10} {eminence_score:<10} {s['Name']}\n")
            else:
                f.write("None\n")

            # --- Section 2: Not Attempted ---
            f.write(f"\n{banner}\n")
            f.write(f"CATEGORY 2: Subjects Not Processed ({len(unattempted_subjects)})\n")
            f.write(f"{banner}\n")
            f.write("- The script was halted or did not reach these subjects.\n\n")

            if unattempted_subjects:
                f.write(f"{'idADB':<10} {'Eminence':<10} {'Name'}\n")
                f.write(f"{'-'*10} {'-'*10} {'-'*50}\n")
                # Sort by EminenceScore to show the most important missed subjects first
                for s in sorted(unattempted_subjects, key=lambda x: x.get('EminenceScore', 0), reverse=True):
                    eminence_score = f"{s.get('EminenceScore', 0):.2f}"
                    f.write(f"{s['idADB']:<10} {eminence_score:<10} {s['Name']}\n")
            else:
                f.write("None\n")

    except Exception as e:
        logging.error(f"Failed to generate missing scores report: {e}")


if __name__ == "__main__":
    main()

# === End of src/generate_ocean_scores.py ===

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
# Filename: src/generate_ocean_scores.py

"""
Generates OCEAN scores and determines the final subject pool size.

This script is the second main component in the "LLM-based Candidate Selection"
stage and acts as the final arbiter of the subject pool size. It reads the
rank-ordered list from the eminence scores file and queries an LLM for OCEAN
scores, stopping automatically when personality diversity declines.

Key Features:
-   **Bypass Aware**: If the `bypass_candidate_selection` flag is true in the
    `config.ini`, the script will issue a warning and prompt for confirmation
    before running, as its output will be ignored by the downstream pipeline.
-   **Data-Driven Cutoff**: Stops processing when it detects a sustained drop in
    the variance of OCEAN scores, ensuring a psychologically diverse cohort.
-   **Robust & Resumable**: A pre-flight check re-analyzes all existing data
    on startup, allowing it to safely resume interrupted runs or finalize a
    completed run without reprocessing subjects.
-   **Comprehensive Reporting**: Generates a detailed summary with descriptive
    statistics and a full breakdown of the cutoff analysis.

The final count of subjects in its output file, `ocean_scores.csv`, dictates
the final list and number of subjects for the experiment.
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

# Initialize colorama
init(autoreset=True, strip=False)

# Ensure the src directory is in the Python path for nested imports
sys.path.append(str(Path(__file__).resolve().parents[1]))
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
try:
    from config_loader import APP_CONFIG, get_config_value
except ImportError:
    current_script_dir = Path(__file__).parent
    sys.path.insert(0, str(current_script_dir))
    try:
        from config_loader import APP_CONFIG, get_config_value
    except ImportError as e:
        print(f"FATAL: Could not import from config_loader.py. Error: {e}")
        sys.exit(1)

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
        with open(filepath, 'a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=OCEAN_FIELDNAMES)
            if file_is_new:
                writer.writeheader()
            writer.writerows(scores)
    except IOError as e:
        logging.error(f"Failed to write scores to {filepath}: {e}")

def calculate_average_variance(df: pd.DataFrame) -> float:
    """Calculates the average variance across the five OCEAN trait columns."""
    # Create an explicit copy to avoid SettingWithCopyWarning on slices.
    df = df.copy()
    ocean_cols = ["Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism"]
    # Ensure columns exist and are numeric
    for col in ocean_cols:
        if col not in df.columns:
            return 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df.dropna(subset=ocean_cols, inplace=True)
    if len(df) < 2:
        return 0.0 # Variance is undefined for less than 2 samples
    
    variances = df[ocean_cols].var()
    return variances.mean()


def truncate_and_archive_scores(filepath: Path, num_records_to_keep: int):
    """
    Truncates the main scores file to the specified number of records,
    and archives the discarded records to a separate file.
    """
    if not filepath.exists() or filepath.stat().st_size == 0:
        logging.warning(f"Cannot truncate file that does not exist: {filepath}")
        return
    try:
        df = pd.read_csv(filepath)
        if num_records_to_keep >= len(df):
            logging.info(f"No truncation needed. File has {len(df)} records, asked to keep {num_records_to_keep}.")
            return

        # 1. Archive discarded data
        discarded_df = df.iloc[num_records_to_keep:]
        archive_path = filepath.parent.parent / "intermediate" / f"{filepath.stem}_discarded.csv"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_is_new = not archive_path.exists() or archive_path.stat().st_size == 0
        discarded_df.to_csv(archive_path, mode='a', header=file_is_new, index=False, columns=OCEAN_FIELDNAMES)
        logging.warning(f"Archived {len(discarded_df)} discarded records to '{archive_path}'.")

        # 2. Truncate the main file
        df_truncated = df.head(num_records_to_keep).copy()
        df_truncated['Index'] = range(1, len(df_truncated) + 1)
        df_truncated.to_csv(filepath, index=False, columns=OCEAN_FIELDNAMES)
        logging.info(f"Successfully truncated '{filepath.name}' to the top {num_records_to_keep} records.")

    except Exception as e:
        logging.error(f"Failed to truncate and archive scores: {e}")

import re
def generate_summary_report(
    filepath: Path,
    stop_reason: str,
    total_processed: int,
    final_count: int,
    benchmark_variance: float,
    last_checks: deque,
    variance_analysis_window: int,
    benchmark_population_size: int,
    variance_check_window: int,
    variance_trigger_count: int,
):
    """Generates a summary report from the final scores file."""
    if not filepath.exists() or filepath.stat().st_size == 0:
        print("\n--- Summary Report ---")
        print("Output file is empty. No summary to generate.")
        return

    summary_path = filepath.parent.parent / "reports" / f"{filepath.stem}_summary.txt"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df = pd.read_csv(filepath)
        # Define columns for the main stats table and for the 'Overall' calculation
        report_cols = [field for field in OCEAN_FIELDNAMES if field not in ["Index", "idADB", "Name"]]
        personality_cols = ["Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism"]
        stats_raw = df[report_cols].describe()

        # Calculate the 'Overall' aggregate column for the main table, using only personality scores
        stats_raw['Overall'] = stats_raw[personality_cols].mean(axis=1)
        stats_raw.loc['count', 'Overall'] = stats_raw.loc['count', 'Openness']
        stats_raw.loc['min', 'Overall'] = stats_raw.loc['min', personality_cols].min()
        stats_raw.loc['max', 'Overall'] = stats_raw.loc['max', personality_cols].max()

        # Reorder columns
        all_cols_with_overall = ['Overall'] + report_cols
        stats_raw = stats_raw[all_cols_with_overall]

        def format_with_custom_precision(raw_stats_df):
            """Applies custom formatting rules to each row of a stats dataframe."""
            formatted_df = pd.DataFrame(index=raw_stats_df.index, columns=raw_stats_df.columns)
            for idx in raw_stats_df.index:
                if idx == 'count':
                    formatted_df.loc[idx] = raw_stats_df.loc[idx].map('{:,.0f}'.format)
                elif idx == 'std':
                    formatted_df.loc[idx] = raw_stats_df.loc[idx].map('{:,.4f}'.format)
                else:
                    formatted_df.loc[idx] = raw_stats_df.loc[idx].map('{:,.2f}'.format)
            return formatted_df
        
        stats_formatted = format_with_custom_precision(stats_raw)

        # --- Custom Table Formatter ---
        def format_stats_table(stats_df):
            """Helper function to format a stats dataframe into a string table."""
            # Calculate a single, uniform width for all data columns for even spacing
            max_header_len = max(len(col) for col in stats_df.columns)
            max_value_len = max(stats_df[col].str.len().max() for col in stats_df.columns)
            uniform_col_width = max(max_header_len, max_value_len) + 2
            
            index_width = max(len(s) for s in stats_df.index) + 2
            
            # Use the uniform width for all columns
            header = f"{'':<{index_width}}" + "".join([col.center(uniform_col_width) for col in stats_df.columns])
            table_width = len(header)
            
            table_lines = [header]
            for index, row in stats_df.iterrows():
                line = f"{index:<{index_width}}" + "".join([row[col].center(uniform_col_width) for col in stats_df.columns])
                table_lines.append(line)
            return "\n".join(table_lines), table_width

        stats_string, table_width = format_stats_table(stats_formatted)
        divider = "=" * table_width
        title = "OCEAN Scores Generation Summary".center(table_width)

        report = [divider, title, divider]
        report.append(f"Stop Reason:      {stop_reason}")
        report.append(f"Total Processed:  {total_processed:,}")

        if final_count < total_processed:
            report.append(f"Final Count:      {final_count:,} (rounded down from {total_processed:,})")
        else:
            report.append(f"Final Count:      {final_count:,}")
        
        # --- Cutoff Analysis Section ---
        if benchmark_variance > 0:
            report.append("\n--- Cutoff Analysis (based on Average Variance) ---")
            report.append(f"Rule: Stop if >= {variance_trigger_count} of last {variance_check_window} windows are below threshold.")
            report.append(f"Benchmark Variance (Top {benchmark_population_size}): {benchmark_variance:.4f}")
            for check_point, v_avg, is_met, pct in last_checks:
                start = check_point - variance_analysis_window
                status = "Met" if is_met else "Not Met"
                report.append(f"  - Window (Entries {start+1}-{check_point}): Avg Var: {v_avg:.4f}, Cutoff: {status} ({pct:.2f}%)")

        report.append("\n\n--- Descriptive Statistics for Final Dataset ---")
        report.append(stats_string)

        # --- Quintile Analysis ---
        report.append("\n\n" + "--- Quintile Analysis (Degradation of Variance) ---".center(table_width))
        
        n_total = len(df)
        quintile_size = n_total // 5
        quintile_labels = [
            "Quintile 1 (Top 20%)", "Quintile 2 (80-60%)", "Quintile 3 (60-40%)",
            "Quintile 4 (40-20%)", "Quintile 5 (Bottom 20%)"
        ]

        if quintile_size > 0:
            for i in range(5):
                start_row = i * quintile_size
                # Ensure the last quintile includes all remaining rows
                end_row = (i + 1) * quintile_size if i < 4 else n_total
                
                quintile_df = df.iloc[start_row:end_row]
                if quintile_df.empty:
                    continue

                # Get stats for the quintile
                q_stats_raw = quintile_df[report_cols].describe().loc[['count', 'mean', 'std']]
                
                # Calculate the 'Overall' aggregate column for the quintile, using only personality scores
                q_stats_raw['Overall'] = q_stats_raw[personality_cols].mean(axis=1)
                q_stats_raw.loc['count', 'Overall'] = q_stats_raw.loc['count', 'Openness']
                
                # Reorder and format using the custom precision formatter
                q_stats_formatted = format_with_custom_precision(q_stats_raw[all_cols_with_overall])
                
                # Format the quintile table using the helper
                q_table_string, _ = format_stats_table(q_stats_formatted)
                
                report.append(f"\n\n--- {quintile_labels[i]} (Entries {start_row+1}-{end_row}) ---".center(table_width))
                report.append(q_table_string)

        report.append("\n" + divider)

        # --- Cutoff State for Resumption ---
        report.append("\n--- Cutoff State (for script resumption) ---")
        if benchmark_variance > 0:
            report.append(f"BenchmarkVariance: {benchmark_variance:.4f}")
            # Format for safe and clean serialization
            formatted_checks_for_file = [
                (cp, round(v_avg, 4), is_met, round(pct, 2))
                for cp, v_avg, is_met, pct in last_checks
            ]
            report.append(f"LastChecks_SERIALIZED: {json.dumps(formatted_checks_for_file)}")
        else:
            report.append(f"BenchmarkVariance: Not yet established (requires {benchmark_population_size} subjects).")
            report.append("LastChecks_SERIALIZED: []")
        
        summary_content = "\n".join(report)
        summary_path.write_text(summary_content, encoding='utf-8')
        print(f"\n{summary_content}\n")
        
    except Exception as e:
        logging.error(f"Could not generate summary report: {e}")

def load_cutoff_state(summary_path: Path, maxlen: int) -> (float, deque):
    """Loads benchmark variance and last checks from the summary report."""
    benchmark_variance = 0.0
    last_checks = deque(maxlen=maxlen)

    if not summary_path.exists():
        return benchmark_variance, last_checks

    try:
        content = summary_path.read_text(encoding='utf-8')
        
        bv_match = re.search(r"BenchmarkVariance: (\d+\.\d+)", content)
        if bv_match:
            benchmark_variance = float(bv_match.group(1))

        # Use a non-greedy match that handles newlines
        lc_match = re.search(r"LastChecks_SERIALIZED: (\[.*\])", content)
        if lc_match:
            # Safely parse the list from the dedicated JSON string
            last_checks_list = json.loads(lc_match.group(1))
            last_checks.extend(last_checks_list)
            
    except Exception as e:
        logging.warning(f"Could not parse cutoff state from {summary_path}: {e}")

    return benchmark_variance, last_checks

def perform_pre_flight_check(output_path, args, all_scores_df, benchmark_variance, initial_checks):
    """
    Analyzes the current data to decide if the run should continue or stop.
    It returns the authoritative, up-to-date variance check state for resumption.
    """
    if len(all_scores_df) < args.cutoff_start_point or benchmark_variance == 0:
        return "CONTINUE", initial_checks

    # Recalculate the true state of variance checks from all existing data.
    recalculated_checks = deque(maxlen=args.variance_check_window)
    start = args.cutoff_start_point
    end = len(all_scores_df)

    for check_point in range(start, end + 1, args.variance_analysis_window):
        window_df = all_scores_df.iloc[check_point - args.variance_analysis_window : check_point]
        if len(window_df) < args.variance_analysis_window:
            continue
        
        v_avg = calculate_average_variance(window_df)
        is_met = v_avg < (args.variance_cutoff_percentage * benchmark_variance)
        percentage = (v_avg / benchmark_variance) * 100 if benchmark_variance > 0 else 0.0
        recalculated_checks.append((check_point, v_avg, bool(is_met), percentage))

    met_count = sum(1 for check in recalculated_checks if check[2])
    if met_count < args.variance_trigger_count:
        logging.info(f"{Fore.GREEN}Pre-flight check: Cutoff condition not met ({met_count}/{args.variance_trigger_count}). Resuming run...")
        return "CONTINUE", recalculated_checks

    # --- Cutoff condition IS met based on existing data ---
    logging.warning(f"Pre-flight check: Cutoff condition is met based on existing data ({met_count}/{args.variance_trigger_count}).")
    logging.warning("No new subjects will be processed. Finalizing with current data.")
    
    last_check_checkpoint = recalculated_checks[-1][0]
    cutoff_start_point = last_check_checkpoint - args.variance_analysis_window
    final_rounded_count = (cutoff_start_point // args.variance_analysis_window) * args.variance_analysis_window

    truncate_and_archive_scores(output_path, final_rounded_count)
    generate_summary_report(
        output_path, "Finalized by pre-flight check (cutoff met).", len(all_scores_df), final_rounded_count,
        benchmark_variance, recalculated_checks, args.variance_analysis_window,
        args.benchmark_population_size, args.variance_check_window, args.variance_trigger_count
    )
    return "EXIT", None

def main():
    """Main function to orchestrate the OCEAN score generation."""
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
    parser.add_argument("--variance-cutoff-percentage", type=float, default=default_cutoff_pct, help="Stop when window variance is <% of benchmark variance.")
    parser.add_argument("--variance-check-window", type=int, default=default_check_win, help="Number of recent windows to consider for cutoff (N).")
    parser.add_argument("--variance-trigger-count", type=int, default=default_trigger_count, help="Number of windows that must be below threshold to stop (M).")
    parser.add_argument("--variance-analysis-window", type=int, default=default_analysis_win, help="Fixed number of new subjects for each variance check.")
    parser.add_argument("--benchmark-population-size", type=int, default=default_benchmark_pop, help="Number of top subjects to use for benchmark variance.")
    parser.add_argument("--cutoff-start-point", type=int, default=default_cutoff_start, help="Minimum subjects to process before cutoff logic is active.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file, starting from scratch.")
    parser.add_argument("--no-summary", action="store_true", help="Suppress the final summary report output.")
    parser.add_argument("--no-api-warning", action="store_true", help="Suppress the API cost warning.")
    args = parser.parse_args()

    # If a sandbox path is provided, set the environment variable.
    if args.sandbox_path:
        os.environ['PROJECT_SANDBOX_PATH'] = os.path.abspath(args.sandbox_path)
    
    # Now that the environment is set, we can safely load modules that depend on it.
    from config_loader import get_path, APP_CONFIG, get_config_value

    # Load bypass_candidate_selection AFTER sandbox is established
    if args.sandbox_path:
        import configparser
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

    # --- Intelligent Startup Logic (Stale Check) ---
    if not args.force and output_path.exists() and input_path.exists():
        if os.path.getmtime(input_path) > os.path.getmtime(output_path):
            print(f"{Fore.YELLOW}\nInput file '{input_path.name}' is newer than the existing output. Stale data detected.")
            print("Automatically re-running full scoring process...{Fore.RESET}")
            backup_and_overwrite_related_files(output_path)
            args.force = True

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

    # --- Pre-flight Check ---
    summary_path = output_path.parent.parent / "reports" / f"{output_path.stem}_summary.txt"
    benchmark_variance, initial_checks = load_cutoff_state(summary_path, args.variance_check_window)
    
    if not args.force:
        status, last_variance_checks = perform_pre_flight_check(output_path, args, all_scores_df, benchmark_variance, initial_checks)
        if status == "EXIT":
            sys.exit(0)
    else:
        # If forcing, we don't need the pre-flight check's result, just an initialized deque
        last_variance_checks = initial_checks
    
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
        print(f"\n{Fore.YELLOW}WARNING: The scores file at '{output_path}' is already up to date. ✨")
        print(f"{Fore.YELLOW}The update process incurs API costs and can take some time to complete.")
        print(f"{Fore.YELLOW}If you decide to go ahead with recreating OCEAN scores, a backup of the existing file will be created first.{Fore.RESET}")
        confirm = input("Do you wish to proceed? (Y/N): ").lower().strip()
        if confirm == 'y':
            print(f"{Fore.YELLOW}Backing up and removing existing output files...{Fore.RESET}")
            backup_and_overwrite_related_files(output_path)
            args.force = True
            # Re-load after backup to ensure we process everything
            processed_ids = load_processed_ids(output_path)
            subjects_to_process = load_subjects_to_process(input_path, processed_ids)
            # CRITICAL FIX: Reset the in-memory DataFrame after deleting the file
            all_scores_df = pd.DataFrame()
        else:
            print(f"\n{Fore.YELLOW}Operation cancelled by user.\n")
            sys.exit(0)

    # Correctly calculate the total to process *after* the interactive prompt has run
    total_to_process = len(subjects_to_process)
    total_possible_subjects = len(processed_ids) + total_to_process
    bypass_candidate_selection = get_config_value(APP_CONFIG, "DataGeneration", "bypass_candidate_selection", "false").lower() == 'true'

    # Display a non-interactive warning if the script is proceeding automatically
    if not args.no_api_warning and total_to_process > 0 and not (output_path.exists() and not args.force and not 'is_stale' in locals()):
        print(f"\n{Fore.YELLOW}WARNING: This process will make LLM calls that will take some time and incur API transaction costs.{Fore.RESET}")
        
        if bypass_candidate_selection:
            print(f"{Fore.RED}BYPASS ACTIVE: The 'bypass_candidate_selection' flag is set to true in config.ini.{Fore.RESET}")
            print(f"{Fore.YELLOW}The scores generated by this script will be IGNORED by the downstream 'select_final_candidates.py' script.{Fore.RESET}")
            confirm = input("Do you wish to proceed anyway? (y/n): ").lower().strip()
            if confirm != 'y':
                print(f"\n{Fore.YELLOW}Operation cancelled by user.{Fore.RESET}\n")
                sys.exit(0)

    print(f"\n{Fore.YELLOW}--- Processing Scope ---{Fore.RESET}")
    print(f"Found {len(processed_ids):,} existing scores.")
    print(f"Processing {total_to_process:,} new subjects (out of {total_possible_subjects:,} total).")

    llm_missed_subjects = []
    consecutive_failures = 0
    max_consecutive_failures = 3
    cutoff_start_subject_count = 0
    stop_reason = "Completed all available subjects."
    was_interrupted = False
    
    try:
        for i in range(0, total_to_process, args.batch_size):
            batch = subjects_to_process[i:i + args.batch_size]
            # Calculate batch numbers relative to the current run for accurate progress
            session_batch_num = (i // args.batch_size) + 1
            total_session_batches = (total_to_process + args.batch_size - 1) // args.batch_size
            
            print(f"\n{Fore.CYAN}--- Processing Session Batch {session_batch_num} of {total_session_batches} (max) ---{Fore.RESET}")

            # 1. Construct prompt
            subject_list_str = "\n".join([f'{s["Name"]} ({s["BirthYear"]}), ID {s["idADB"]}' for s in batch])
            prompt_text = OCEAN_PROMPT_TEMPLATE.format(subject_list=subject_list_str)
            temp_query_file.write_text(prompt_text, encoding='utf-8')

            # 2. Call LLM worker
            worker_cmd = [
                sys.executable, str(script_dir / "llm_prompter.py"), f"ocean_batch_{session_batch_num}",
                "--input_query_file", str(temp_query_file), "--output_response_file", str(temp_response_file),
                "--output_error_file", str(temp_error_file), "--config_path", str(temp_config_file)
            ]
            if log_level > logging.DEBUG: worker_cmd.append("--quiet")
            subprocess.run(worker_cmd, check=False)

            # 3. Process response
            if temp_error_file.exists() and temp_error_file.stat().st_size > 0:
                error_msg = temp_error_file.read_text().strip()
                logging.error(f"Worker failed for batch {session_batch_num}. Error: {error_msg}")
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logging.critical(f"Halting after {max_consecutive_failures} consecutive batch failures.")
                    stop_reason = "Halted due to consecutive API errors."
                    break
                temp_error_file.unlink()
                continue
            
            consecutive_failures = 0
            
            if not temp_response_file.exists():
                logging.error(f"Worker did not produce response file for batch {session_batch_num}.")
                continue
            
            response_text = temp_response_file.read_text(encoding='utf-8')
            parsed_scores = parse_batch_response(response_text)

            if not parsed_scores:
                logging.error(f"Failed to parse any scores from response for batch {session_batch_num}.")
                continue
            
            # Create a lookup map to add BirthYear back to the results
            id_to_birth_year = {str(s["idADB"]): s["BirthYear"] for s in batch}
            
            start_index = len(all_scores_df) + 1
            for idx, score_dict in enumerate(parsed_scores):
                score_dict["Index"] = start_index + idx
                # Add the BirthYear from our lookup map
                score_dict["BirthYear"] = id_to_birth_year.get(str(score_dict["idADB"]), "")

            save_scores_to_csv(output_path, parsed_scores)
            
            # Reconcile sent vs received to find missed subjects
            sent_ids = {str(s['idADB']) for s in batch}
            received_ids = {str(p['idADB']) for p in parsed_scores}
            missed_ids = sent_ids - received_ids
            if missed_ids:
                missed_in_batch = [s for s in batch if str(s['idADB']) in missed_ids]
                llm_missed_subjects.extend(missed_in_batch)
                logging.warning(f"LLM did not return scores for {len(missed_in_batch)} subjects in this batch.")

            # 4. Variance Cutoff Logic
            batch_df = pd.DataFrame(parsed_scores)
            
            previous_total = len(all_scores_df)
            all_scores_df = pd.concat([all_scores_df, batch_df], ignore_index=True)
            new_total = len(all_scores_df)
            
            print(f"Successfully processed and saved {len(parsed_scores)} scores. Total overall: {new_total:,}")
            
            # Check if we crossed a boundary for statistical analysis
            if (new_total // args.variance_analysis_window) > (previous_total // args.variance_analysis_window):
                
                # Establish the benchmark variance once enough subjects are collected
                if benchmark_variance == 0 and new_total >= args.benchmark_population_size:
                    benchmark_df = all_scores_df.iloc[:args.benchmark_population_size]
                    benchmark_variance = calculate_average_variance(benchmark_df)
                    logging.info(f"{Fore.GREEN}Benchmark variance established from top {args.benchmark_population_size} subjects: {benchmark_variance:.4f}")

                # If benchmark is set, perform the cutoff check
                if benchmark_variance > 0:
                    check_point = (new_total // args.variance_analysis_window) * args.variance_analysis_window
                    
                    if check_point < args.cutoff_start_point:
                        logging.info(f"{Fore.CYAN}Cutoff checks will begin after {args.cutoff_start_point} subjects are processed.")
                    else:
                        latest_window_df = all_scores_df.iloc[check_point - args.variance_analysis_window : check_point]
                        V_avg_latest_window = calculate_average_variance(latest_window_df)
                        
                        percentage = (V_avg_latest_window / benchmark_variance) * 100 if benchmark_variance > 0 else 0.0
                        logging.info(f"Variance Check: Benchmark Avg={benchmark_variance:.4f}, Latest {len(latest_window_df)} entries Avg={V_avg_latest_window:.4f} ({percentage:.2f}%)")

                        is_met = V_avg_latest_window < (args.variance_cutoff_percentage * benchmark_variance)
                        # Convert numpy.bool_ to standard Python bool for JSON serialization
                        last_variance_checks.append((check_point, V_avg_latest_window, bool(is_met), percentage))
                        
                        met_count = sum(1 for check in last_variance_checks if check[2])
                        # Report against the configured check window size for clarity
                        logging.warning(f"Cutoff Status: {met_count}/{args.variance_trigger_count} of last {args.variance_check_window} windows have met the threshold ({len(last_variance_checks)} currently tracked).")

                        if met_count >= args.variance_trigger_count:
                            stop_reason = f"Cutoff met ({met_count} of last {len(last_variance_checks)} windows below threshold)."
                            
                            # Set cutoff to the beginning of the window that triggered this final check.
                            cutoff_start_subject_count = check_point - args.variance_analysis_window
                            
                            logging.warning(f"{Fore.RED}STOPPING: {stop_reason}")
                            break # Exit main loop
            
            time.sleep(1)

    except KeyboardInterrupt:
        was_interrupted = True
        stop_reason = "Process interrupted by user."
        print(f"\n\n{Fore.YELLOW}{stop_reason} Exiting gracefully.{Fore.RESET}")
    finally:
        # --- Finalization ---
        print("\n--- Finalizing ---")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        total_processed_count = len(all_scores_df)
        final_count = total_processed_count  # Default to preserving all data

        # Only truncate the file if the specific "Cutoff met" reason was given
        if stop_reason.startswith("Cutoff met"):
            # The cutoff point is the start of the window that triggered the final check
            final_raw_count = cutoff_start_subject_count
            # Round down to the nearest full window size for a clean dataset
            final_count = (final_raw_count // args.variance_analysis_window) * args.variance_analysis_window
            truncate_and_archive_scores(output_path, final_count)

        # Always generate reports. They will reflect the final state of the CSV file.
        if not args.no_summary:
            generate_summary_report(
                output_path, stop_reason, total_processed_count, final_count,
                benchmark_variance, last_variance_checks, args.variance_analysis_window,
                args.benchmark_population_size, args.variance_check_window, args.variance_trigger_count,
            )
        generate_missing_scores_report(
            missing_report_path, llm_missed_subjects, subjects_to_process, all_scores_df
        )

        # Print final status message based on the exit condition
        if was_interrupted:
            logging.warning("OCEAN score generation terminated by user. ✨\n")
        elif stop_reason.startswith("Halted"):
            logging.critical("OCEAN score generation halted due to critical errors. ✨\n")
        else:
            final_df = pd.read_csv(output_path) if output_path.exists() and output_path.stat().st_size > 0 else pd.DataFrame()
            
            from config_loader import PROJECT_ROOT
            display_output_path = os.path.relpath(output_path, PROJECT_ROOT)
            display_summary_path = os.path.relpath(summary_path, PROJECT_ROOT)
            display_missing_path = os.path.relpath(missing_report_path, PROJECT_ROOT)

            print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
            print(f"{Fore.CYAN} - OCEAN scores saved to: {display_output_path}{Fore.RESET}")
            print(f"{Fore.CYAN} - Missing scores report saved to: {display_missing_path}{Fore.RESET}")
            print(f"{Fore.CYAN} - Summary report saved to: {display_summary_path}{Fore.RESET}")

            final_count = len(final_df)
            key_metric = f"Final Count: {final_count:,} subjects"
            
            if final_count == 0:
                print(f"\n{Fore.RED}FAILURE: {key_metric}. No OCEAN scores were generated.{Fore.RESET}\n")
            else:
                print(f"\n{Fore.GREEN}SUCCESS: {key_metric}. OCEAN score generation completed as designed. ✨{Fore.RESET}\n")

def generate_missing_scores_report(
    filepath: Path,
    llm_missed_subjects: List[Dict],
    initial_subjects_to_process: List[Dict],
    final_scores_df: pd.DataFrame
):
    """Generates a report of all subjects who did not receive a score."""
    try:
        # Determine which subjects were not attempted at all
        initial_ids = {str(s['idADB']) for s in initial_subjects_to_process}
        processed_ids = set(final_scores_df['idADB'].astype(str)) if not final_scores_df.empty else set()
        missed_in_batch_ids = {str(s['idADB']) for s in llm_missed_subjects}
        
        unattempted_ids = initial_ids - processed_ids - missed_in_batch_ids
        unattempted_subjects = [s for s in initial_subjects_to_process if str(s['idADB']) in unattempted_ids]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("Missing OCEAN Scores Report".center(80) + "\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"--- Subjects Missed in LLM Batches ({len(llm_missed_subjects)}) ---\n")
            if llm_missed_subjects:
                for s in sorted(llm_missed_subjects, key=lambda x: x['Name']):
                    f.write(f"  - {s['Name']} (idADB: {s['idADB']})\n")
            else:
                f.write("  None\n")
            
            f.write(f"\n--- Subjects Not Attempted ({len(unattempted_subjects)}) ---\n")
            if unattempted_subjects:
                 for s in sorted(unattempted_subjects, key=lambda x: x.get('EminenceScore', 0), reverse=True):
                    f.write(f"  - {s['Name']} (idADB: {s['idADB']})\n")
            else:
                f.write("  None\n")

        # Final log messages are handled by the main finally block.

    except Exception as e:
        logging.error(f"Failed to generate missing scores report: {e}")


if __name__ == "__main__":
    main()

# === End of src/generate_ocean_scores.py ===

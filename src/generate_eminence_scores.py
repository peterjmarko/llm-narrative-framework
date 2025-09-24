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
# Filename: src/generate_eminence_scores.py

"""
Generates eminence scores for all "eligible candidates".

This script is the first of two main components in the "LLM-based Candidate
Selection" stage. It reads the pre-filtered list of eligible candidates,
groups them into batches, and queries an LLM for a calibrated "eminence" score
for each individual.

Key Features:
-   **Bypass Aware**: If the `bypass_candidate_selection` flag is true in the
    `config.ini`, the script will issue a warning and prompt for confirmation
    before running, as its output will be ignored by the downstream pipeline.
-   **Resilient & Resumable**: Safely stops with Ctrl+C and resumes from the
    last completed batch on the next run.
-   **Calibrated Prompting**: Uses a sophisticated prompt with fixed historical
    anchors (e.g., Plato, Einstein) and 20th-century examples to force the
    LLM to use a consistent, absolute scale.
-   **Automated Reporting**: Upon completion, it automatically sorts the final
    data by score and generates a detailed summary report.

The final output is `eminence_scores.csv`, a foundational asset for the
downstream OCEAN scoring script, containing the headers: `Index`, `idADB`,
`Name`, `BirthYear`, and `EminenceScore`.
"""

import argparse
import configparser
import csv
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

from colorama import Fore, init
from tqdm import tqdm

# --- Pre-emptive Path Correction ---
# Ensure the `src` directory is in the Python path for reliable module imports.
# This must be done before any local imports.
try:
    from config_loader import APP_CONFIG
except ImportError:
    # If the script is run directly, the src directory might not be in the path
    current_script_dir = Path(__file__).parent
    src_dir = current_script_dir.parent
    sys.path.insert(0, str(src_dir))

# Initialize colorama
init(autoreset=True, strip=False)

# --- Prompt Template ---
EMINENCE_PROMPT_TEMPLATE = """
Your task is to act as an expert historian and rate individuals on an absolute eminence scale of 0-100, considering **all people who have ever lived in human history**.

**Global Historical Anchors:**
To calibrate your ratings, use these historical figures as an absolute, fixed guide.
- **100.0:** A figure like **Jesus Christ**, whose impact is maximal across millennia and cultures.
- **99.5:** A foundational figure of civilization, like **Plato** or **Isaac Newton**.
- **99.0:** A modern giant who redefined our understanding of the universe, like **Albert Einstein**.

**20th-Century Examples (for finer calibration):**
- **~95.0:** A dominant global leader of their era, like **John F. Kennedy**.
- **~90.0:** A person who fundamentally changed a major field, like **Alan Turing**.
- **~85.0:** An iconic, enduring cultural figure, like **Marilyn Monroe**.
- **~70.0:** A celebrity well-known for decades, but with less historical impact, like **Zsa Zsa Gabor**.
- **~45.0:** A nationally-known politician (e.g., a typical US Senator).

**Definition of Eminence vs. Fame:**
Your primary task is to distinguish "lasting historical eminence" from "transient celebrity" or "pop culture fame."
- **Eminence** implies a foundational, enduring impact on culture, science, politics, or art that will be remembered for centuries.
- **Fame** can be immense but is often tied to entertainment and may fade faster over historical time.
Figures like Michael Jackson, Lionel Messi, or Oprah Winfrey are global icons of fame *currently*, but their *historical* eminence is not the same as a figure like Isaac Newton, who redefined science. Please use this distinction in your ratings.

**Crucial Context for this Task:**
The list you are about to rate contains **only famous people from the 20th century**. Given the historical anchors above, it is unlikely that anyone in this specific list will score above 98.0. You should expect most scores to fall between 40.0 and 95.0.

**Final Instruction:**
Your scores MUST reflect this absolute, history-wide scale. **Do NOT normalize your scores relative to the other people in the batch you are given.** Rate each person independently against the global anchors and the definition of eminence.

Provide your response as a list, with each person on a new line, in the exact format:
"<FullName> (<BirthYear>), ID <idADB>: <Score>"

Do not add any commentary before or after the list of rated individuals.

List of Individuals to Rate:
{subject_list}
"""

# --- Config Loader ---
from config_loader import APP_CONFIG, get_config_value

# Configure logging
logging.basicConfig(level=logging.INFO, format=f"{Fore.YELLOW}%(levelname)s:{Fore.RESET} %(message)s")


from utils.file_utils import backup_and_remove

def load_processed_ids(filepath: Path) -> set:
    """
    Reads an existing output file to find which idADBs have been processed.
    Detects and halts on legacy file format ('ARN' column).
    """
    if not filepath.exists() or filepath.stat().st_size == 0:
        return set()
    
    processed_ids = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Read just the header to check for format compatibility.
            header_line = f.readline()
            reader = csv.reader([header_line])
            header = next(reader)

            if 'idADB' not in header:
                if 'ARN' in header:
                    from config_loader import PROJECT_ROOT
                    display_path = os.path.relpath(filepath, PROJECT_ROOT)
                    # Legacy format detected. Halt with instructions.
                    logging.critical("Incompatible legacy file format detected.")
                    logging.error(f"The existing file '{display_path}' uses the old 'ARN' column.")
                    logging.error("The new script requires an 'idADB' column to function correctly.")
                    print("\nTo fix this, you have two options:")
                    print(f"  1. Manually rename or delete the old file: '{filepath}'")
                    print(f"  2. Re-run the script with the {Fore.CYAN}--force{Fore.RESET} flag to automatically back up and overwrite it.")
                    sys.exit(1)
                else:
                    from config_loader import PROJECT_ROOT
                    display_path = os.path.relpath(filepath, PROJECT_ROOT)
                    # Header is malformed.
                    logging.critical("Malformed CSV header.")
                    logging.error(f"Could not find required 'idADB' column in '{display_path}'.")
                    sys.exit(1)

            # If header is valid, proceed to read the rest of the file.
            f.seek(0) # Go back to the start of the file.
            dict_reader = csv.DictReader(f)
            for row in dict_reader:
                if 'idADB' in row and row['idADB']:
                    processed_ids.add(row['idADB'])
    except csv.Error as e:
        logging.error(f"Could not parse existing scores file {filepath}: {e}. Starting fresh.")
        return set()
    except IOError as e:
        logging.error(f"Could not read existing scores file {filepath}: {e}")
        sys.exit(1)
    
    return processed_ids

def load_subjects_to_process(input_path: Path, processed_ids: set) -> List[Dict]:
    """Loads all subjects from the eligible candidates file and filters out processed ones."""
    subjects_to_process = []
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                id_adb = row.get('idADB')
                if id_adb and id_adb not in processed_ids:
                    subjects_to_process.append(row)
    except FileNotFoundError:
        logging.error(f"Input file not found: {input_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading input file {input_path}: {e}")
        sys.exit(1)
    return subjects_to_process

def parse_batch_response(response_text: str) -> List[Tuple[str, str, str, str]]:
    """
    Parses the LLM response to extract idADB, name, birth year, and score.
    Uses a robust right-split method and regex to handle complex names.
    """
    parsed_data = []
    lines = response_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        try:
            # Split from the right on ", ID" to isolate the name part.
            name_part, id_score_part = line.rsplit(', ID', 1)
            
            # Parse the ID and score from the second part.
            id_match = re.search(r'(\d+):\s*([\d.]+)', id_score_part)
            if not id_match:
                continue

            id_adb = id_match.group(1)
            score = id_match.group(2)
            
            # Clean quotes and whitespace from the name part.
            cleaned_name_part = name_part.strip().strip('"')
            
            # Check for a birth year in parentheses at the end of the name.
            year_match = re.search(r'\s*\((\d{4})\)$', cleaned_name_part)
            if year_match:
                birth_year = year_match.group(1)
                # Remove the year from the name for a clean name field.
                name = re.sub(r'\s*\(\d{4}\)$', '', cleaned_name_part).strip()
            else:
                birth_year = ''
                name = cleaned_name_part
            
            parsed_data.append((id_adb, name, birth_year, score))
        except ValueError:
            logging.warning(f"Could not parse line: '{line}'")
            continue
            
    return parsed_data

def save_scores_to_csv(filepath: Path, scores: List[Tuple[str, str, str, str]], start_index: int):
    """Appends a list of scores to the CSV file, adding a header only if the file is new."""
    try:
        file_is_new = not filepath.exists() or filepath.stat().st_size == 0

        with open(filepath, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            if file_is_new:
                writer.writerow(["Index", "idADB", "Name", "BirthYear", "EminenceScore"])
            
            for i, (id_adb, name, birth_year, score) in enumerate(scores):
                writer.writerow([start_index + i, id_adb, name, birth_year, score])
    except IOError as e:
        logging.error(f"Failed to write scores to {filepath}: {e}")

def sort_and_reindex_scores(filepath: Path) -> bool:
    """
    Sorts the scores file by EminenceScore (desc) and re-applies the Index.
    Returns True on success, False on failure.
    """
    if not filepath.exists() or filepath.stat().st_size == 0:
        return True  # Nothing to do is considered a success

    try:
        import pandas as pd
        df = pd.read_csv(filepath)
        df['EminenceScore'] = pd.to_numeric(df['EminenceScore'], errors='coerce')
        df.dropna(subset=['EminenceScore'], inplace=True)
        df.sort_values(by=['EminenceScore', 'Name'], ascending=[False, True], inplace=True)
        df['Index'] = range(1, len(df) + 1)
        df.to_csv(filepath, index=False, float_format='%.2f')
        return True
    except ImportError:
        logging.warning("Pandas not installed. Skipping sorting. Install with 'pdm add pandas'.")
        return True # Not a fatal error, but we didn't sort. Treat as success for reporting.
    except Exception as e:
        logging.error(f"Could not sort scores file: {e}")
        return False

def generate_scores_summary(filepath: Path, total_subjects_overall: int):
    """Generates a summary report from the final scores file."""
    if not filepath.exists() or filepath.stat().st_size == 0:
        print("\n--- Summary Report ---")
        print("Output file is empty. No summary to generate.")
        return

    from config_loader import get_path
    reports_dir = Path(get_path("data/reports"))
    summary_path = reports_dir / f"{filepath.stem}_summary.txt"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pandas as pd
        df = pd.read_csv(filepath)
        
        total_scored = len(df)
        stats = df['EminenceScore'].describe()
        
        bins = [0, 20, 40, 60, 70, 80, 90, 95, 100]
        labels = [f"{bins[i]}-{bins[i+1]}" for i in range(len(bins)-1)]
        df['Score Range'] = pd.cut(df['EminenceScore'], bins=bins, labels=labels, right=False)
        distribution = df['Score Range'].value_counts().sort_index()

        top_10 = df.head(10)

        banner = "="*50
        report = [banner, f"{'Eminence Scores Summary'.center(50)}", banner]
        report.append(f"Total Scored:     {total_scored:,}")
        report.append(f"Total in Source:  {total_subjects_overall:,}")
        
        def _stat_line(label: str, value: float, label_width: int = 16, value_width: int = 8) -> str:
            # Two leading spaces, then label padded to label_width, then value right-aligned
            return f"  {label:<{label_width}}{value:>{value_width}.2f}"

        report.extend([
            "\n--- Descriptive Statistics ---",
            f"  Mean:           {stats['mean']:.2f}",
            f"  Std Dev:        {stats['std']:.2f}",
            f"  Min:            {stats['min']:.2f}",
            f"  25% (Q1):       {stats['25%']:.2f}",
            f"  50% (Median):   {stats['50%']:.2f}",
            f"  75% (Q3):       {stats['75%']:.2f}",
            f"  Max:            {stats['max']:.2f}",
        ])
        
        report.append("\n--- Score Distribution ---")
        for label, count in distribution.items():
            report.append(f"  {label:<10}: {count:>{5},d} ({count/total_scored:7.2%})")

        report.append("\n--- Top 10 Most Eminent ---")
        for _, row in top_10.iterrows():
            report.append(f"  {row['EminenceScore']:>5.2f} - {row['Name']}")
        report.append(banner)

        completion_pct = (total_scored / total_subjects_overall) * 100 if total_subjects_overall > 0 else 0
        status_line = f"Completion: {total_scored}/{total_subjects_overall} ({completion_pct:.2f}%)"
        
        # The SUCCESS keyword is the trigger for the orchestrator to mark the step as complete.
        if total_scored == total_subjects_overall:
            report.append(f"\n{Fore.GREEN}SUCCESS - {status_line}")
        elif completion_pct >= 95.0:
            report.append(f"\n{Fore.YELLOW}WARNING - {status_line}")
        else:
            report.append(f"\n{Fore.RED}ERROR - {status_line} - Significantly incomplete.")

        summary_content_for_console = "\n".join(report)
        # Remove ANSI color codes for the version saved to the file
        summary_content_for_file = re.sub(r'\x1b\[[0-9;]*m', '', summary_content_for_console)
        
        summary_path.write_text(summary_content_for_file, encoding='utf-8')
        print(f"\n{summary_content_for_console}")
        
        from config_loader import PROJECT_ROOT
        display_scores_path = os.path.relpath(filepath, PROJECT_ROOT).replace('\\', '/')
        display_summary_path = os.path.relpath(summary_path, PROJECT_ROOT).replace('\\', '/')

        print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
        print(f"{Fore.CYAN} - Eminence scores saved to: {display_scores_path}{Fore.RESET}")
        print(f"{Fore.CYAN} - Summary report saved to: {display_summary_path}{Fore.RESET}")

        key_metric = f"Scored {total_scored:,} of {total_subjects_overall:,} subjects"
        if total_scored == 0 and total_subjects_overall > 0:
            print(f"\n{Fore.RED}FAILURE: {key_metric}. No scores were generated. Please check for errors.{Fore.RESET}\n")
        else:
            print(f"\n{Fore.GREEN}SUCCESS: {key_metric}. Eminence scoring completed successfully. ✨{Fore.RESET}\n")

    except ImportError:
        logging.warning("Pandas not installed. Skipping summary report. Install with 'pdm add pandas'.")
    except Exception as e:
        logging.error(f"Could not generate summary report: {e}")

def main():
    """Main function to orchestrate the eminence score generation."""
    # --- Load Defaults from Config ---
    default_input = get_config_value(APP_CONFIG, 'DataGeneration', 'eligible_candidates_input', 'data/intermediate/adb_eligible_candidates.txt')
    default_output = get_config_value(APP_CONFIG, 'DataGeneration', 'eminence_scores_output', 'data/foundational_assets/eminence_scores.csv')
    default_model = get_config_value(APP_CONFIG, 'DataGeneration', 'eminence_model', 'openai/gpt-4o')
    default_batch_size = get_config_value(APP_CONFIG, 'DataGeneration', 'eminence_batch_size', 100, value_type=int)

    parser = argparse.ArgumentParser(
        description="Generate eminence scores for ADB subjects using an LLM.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--sandbox-path", help="Specify a sandbox directory for all file operations.")
    parser.add_argument("--model", default=default_model, help="Name of the LLM to use for scoring. Default is from config.ini.")
    parser.add_argument("--batch-size", type=int, default=default_batch_size, help="Number of subjects per API call. Default is from config.ini.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file, starting from scratch.")
    parser.add_argument("--no-summary", action="store_true", help="Suppress the final summary report output.")
    parser.add_argument("--no-api-warning", action="store_true", help="Suppress the API cost warning.")
    args = parser.parse_args()

    # If a sandbox path is provided, set the environment variable.
    # This must be done before any other modules are used.
    if args.sandbox_path:
        os.environ['PROJECT_SANDBOX_PATH'] = os.path.abspath(args.sandbox_path)
    
    # Now that the environment is set, we can safely load modules that depend on it.
    from config_loader import get_path, PROJECT_ROOT
    
    # Load bypass_candidate_selection AFTER sandbox is established
    # If we have a sandbox path, read the config directly from there
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

    # --- Setup Paths ---
    script_dir = Path(__file__).parent
    input_path = Path(get_path(default_input))
    output_path = Path(get_path(default_output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # --- Temp files for worker ---
    # Use the sandbox path for the temp directory if it's active.
    base_temp_path = Path(args.sandbox_path) if args.sandbox_path else script_dir
    temp_dir = base_temp_path / "temp_eminence_worker"
    temp_dir.mkdir(exist_ok=True)
    temp_query_file = temp_dir / "query.txt"
    temp_response_file = temp_dir / "response.txt"
    temp_error_file = temp_dir / "error.txt"
    temp_config_file = temp_dir / "temp_config.ini"

    print(f"\n{Fore.YELLOW}--- Starting Eminence Score Generation ---{Fore.RESET}")

    # --- Intelligent Startup Logic (Stale Check) ---
    if not args.force and output_path.exists() and input_path.exists():
        if os.path.getmtime(input_path) > os.path.getmtime(output_path):
            print(f"{Fore.YELLOW}\nInput file '{input_path.name}' is newer than the existing output. Stale data detected.")
            print("Automatically re-running full selection process...")
            args.force = True

    # --- Handle --force flag ---
    if args.force and output_path.exists():
        backup_and_remove(output_path)

    # --- Load Data and Determine Scope ---
    processed_ids = load_processed_ids(output_path)
    all_subjects = load_subjects_to_process(input_path, processed_ids)

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
    elif not all_subjects and not args.force:
        display_path = os.path.relpath(output_path, PROJECT_ROOT)
        print(f"\n{Fore.YELLOW}Scores file at '{display_path}' is already up to date. ✨")
        
        # In interactive sessions, prompt the user for action.
        if sys.stdout.isatty():
            confirm = input("Do you wish to force a re-run anyway? (y/n): ").lower().strip()
            if confirm == 'y':
                print(f"{Fore.YELLOW}Forcing overwrite of existing output file...{Fore.RESET}")
                backup_and_remove(output_path)
                args.force = True # Set force to true for the rest of the script
            else:
                print(f"\n{Fore.YELLOW}Operation cancelled by user.{Fore.RESET}\n")
                sys.exit(0)
        # In non-interactive sessions, just report and exit.
        else:
            print("Regenerating summary report...")
            total_subjects_in_source = len(processed_ids)
            if not args.no_summary:
                generate_scores_summary(output_path, total_subjects_in_source)
            sys.exit(0)
    
    # Reload subjects if force was used, as the file state has changed
    if args.force:
        processed_ids = load_processed_ids(output_path)
        all_subjects = load_subjects_to_process(input_path, processed_ids)

    total_to_process = len(all_subjects)
    total_subjects_in_source = len(processed_ids) + total_to_process

    # Display a non-interactive warning if the script is proceeding automatically
    if not args.no_api_warning and total_to_process > 0 and not (output_path.exists() and not args.force and not 'is_stale' in locals()):
         print(f"\n{Fore.YELLOW}WARNING: This process will make LLM calls that will incur API transaction costs and could take some time (1.5 minutes or more for each set of 1,000 records).{Fore.RESET}")

    print(f"\n{Fore.YELLOW}--- Processing Scope ---{Fore.RESET}")
    print(f"Found {len(processed_ids):,} existing scores.")
    print(f"Processing {total_to_process:,} new subjects (out of {total_subjects_in_source:,} total).")
    
    # --- Create Temporary Config for Model Override ---
    temp_config = configparser.ConfigParser()
    if APP_CONFIG.has_section('LLM'): temp_config['LLM'] = APP_CONFIG['LLM']
    if APP_CONFIG.has_section('API'): temp_config['API'] = APP_CONFIG['API']
    if not temp_config.has_section('LLM'): temp_config.add_section('LLM')
    temp_config.set('LLM', 'model_name', args.model)
    with open(temp_config_file, 'w') as f: temp_config.write(f)

    # --- Main Batch Processing Loop ---
    processed_count = 0
    consecutive_failures = 0
    max_consecutive_failures = 3
    was_interrupted = False
    run_completed_successfully = False
    current_index = len(processed_ids) + 1

    try:
        total_batches = (total_to_process + args.batch_size - 1) // args.batch_size
        with tqdm(total=total_to_process, desc="Processing Batches", unit="subject", ncols=80) as pbar:
            for i in range(0, total_to_process, args.batch_size):
                batch = all_subjects[i:i + args.batch_size]
                batch_num = (i // args.batch_size) + 1
                pbar.set_description(f"Processing Batch {batch_num}/{total_batches}")

                subject_list_str = "\n".join([f'"{b["FirstName"]} {b["LastName"]}" ({b["Year"]}), ID {b["idADB"]}' for b in batch])
                prompt_text = EMINENCE_PROMPT_TEMPLATE.format(subject_list=subject_list_str)
                temp_query_file.write_text(prompt_text, encoding='utf-8')

                worker_cmd = [
                    sys.executable, str(script_dir / "llm_prompter.py"),
                    f"eminence_batch_{batch_num}", "--input_query_file", str(temp_query_file),
                    "--output_response_file", str(temp_response_file), "--output_error_file", str(temp_error_file),
                    "--config_path", str(temp_config_file), "--quiet"
                ]
                subprocess.run(worker_cmd, check=False)
                pbar.refresh()  # Force redraw of the main progress bar

                if temp_error_file.exists() and temp_error_file.stat().st_size > 0:
                    error_msg = temp_error_file.read_text(encoding='utf-8').strip()
                    tqdm.write(f"{Fore.RED}Worker failed for batch {batch_num}. Error: {error_msg}")
                    consecutive_failures += 1
                    if "401" in error_msg or "403" in error_msg:
                        tqdm.write(f"{Fore.RED}Halting due to a fatal API authentication error.")
                        break
                    if consecutive_failures >= max_consecutive_failures:
                        tqdm.write(f"{Fore.RED}Halting after {max_consecutive_failures} consecutive failures.")
                        break
                    continue
                
                consecutive_failures = 0
                response_text = temp_response_file.read_text(encoding='utf-8')
                raw_parsed_scores = parse_batch_response(response_text)
                
                # Filter out any duplicates returned by the LLM that have already been processed in this session.
                # `processed_ids` covers previous runs, this handles duplicates within the current run.
                batch_ids_seen = {score[0] for score in raw_parsed_scores}
                parsed_scores = []
                current_processed_ids = load_processed_ids(output_path)
                for score in raw_parsed_scores:
                    if score[0] not in current_processed_ids:
                        parsed_scores.append(score)

                if len(parsed_scores) < len(raw_parsed_scores):
                    num_dupes = len(raw_parsed_scores) - len(parsed_scores)
                    tqdm.write(f"{Fore.YELLOW}Warning: Skipped {num_dupes} duplicate subject(s) returned by the LLM in batch {batch_num}.")

                if len(parsed_scores) != len(batch_ids_seen):
                    tqdm.write(f"{Fore.YELLOW}Warning: Mismatch in scores for batch {batch_num}. Expected: {len(batch)}, Got: {len(parsed_scores)}.")
                if not parsed_scores:
                    tqdm.write(f"{Fore.RED}Error: Failed to parse any scores for batch {batch_num}.")
                    continue

                save_scores_to_csv(output_path, parsed_scores, current_index)
                processed_count += len(parsed_scores)
                current_index += len(parsed_scores)
                pbar.update(len(batch))
        
        run_completed_successfully = True
    except KeyboardInterrupt:
        was_interrupted = True
        print(f"\n\n{Fore.YELLOW}Process interrupted by user. Exiting gracefully.{Fore.RESET}")
    finally:
        print(f"\n{Fore.YELLOW}--- Finalizing ---{Fore.RESET}")
        sort_success = sort_and_reindex_scores(output_path)
        
        if not args.no_summary:
            generate_scores_summary(output_path, total_subjects_in_source)
        else:
            # When --no-summary is used, print a simple final report.
            from config_loader import PROJECT_ROOT
            display_path = os.path.relpath(output_path, PROJECT_ROOT).replace('\\', '/')
            total_scored = len(processed_ids) + processed_count

            print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
            if sort_success:
                print(f"{Fore.CYAN} - Eminence scores saved to: {display_path}{Fore.RESET}")
            
            if not sort_success:
                print(f"\n{Fore.RED}FAILURE: Sorting and re-indexing failed. The file may be in an inconsistent state.{Fore.RESET}\n")
            elif total_scored == 0 and total_subjects_in_source > 0:
                key_metric = f"Scored 0 of {total_subjects_in_source:,} subjects"
                print(f"\n{Fore.RED}FAILURE: {key_metric}. No scores were generated.{Fore.RESET}\n")
            else:
                key_metric = f"Scored {total_scored:,} of {total_subjects_in_source:,} subjects"
                print(f"\n{Fore.GREEN}SUCCESS: {key_metric}. Eminence scoring completed successfully. ✨{Fore.RESET}\n")

        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        # --- Final Reconciliation and Reporting ---
        # Determine which subjects were missed by the LLM.
        final_processed_ids = load_processed_ids(output_path)
        all_eligible_ids = {s['idADB'] for s in all_subjects} | processed_ids
        missing_ids = all_eligible_ids - final_processed_ids
        
        if missing_ids:
            missing_report_path = output_path.parent.parent / "reports" / "missing_eminence_scores.txt"
            missing_report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(missing_report_path, 'w', encoding='utf-8') as f:
                f.write("Subjects missed by LLM during eminence scoring:\n")
                for subject_id in sorted(missing_ids):
                    f.write(f"{subject_id}\n")
            tqdm.write(f"{Fore.YELLOW}Wrote report of {len(missing_ids)} missing subjects to '{missing_report_path}'.")

        # --- Final Reconciliation and Reporting ---
        final_processed_ids = load_processed_ids(output_path)
        all_eligible_ids = {s['idADB'] for s in all_subjects} | processed_ids
        missing_ids = all_eligible_ids - final_processed_ids
        
        if missing_ids:
            missing_report_path = output_path.parent.parent / "reports" / "missing_eminence_scores.txt"
            missing_report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(missing_report_path, 'w', encoding='utf-8') as f:
                f.write("Subjects missed by LLM during eminence scoring:\n")
                for subject_id in sorted(list(missing_ids)):
                    f.write(f"{subject_id}\n")
            
            logging.error(f"Failed to retrieve scores for {len(missing_ids)} subject(s). See '{missing_report_path}' for details.")
            logging.error("The pipeline will be halted. Please re-run the script to automatically retry the missing subjects.")
            sys.exit(1)

        if was_interrupted:
            logging.warning("Eminence score generation terminated by user. Re-run to continue. ✨\n")
        elif not run_completed_successfully:
            logging.critical("Eminence score generation halted due to critical errors. ✨\n")

if __name__ == "__main__":
    main()

# === End of src/generate_eminence_scores.py ===

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
# Filename: src/generate_eminence_scores.py

"""
Orchestrator to generate eminence scores for all eligible subjects using an LLM.

This script reads the pre-filtered list of eligible candidates, groups them into
batches, and invokes the `llm_prompter.py` worker to query a Large Language
Model (LLM) for a calibrated "eminence" score for each individual.

Key Features:
-   **Configuration Driven & Sandbox Aware**: Default input/output paths and
    model settings are managed in `config.ini`. The script is fully sandboxed
    via a `--sandbox-path` argument, ensuring all file operations can be
    isolated for testing.
-   **Resilient & Resumable**: Safely stops with Ctrl+C and resumes from the
    last completed batch on the next run.
-   **Calibrated Prompting**: Uses a sophisticated prompt with fixed historical
    anchors (e.g., Plato, Einstein) and 20th-century examples to force the
    LLM to use a consistent, absolute scale.
-   **Automated Reporting**: Upon completion or interruption, it automatically sorts
    the final data by score and generates a detailed summary report with
    descriptive statistics and a completion status.
-   **Safety First**: Halts with clear instructions if it detects an older,
    incompatible `eminence_scores.csv` format. A `--force` flag with a
    confirmation prompt and automatic backup allows for safe overwriting.

The final output is `eminence_scores.csv`, a foundational asset for all
downstream filtering and analysis, containing the headers: `Index`, `idADB`,
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

# Initialize colorama
init(autoreset=True)

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


def backup_and_overwrite(file_path: Path):
    """Creates a backup of a file before deleting the original to allow a fresh start."""
    from config_loader import get_path, PROJECT_ROOT
    try:
        backup_dir = Path(get_path('data/backup'))
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{file_path.name}.{timestamp}.bak"
        shutil.copy2(file_path, backup_path)
        display_backup_path = os.path.relpath(backup_path, PROJECT_ROOT)
        print(f"\n{Fore.CYAN}Created backup of existing file at: {display_backup_path}{Fore.RESET}")
        file_path.unlink()
        display_path = os.path.relpath(file_path, PROJECT_ROOT)
        print(f"\n{Fore.YELLOW}--- Starting Fresh Run ---{Fore.RESET}")
        print(f"Removed existing file: {display_path}")
    except (IOError, OSError) as e:
        logging.error(f"{Fore.RED}Failed to create backup or remove file: {e}")
        sys.exit(1)

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
    except (IOError, csv.Error) as e:
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

def sort_and_reindex_scores(filepath: Path):
    """Sorts the scores file by EminenceScore (desc) and re-applies the Index."""
    if not filepath.exists() or filepath.stat().st_size == 0:
        return

    try:
        # Using pandas is the most robust way to handle large CSV sorting
        import pandas as pd
        df = pd.read_csv(filepath)

        # Ensure EminenceScore is numeric for correct sorting
        df['EminenceScore'] = pd.to_numeric(df['EminenceScore'], errors='coerce')
        df.dropna(subset=['EminenceScore'], inplace=True)
        
        # Sort by score descending, then by name ascending as a tie-breaker
        df.sort_values(by=['EminenceScore', 'Name'], ascending=[False, True], inplace=True)
        
        # Re-index the 'Index' column from 1 to N
        df['Index'] = range(1, len(df) + 1)
        
        # Save the sorted file, overwriting the original
        df.to_csv(filepath, index=False, float_format='%.2f')
        print(f"Successfully sorted and re-indexed '{filepath.name}'.")

    except ImportError:
        logging.warning("Pandas not installed. Skipping sorting. Install with 'pdm add pandas'.")
    except Exception as e:
        logging.error(f"Could not sort scores file: {e}")

def generate_scores_summary(filepath: Path, total_subjects_overall: int):
    """Generates a summary report from the final scores file."""
    if not filepath.exists() or filepath.stat().st_size == 0:
        print("\n--- Summary Report ---")
        print("Output file is empty. No summary to generate.")
        return

    summary_path = filepath.parent / f"{filepath.stem}_summary.txt"
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
        
        report.extend(["\n--- Descriptive Statistics ---",
                       f"  Mean:          {stats['mean']:>8.2f}", f"  Std Dev:       {stats['std']:>8.2f}",
                       f"  Min:           {stats['min']:>8.2f}", f"  25% (Q1):      {stats['25%']:>8.2f}",
                       f"  50% (Median):  {stats['50%']:>8.2f}", f"  75% (Q3):      {stats['75%']:>8.2f}",
                       f"  Max:           {stats['max']:>8.2f}"])
        
        report.append("\n--- Score Distribution ---")
        for label, count in distribution.items():
            report.append(f"  {label:<10}: {count:>{5},d} ({count/total_scored:7.2%})")

        report.append("\n--- Top 10 Most Eminent ---")
        for _, row in top_10.iterrows():
            report.append(f"  {row['EminenceScore']:>5.2f} - {row['Name']}")
        report.append(banner)

        completion_pct = (total_scored / total_subjects_overall) * 100 if total_subjects_overall > 0 else 0
        status_line = f"Completion: {total_scored}/{total_subjects_overall} ({completion_pct:.2f}%)"
        if completion_pct > 99.5:
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
        display_scores_path = os.path.relpath(filepath, PROJECT_ROOT)
        display_summary_path = os.path.relpath(summary_path, PROJECT_ROOT)

        print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
        print(f"{Fore.CYAN} - Eminence scores saved to: {display_scores_path}{Fore.RESET}")
        print(f"{Fore.CYAN} - Summary report saved to: {display_summary_path}{Fore.RESET}")

        key_metric = f"Scored {total_scored:,} of {total_subjects_overall:,} subjects"
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
    args = parser.parse_args()

    # If a sandbox path is provided, set the environment variable.
    # This must be done before any other modules are used.
    if args.sandbox_path:
        os.environ['PROJECT_SANDBOX_PATH'] = os.path.abspath(args.sandbox_path)
    
    # Now that the environment is set, we can safely load modules that depend on it.
    from config_loader import get_path, PROJECT_ROOT
    
    # Load bypass_scoring AFTER sandbox is established
    # If we have a sandbox path, read the config directly from there
    if args.sandbox_path:
        import configparser
        sandbox_config_path = Path(args.sandbox_path) / "config.ini"
        if sandbox_config_path.exists():
            sandbox_config = configparser.ConfigParser()
            sandbox_config.read(sandbox_config_path)
            bypass_scoring = sandbox_config.get("DataGeneration", "bypass_llm_scoring", fallback="false").lower() == 'true'
        else:
            bypass_scoring = False
    else:
        bypass_scoring = get_config_value(APP_CONFIG, "DataGeneration", "bypass_llm_scoring", "false").lower() == 'true'

    # --- Setup Paths ---
    script_dir = Path(__file__).parent
    input_path = Path(get_path(default_input))
    output_path = Path(get_path(default_output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # --- Temp files for worker ---
    temp_dir = script_dir / "temp_eminence_worker"
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
            backup_and_overwrite(output_path)
            args.force = True

    # --- Load Data and Determine Scope ---
    processed_ids = load_processed_ids(output_path)
    all_subjects = load_subjects_to_process(input_path, processed_ids)

    # --- Main Logic Branching ---
    # First, handle the bypass case.
    if bypass_scoring and not args.force:
        print(f"\n{Fore.RED}BYPASS ACTIVE: The 'bypass_llm_scoring' flag is set to true in config.ini.{Fore.RESET}")
        print(f"{Fore.YELLOW}The scores generated by this script will be IGNORED by the downstream 'select_final_candidates.py' script.{Fore.RESET}")
        if sys.stdout.isatty():
            confirm = input("Do you wish to proceed anyway? (y/n): ").lower().strip()
            if confirm != 'y':
                print(f"\n{Fore.YELLOW}Operation cancelled by user.{Fore.RESET}\n")
                sys.exit(0)
    
    # If not bypassing, check if the file is already up-to-date.
    elif not all_subjects and not args.force:
        display_path = os.path.relpath(output_path, PROJECT_ROOT)
        print(f"\n{Fore.YELLOW}WARNING: The scores file at '{display_path}' is already up to date. ✨")
        print(f"{Fore.YELLOW}The update process incurs API costs and can take some time to complete.")
        print(f"{Fore.YELLOW}If you decide to go ahead with recreating the eminence scores, a backup of the existing file will be created first.{Fore.RESET}")
        confirm = input("Do you wish to proceed? (Y/N): ").lower().strip()
        if confirm == 'y':
            backup_and_overwrite(output_path)
            args.force = True
            processed_ids = load_processed_ids(output_path)
            all_subjects = load_subjects_to_process(input_path, processed_ids)
        else:
            print(f"\n{Fore.YELLOW}Operation cancelled by user.{Fore.RESET}\n")
            sys.exit(0)
    
    if args.force and output_path.exists():
        backup_and_overwrite(output_path)
        processed_ids = load_processed_ids(output_path)
        all_subjects = load_subjects_to_process(input_path, processed_ids)

    total_to_process = len(all_subjects)
    total_subjects_in_source = len(processed_ids) + total_to_process

    # Display a non-interactive warning if the script is proceeding automatically
    if total_to_process > 0 and not (output_path.exists() and not args.force and not 'is_stale' in locals()):
         print(f"\n{Fore.YELLOW}WARNING: This process will make LLM calls that will take some time and incur API transaction costs.{Fore.RESET}")

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
        for i in range(0, total_to_process, args.batch_size):
            batch = all_subjects[i:i + args.batch_size]
            batch_num = (i // args.batch_size) + 1
            total_batches = (total_to_process + args.batch_size - 1) // args.batch_size

            print(f"\n{Fore.CYAN}--- Processing Batch {batch_num} of {total_batches} ---{Fore.RESET}")
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

            if temp_error_file.exists() and temp_error_file.stat().st_size > 0:
                error_msg = temp_error_file.read_text(encoding='utf-8')
                logging.error(f"Worker failed for batch {batch_num}. Error: {error_msg.strip()}")
                consecutive_failures += 1
                if "401" in error_msg or "403" in error_msg or "Unauthorized" in error_msg or "Forbidden" in error_msg:
                    logging.critical("Halting due to a fatal API authentication/authorization error.")
                    break
                if consecutive_failures >= max_consecutive_failures:
                    logging.critical(f"Halting after {max_consecutive_failures} consecutive batch failures.")
                    break
                temp_error_file.unlink()
                continue
            
            if not temp_response_file.exists():
                logging.error(f"Worker did not produce a response file for batch {batch_num}.")
                consecutive_failures += 1
                continue
            
            consecutive_failures = 0
            response_text = temp_response_file.read_text(encoding='utf-8')
            parsed_scores = parse_batch_response(response_text)

            if len(parsed_scores) != len(batch):
                logging.warning(f"LLM did not return the correct number of scores for batch {batch_num}. Expected: {len(batch)}, Got: {len(parsed_scores)}. Saving what was returned.")
            if not parsed_scores:
                logging.error(f"Failed to parse any scores from the LLM response for batch {batch_num}.")
                continue

            save_scores_to_csv(output_path, parsed_scores, current_index)
            processed_count += len(parsed_scores)
            current_index += len(parsed_scores)
            
            print(f"Successfully processed and saved {len(parsed_scores)} scores for batch {batch_num}.")
            session_progress = f"Session: {processed_count}/{total_to_process}"
            overall_progress = f"Overall: {len(processed_ids) + processed_count}/{total_subjects_in_source}"
            print(f"{session_progress} | {overall_progress}")
            time.sleep(1)
        
        run_completed_successfully = True
    except KeyboardInterrupt:
        was_interrupted = True
        print(f"\n\n{Fore.YELLOW}Process interrupted by user. Exiting gracefully.{Fore.RESET}")
    finally:
        print(f"\n{Fore.YELLOW}--- Finalizing ---{Fore.RESET}")
        sort_and_reindex_scores(output_path)
        generate_scores_summary(output_path, total_subjects_in_source)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        if was_interrupted:
            logging.warning("Eminence score generation terminated by user. Re-run to continue. ✨\n")
        elif not run_completed_successfully:
            logging.critical("Eminence score generation halted due to critical errors. ✨\n")

if __name__ == "__main__":
    main()

# === End of src/generate_eminence_scores.py ===

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

This script reads the pre-filtered `adb_eligible_candidates.txt` file, which
contains only high-quality subjects, groups them into batches, and invokes the
`llm_prompter.py` worker to query a Large Language Model (LLM) for a
calibrated "eminence" score for each individual.

Key Features:
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
                    # Legacy format detected. Halt with instructions.
                    logging.critical("Incompatible legacy file format detected.")
                    logging.error(f"The existing file '{filepath}' uses the old 'ARN' column.")
                    logging.error("The new script requires an 'idADB' column to function correctly.")
                    print("\nTo fix this, you have two options:")
                    print(f"  1. Manually rename or delete the old file: '{filepath}'")
                    print(f"  2. Re-run the script with the {Fore.CYAN}--force{Fore.RESET} flag to automatically back up and overwrite it.")
                    sys.exit(1)
                else:
                    # Header is malformed.
                    logging.critical("Malformed CSV header.")
                    logging.error(f"Could not find required 'idADB' column in '{filepath}'.")
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
        logging.info(f"Successfully sorted and re-indexed '{filepath.name}'.")

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

        report = ["="*50, "Eminence Scores Summary".center(50), "="*50]
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
        report.append("="*50)

        completion_pct = (total_scored / total_subjects_overall) * 100 if total_subjects_overall > 0 else 0
        status_line = f"Completion: {total_scored}/{total_subjects_overall} ({completion_pct:.2f}%)"
        if completion_pct > 99.5:
            report.append(f"\n{Fore.GREEN}SUCCESS - {status_line}")
        elif completion_pct >= 95.0:
            report.append(f"\n{Fore.YELLOW}WARNING - {status_line}")
        else:
            report.append(f"\n{Fore.RED}ERROR - {status_line} - Significantly incomplete.")

        summary_content = "\n".join(report)
        summary_path.write_text(summary_content, encoding='utf-8')
        print(f"\n{summary_content}\n")
        logging.info(f"Summary report saved to '{summary_path.name}'.")

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
    parser.add_argument("-i", "--input-file", default=default_input, help="Path to the pre-filtered eligible candidates file. Default is from config.ini.")
    parser.add_argument("-o", "--output-file", default=default_output, help="Path for the output CSV file. Default is from config.ini.")
    parser.add_argument("--model", default=default_model, help="Name of the LLM to use for scoring. Default is from config.ini.")
    parser.add_argument("--batch-size", type=int, default=default_batch_size, help="Number of subjects per API call. Default is from config.ini.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file, starting from scratch.")
    args = parser.parse_args()

    # --- Setup Paths ---
    script_dir = Path(__file__).parent
    input_path = Path(args.input_file)
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # --- Temp files for worker ---
    temp_dir = script_dir / "temp_eminence_worker"
    temp_dir.mkdir(exist_ok=True)
    temp_query_file = temp_dir / "query.txt"
    temp_response_file = temp_dir / "response.txt"
    temp_error_file = temp_dir / "error.txt"
    temp_config_file = temp_dir / "temp_config.ini"

    print(f"\n{Fore.YELLOW}--- Starting Eminence Score Generation ---{Fore.RESET}")

    # --- Handle Overwrite with Backup and Confirmation ---
    proceed = True
    if output_path.exists():
        if not args.force:
            print(f"\n{Fore.YELLOW}WARNING: The output file '{output_path}' already exists.")
            print(f"This process incurs API costs and can take over 30 minutes to complete.{Fore.RESET}")
            confirm = input("A backup will be created. Are you sure you want to continue? (Y/N): ").lower().strip()
            if confirm != 'y':
                proceed = False
        
        if proceed:
            try:
                backup_dir = Path('data/backup')
                backup_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"{output_path.name}.{timestamp}.bak"
                shutil.copy2(output_path, backup_path)
                logging.info(f"Created backup of existing file at: {backup_path}")
                output_path.unlink()
                logging.warning(f"Removed existing file to start fresh: {output_path.name}")
            except (IOError, OSError) as e:
                logging.error(f"{Fore.RED}Failed to create backup or remove file: {e}")
                sys.exit(1)
        else:
            print("\nOperation cancelled by user.\n")
            sys.exit(0)

    # --- Load Data and Create To-Do List ---
    processed_ids = load_processed_ids(output_path)
    all_subjects = load_subjects_to_process(input_path, processed_ids)

    total_to_process = len(all_subjects)
    total_subjects_in_source = len(processed_ids) + total_to_process
    logging.info(f"Found {len(processed_ids):,} existing scores. Processing {total_to_process:,} new subjects out of {total_subjects_in_source:,} total.")

    if not all_subjects:
        print(f"\n{Fore.GREEN}All subjects have already been processed. Nothing to do. ✨\n")

    # --- Create Temporary Config for Model Override ---
    # Create a new config parser and copy all relevant sections from the global config.
    temp_config = configparser.ConfigParser()
    if APP_CONFIG.has_section('LLM'):
        temp_config['LLM'] = APP_CONFIG['LLM']
    if APP_CONFIG.has_section('API'):
        temp_config['API'] = APP_CONFIG['API']

    # Now, override the model name with the one from the script's arguments.
    if not temp_config.has_section('LLM'):
        temp_config.add_section('LLM')
    temp_config.set('LLM', 'model_name', args.model)
    
    with open(temp_config_file, 'w') as f:
        temp_config.write(f)

    # --- Main Batch Processing Loop ---
    processed_count = 0
    consecutive_failures = 0
    max_consecutive_failures = 3
    was_interrupted = False
    run_completed_successfully = False

    # Initialize the starting index for new entries. The final sort will re-index
    # from 1, but this keeps the index column consistent during generation.
    current_index = len(processed_ids) + 1

    try:
        for i in range(0, total_to_process, args.batch_size):
            batch = all_subjects[i:i + args.batch_size]
            batch_num = (i // args.batch_size) + 1
            total_batches = (total_to_process + args.batch_size - 1) // args.batch_size

            print(f"\n{Fore.CYAN}--- Processing Batch {batch_num} of {total_batches} ---{Fore.RESET}")

            # 1. Construct prompt
            subject_list_str = "\n".join([f'"{b["FirstName"]} {b["LastName"]}" ({b["Year"]}), ID {b["idADB"]}' for b in batch])
            prompt_text = EMINENCE_PROMPT_TEMPLATE.format(batch_size=len(batch), subject_list=subject_list_str)
            temp_query_file.write_text(prompt_text, encoding='utf-8')

            # 2. Call LLM worker
            worker_cmd = [
                sys.executable, str(script_dir / "llm_prompter.py"),
                f"eminence_batch_{batch_num}",
                "--input_query_file", str(temp_query_file),
                "--output_response_file", str(temp_response_file),
                "--output_error_file", str(temp_error_file),
                "--config_path", str(temp_config_file),
                "--quiet"
            ]

            subprocess.run(worker_cmd, check=False)

            # 3. Process response
            if temp_error_file.exists() and temp_error_file.stat().st_size > 0:
                error_msg = temp_error_file.read_text(encoding='utf-8')
                logging.error(f"Worker failed for batch {batch_num}. Error: {error_msg.strip()}")
                consecutive_failures += 1
                
                # Fast-fail for critical errors
                if "401" in error_msg or "403" in error_msg or "Unauthorized" in error_msg or "Forbidden" in error_msg:
                    logging.critical("Halting due to a fatal API authentication/authorization error.")
                    break
                if consecutive_failures >= max_consecutive_failures:
                    logging.critical(f"Halting after {max_consecutive_failures} consecutive batch failures.")
                    break
                
                temp_error_file.unlink() # Clean up error file before next iteration
                continue

            if not temp_response_file.exists():
                logging.error(f"Worker did not produce a response file for batch {batch_num}.")
                consecutive_failures += 1
                continue
            
            # Reset failure count on a successful call
            consecutive_failures = 0

            response_text = temp_response_file.read_text(encoding='utf-8')
            parsed_scores = parse_batch_response(response_text)

            if len(parsed_scores) != len(batch):
                logging.warning(f"LLM did not return the correct number of scores for batch {batch_num}. "
                                f"Expected: {len(batch)}, Got: {len(parsed_scores)}. Saving what was returned.")

            if not parsed_scores:
                logging.error(f"Failed to parse any scores from the LLM response for batch {batch_num}.")
                continue

            # 4. Save results
            save_scores_to_csv(output_path, parsed_scores, current_index)
            processed_count += len(parsed_scores)
            current_index += len(parsed_scores)
            
            print(f"Successfully processed and saved {len(parsed_scores)} scores for batch {batch_num}.")
            session_progress = f"Session: {processed_count}/{total_to_process}"
            overall_progress = f"Overall: {len(processed_ids) + processed_count}/{total_subjects_in_source}"
            print(f"{session_progress} | {overall_progress}")
            time.sleep(1)
        
        # If the script reaches this point without a critical error or interruption,
        # the run is considered successful, even if no new records were processed.
        run_completed_successfully = True

    except KeyboardInterrupt:
        was_interrupted = True
        print(f"\n\n{Fore.YELLOW}Process interrupted by user. Exiting gracefully.{Fore.RESET}")
    finally:
        # --- Final Processing and Cleanup ---
        print("\n--- Finalizing ---")
        sort_and_reindex_scores(output_path)
        generate_scores_summary(output_path, total_subjects_in_source)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        final_scored_count = len(processed_ids) + processed_count
        
        if run_completed_successfully:
            if final_scored_count < total_subjects_in_source:
                missing_count = total_subjects_in_source - final_scored_count
                logging.warning("Eminence score generation complete for this run.")
                logging.warning(f"Re-run the script to process the {missing_count} missing subjects. ✨\n")
            else:
                print(f"\n{Fore.GREEN}Eminence score generation completed successfully. All subjects processed. ✨\n")
        elif not was_interrupted:
            # If not interrupted, it must have been a critical error break
            logging.critical("Eminence score generation halted due to critical errors. ✨\n")
        else:
            # It was a user interruption
            logging.warning("Eminence score generation terminated by user. Re-run to continue. ✨\n")

if __name__ == "__main__":
    main()

# === End of src/generate_eminence_scores.py ===

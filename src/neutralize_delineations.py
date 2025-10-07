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
# Filename: src/neutralize_delineations.py

"""
Automates the neutralization of the raw astrological delineation library.

This script reads the raw, esoteric interpretation text from Solar Fire,
intelligently filters and groups related items, and uses an LLM to rewrite
each group into neutral, psychological descriptions.

The final output is a set of CSV files, one for each group, containing the
neutralized key-value pairs ready for use in database generation.
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
from typing import Dict, List

from colorama import Fore, init
from tqdm import tqdm

# Initialize colorama, forcing it not to strip ANSI codes when piped
init(autoreset=True, strip=False)

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(message)s")

# --- Config Loader ---
try:
    from config_loader import APP_CONFIG, get_config_value
    from utils.file_utils import backup_and_remove
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from config_loader import APP_CONFIG, get_config_value
    from utils.file_utils import backup_and_remove


# --- Prompt Template ---
NEUTRALIZE_PROMPT_TEMPLATE = """
Revise the attached text. You MUST follow these rules:
1.  Lines starting with an asterisk (*) are headings. Do NOT revise them; they must remain intact.
2.  Remove all references to astrology, astronomy, time periods, and generations.
3.  Shift the perspective to an impersonal, objective, neutral third-person style.
4.  Do NOT use phrases like "You are," "One sees oneself," "Individuals with this configuration," or any phrasing that refers to "a person." Describe the trait directly.
5.  Correct for grammar and spelling.
6.  Preserve the core psychological meaning of the original text.
7.  Your entire response must be ONLY the revised text block in the same format as the original. Do not add any commentary.

**Example of Style:**
-   **Original:** "This placement means that you are a highly-motivated person with many goals."
-   **Correct Style:** "Highly motivated with many goals."

---
{delineation_block}
---
"""

# --- Filtering and Grouping Logic ---
# These functions define which delineations are selected and how they are grouped.
# This approach ensures only the required texts are processed.

def is_balance_delineation(key: str) -> bool:
    """Selects only 'Strong' or 'Weak' balance delineations."""
    return "Strong" in key or "Weak" in key

def get_points_in_signs_delineations(all_dels: Dict[str, str], points: List[str]) -> Dict[str, str]:
    """Selects delineations for specific points in signs."""
    selected = {}
    for point in points:
        for sign in ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]:
            key = f"{point} in {sign}"
            if key in all_dels:
                selected[key] = all_dels[key]
    return selected

def group_delineations(all_dels: Dict[str, str], points: List[str]) -> Dict[str, Dict[str, str]]:
    """Groups filtered delineations into their target output files."""
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    sign_balance_keys = {f"{sign} {balance}" for sign in signs for balance in ["Strong", "Weak"]}

    groups = {
        "balances_quadrants.csv": {k: v for k, v in all_dels.items() if k.startswith("Quadrant") and is_balance_delineation(k)},
        "balances_hemispheres.csv": {k: v for k, v in all_dels.items() if k.startswith("Hemisphere") and is_balance_delineation(k)},
        "balances_elements.csv": {k: v for k, v in all_dels.items() if k.startswith("Element") and is_balance_delineation(k)},
        "balances_modes.csv": {k: v for k, v in all_dels.items() if k.startswith("Mode") and is_balance_delineation(k)},
        "balances_signs.csv": {k: v for k, v in all_dels.items() if k in sign_balance_keys},
        "points_in_signs.csv": get_points_in_signs_delineations(all_dels, points),
    }
    return groups


def parse_sf_content(content_lines: List[str]) -> Dict[str, str]:
    """Parses a list of lines from a Solar Fire report into a dictionary."""
    delineations = {}
    current_key = None
    current_text = []

    for line in content_lines:
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith(";"):
            continue

        if stripped_line.startswith("*"):
            if current_key:
                delineations[current_key] = " ".join(current_text).strip()
            current_key = stripped_line[1:].strip()
            current_text = []
        elif current_key:
            cleaned_line = stripped_line.replace("|", " ").strip()
            if cleaned_line:
                current_text.append(cleaned_line)

    if current_key:
        delineations[current_key] = " ".join(current_text).strip()
    return delineations


def parse_llm_response(response_filepath: Path) -> Dict[str, str]:
    """
    Reads and parses a delineation file (*Key / Text format) into a dictionary.
    """
    if not response_filepath.exists():
        return {}
    
    lines = response_filepath.read_text(encoding="utf-8", errors="ignore").splitlines()
    return parse_sf_content(lines)


def save_group_to_csv(filepath: Path, data: Dict[str, str]):
    """Saves a group of key-value delineations to a CSV file with all fields quoted."""
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        for key, text in data.items():
            writer.writerow([key, text])


def append_to_csv(filepath: Path, data: Dict[str, str]):
    """Appends key-value delineations to a CSV file with all fields quoted."""
    with open(filepath, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        for key, text in data.items():
            writer.writerow([key, text])


def resort_csv_by_key_order(filepath: Path, key_order: List[str]):
    """Sorts a 2-column CSV file based on a provided list of keys."""
    if not filepath.exists():
        return
    
    # Create a map for efficient lookups: {key: index}
    sort_map = {key: i for i, key in enumerate(key_order)}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        # Read all rows into memory for sorting
        rows = list(reader)

    # Sort the rows based on the key's index in the sort_map
    # Use a large number for keys not found to push them to the end.
    rows.sort(key=lambda row: sort_map.get(row[0], float('inf')))

    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerows(rows)


def get_processed_keys_from_csv(filepath: Path) -> set:
    """Reads a delineation CSV and returns a set of keys already processed."""
    if not filepath.exists():
        return set()
    processed_keys = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    processed_keys.add(row[0])
    except (IOError, csv.Error):
        return set()
    return processed_keys


def get_task_group(task: Dict) -> str:
    """Determines the display group for a given processing task."""
    task_type = task.get('type', '')
    task_name = task.get('name', '')

    if 'balance' in task_type:
        return "Balance Delineations"
    
    if 'point' in task_type:
        # Extracts 'Sun' from 'Sun in Aries' or 'Sun in Signs'
        point = task_name.split(' in ')[0]
        if point in ["Sun", "Moon"]:
            return f"The {point} in Signs"
        return f"{point} in Signs"

    return "Miscellaneous Tasks"


def main():
    """Main function to orchestrate the neutralization process."""
    os.system('')
    # --- Config and Arguments ---
    default_model = get_config_value(APP_CONFIG, "DataGeneration", "neutralization_model", "anthropic/claude-3.5-sonnet")
    default_points_str = "Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Ascendant, Midheaven"
    points_to_process = get_config_value(APP_CONFIG, "DataGeneration", "points_for_neutralization", default_points_str)
    points_list = [p.strip() for p in points_to_process.split(',')]
    
    parser = argparse.ArgumentParser(description="Neutralize raw astrological delineations using an LLM.")
    parser.add_argument("--sandbox-path", type=str, help="Path to the sandbox directory for testing.")
    parser.add_argument("--model", default=default_model)
    parser.add_argument("--force", action="store_true", help="Force re-processing of all groups.")
    parser.add_argument("--fast", action="store_true", help="Use bundled API calls for faster initial processing.")
    parser.add_argument("--debug-task", type=str, default=None, help="Debug a specific task (e.g., 'Sun in Aries', 'Quadrants'). Prints prompt/response and exits.")
    parser.add_argument("--bypass-llm", action="store_true", help="Bypass LLM and write original text to output files for testing.")
    args = parser.parse_args()
    
    if args.sandbox_path:
        # If the sandbox argument is explicitly given, set the env var.
        os.environ["PROJECT_SANDBOX_PATH"] = args.sandbox_path
    else:
        # For a normal run, guarantee we are not using a sandbox path
        # by unsetting any lingering environment variable from a previous test run.
        if "PROJECT_SANDBOX_PATH" in os.environ:
            del os.environ["PROJECT_SANDBOX_PATH"]
    
    from config_loader import get_path

    # --- File Handling Paths ---
    input_path = Path(get_path("data/foundational_assets/sf_delineations_library.txt"))
    output_dir = Path(get_path("data/foundational_assets/neutralized_delineations"))

    # --- LLM Bypass Workflow (for testing) ---
    # This block MUST come before any other file operations to prevent the --force
    # flag from deleting the test directory before this can run.
    if args.bypass_llm:
        print(f"\n{Fore.YELLOW}--- LLM Bypass Mode Activated ---")
        print("Writing original delineation text directly to output files...")
        
        if not input_path.exists():
            logging.error(f"\n{Fore.RED}FATAL: Input file not found for bypass: {input_path}\n")
            sys.exit(1)
        
        # The pytest fixture is responsible for creating a clean directory.
        # This script just ensures it exists before writing to it.
        output_dir.mkdir(parents=True, exist_ok=True)

        all_delineations = parse_llm_response(input_path)
        grouped_delineations = group_delineations(all_delineations, points_list)
        
        for filename, data in grouped_delineations.items():
            if data:
                save_group_to_csv(output_dir / filename, data)
        
        print(f"\n{Fore.GREEN}SUCCESS: Original delineations successfully written to '{output_dir}'.{Fore.RESET}\n")
        sys.exit(0)

    # --- Regular Workflow File Check ---
    if not input_path.exists():
        logging.error(f"\n{Fore.RED}FATAL: Input file not found: {input_path}\n")
        sys.exit(1)

    # --- Intelligent Startup Logic (Stale Check) ---
    if not args.force and output_dir.exists() and input_path.exists():
        if os.path.getmtime(input_path) > os.path.getmtime(output_dir):
            print(f"{Fore.YELLOW}\nInput file '{input_path.name}' is newer than the existing output. Stale data detected.")
            print("Automatically re-running full neutralization process...")
            args.force = True

    # --- Handle --force flag ---
    if args.force and output_dir.exists() and not args.bypass_llm:
        # If running interactively, provide a clear warning about the destructive action.
        # The --force flag serves as confirmation, so we do not prompt.
        if sys.stdout.isatty():
            print(f"\n{Fore.YELLOW}WARNING: The --force flag is active. This will overwrite all neutralized delineations.")
            print(f"This process incurs API costs and can take 10+ minutes to complete.{Fore.RESET}")

        backup_and_remove(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    
    # --- Worker Setup ---
    script_dir, temp_dir = Path(__file__).parent, Path(__file__).parent / "temp_neutralize_worker"
    temp_dir.mkdir(exist_ok=True)
    temp_config = configparser.ConfigParser()
    if APP_CONFIG.has_section('LLM'): temp_config['LLM'] = APP_CONFIG['LLM']
    if APP_CONFIG.has_section('API'): temp_config['API'] = APP_CONFIG['API']
    if not temp_config.has_section('LLM'): temp_config.add_section('LLM')
    temp_config.set('LLM', 'model_name', args.model)
    with open(temp_dir / "temp_config.ini", 'w') as f: temp_config.write(f)

    print(f"\n{Fore.YELLOW}--- Starting Delineation Neutralization ---")
    all_delineations = parse_llm_response(input_path)
    grouped_delineations = group_delineations(all_delineations, points_list)
    points_in_signs_master_order = list(get_points_in_signs_delineations(all_delineations, points_list).keys())

    # --- Dynamically build the list of tasks to run ---
    tasks_to_run = []
    points_output_path = output_dir / "points_in_signs.csv"

    if args.fast:
        tqdm.write("Running in --fast mode: tasks are bundled for speed.")
        all_balances_data = {}
        for filename, data in grouped_delineations.items():
            if filename != "points_in_signs.csv":
                all_balances_data.update(data)
        if all_balances_data:
            tasks_to_run.append({'type': 'balance_bundle', 'name': 'All Balances', 'data': all_balances_data})
        
        for point in points_list:
            point_dels = {k: v for k, v in grouped_delineations["points_in_signs.csv"].items() if k.startswith(point)}
            if point_dels:
                tasks_to_run.append({'type': 'point_bundle', 'name': f"{point} in Signs", 'data': point_dels})
        if points_output_path.exists(): points_output_path.unlink()

    else:
        for filename, data in grouped_delineations.items():
            if filename != "points_in_signs.csv":
                # Only create a task if there is data to process
                if data and (args.force or not (output_dir / filename).exists()):
                    tasks_to_run.append({'type': 'balance', 'name': filename.replace('.csv','').replace('balances_',''), 'filename': filename, 'data': data})
        
        processed_keys = set() if args.force else get_processed_keys_from_csv(points_output_path)
        if args.force and points_output_path.exists(): points_output_path.unlink()
        for key, text in grouped_delineations["points_in_signs.csv"].items():
            if key not in processed_keys:
                tasks_to_run.append({'type': 'point_in_sign', 'name': key, 'data': {key: text}})

    # --- Report on file status before processing ---
    all_output_files = list(grouped_delineations.keys())
    existing_files, generating_files = [], []

    for filename in all_output_files:
        filepath = output_dir / filename
        if not filepath.exists():
            if grouped_delineations.get(filename): # Only list if there's data for it
                generating_files.append(filename)
            continue

        if filename == "points_in_signs.csv":
            processed_count = len(get_processed_keys_from_csv(filepath))
            total_count = len(points_in_signs_master_order)
            if processed_count < total_count:
                generating_files.append(f"{filename} (Incomplete: {processed_count}/{total_count}, will append)")
            else:
                existing_files.append(f"{filename} (Complete)")
        else:
            existing_files.append(filename)

    if existing_files:
        print(f"\n{Fore.CYAN}Found {len(existing_files)} existing/complete file(s) that will be skipped:{Fore.RESET}")
        for f in sorted(existing_files):
            print(f"  - {f}")
    
    if generating_files and tasks_to_run:
        print(f"\n{Fore.CYAN}Will generate/update the following file(s):{Fore.RESET}")
        for f in sorted(generating_files):
            print(f"  - {f}")

    processed_count, failed_count = 0, 0
    resorting_needed = False
    
    # --- Dedicated Debug Workflow ---
    if args.debug_task:
        task_found = False
        for task in tasks_to_run:
            if args.debug_task.lower() == task['name'].lower():
                print(f"--- DEBUG MODE: ISOLATING TASK '{task['name']}' ---")
                block = "\n".join([f"*{k}\n{v}" for k, v in task['data'].items()])
                prompt = NEUTRALIZE_PROMPT_TEMPLATE.format(delineation_block=block)
                debug_and_exit(prompt, run_llm_worker(script_dir, temp_dir, "debug_task", prompt), None, temp_dir)
                task_found = True
                break
        if not task_found:
            print(f"{Fore.RED}Debug task '{args.debug_task}' not found in tasks to be processed.{Fore.RESET}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        sys.exit(0)

    # --- Main Processing Workflow ---
    if not tasks_to_run:
        print(f"\n{Fore.GREEN}All delineation files are already up to date. Nothing to do. ✨{Fore.RESET}\n")
        sys.exit(0)
        
    print(f"\n{Fore.YELLOW}WARNING: This process will make LLM calls incurring API transaction costs and could take an hour or more to complete.{Fore.RESET}")

    is_interactive = sys.stdout.isatty()

    try:
        if is_interactive:
            with tqdm(total=len(tasks_to_run), desc="Processing Tasks", ncols=100) as pbar:
                current_header_group = None
                for task in tasks_to_run:
                    task_group = get_task_group(task)
                    if task_group != current_header_group:
                        if current_header_group is not None:
                            tqdm.write("") # Add separation
                        tqdm.write(f"{Fore.CYAN}--- {task_group} ---{Fore.RESET}")
                        current_header_group = task_group

                    task_msg = f"  - Neutralizing {task['name']}..."
                    tqdm.write(task_msg)
                    
                    block = "\n".join([f"*{k}\n{v}" for k, v in task['data'].items()])
                    prompt = NEUTRALIZE_PROMPT_TEMPLATE.format(delineation_block=block)
                    
                    response, error = run_llm_worker(script_dir, temp_dir, task['name'], prompt)
                    
                    success = False
                    if response:
                        parsed = parse_llm_response(response)
                        if len(parsed) == len(task['data']):
                            success = True
                            if task['type'] == 'balance':
                                save_group_to_csv(output_dir / task['filename'], parsed)
                            elif task['type'] in ['point_in_sign', 'point_bundle']:
                                append_to_csv(points_output_path, parsed)
                                resorting_needed = True
                            elif task['type'] == 'balance_bundle':
                                for fname, grp_data in grouped_delineations.items():
                                    if fname != "points_in_signs.csv":
                                        subset_data = {k: parsed[k] for k in grp_data.keys() if k in parsed}
                                        if subset_data:
                                            save_group_to_csv(output_dir / fname, subset_data)

                    if success:
                        tqdm.write(f"  -> {Fore.GREEN}Completed.{Fore.RESET}")
                        processed_count += 1
                    else:
                        tqdm.write(f"  -> {Fore.RED}Failed.{Fore.RESET}")
                        failed_count += 1
                        if error:
                            error_text = error.read_text(encoding='utf-8').strip()
                            tqdm.write(f"{Fore.RED}      Reason: {error_text}{Fore.RESET}")
                    
                    pbar.update(1)
                    time.sleep(0.1)
        else:  # Non-interactive mode (e.g., piped output)
            current_header_group = None
            for i, task in enumerate(tasks_to_run):
                task_group = get_task_group(task)
                if task_group != current_header_group:
                    if current_header_group is not None:
                        print("") # Add separation
                    print(f"{Fore.CYAN}--- {task_group} ---{Fore.RESET}")
                    current_header_group = task_group
                
                print(f"  - [{i + 1}/{len(tasks_to_run)}] Neutralizing {task['name']}...")
                
                block = "\n".join([f"*{k}\n{v}" for k, v in task['data'].items()])
                prompt = NEUTRALIZE_PROMPT_TEMPLATE.format(delineation_block=block)

                response, error = run_llm_worker(script_dir, temp_dir, task['name'], prompt)
                
                success = False
                if response:
                    parsed = parse_llm_response(response)
                    if len(parsed) == len(task['data']):
                        success = True
                        if task['type'] == 'balance':
                            save_group_to_csv(output_dir / task['filename'], parsed)
                        elif task['type'] in ['point_in_sign', 'point_bundle']:
                            append_to_csv(points_output_path, parsed)
                            resorting_needed = True
                        elif task['type'] == 'balance_bundle':
                            for fname, grp_data in grouped_delineations.items():
                                if fname != "points_in_signs.csv":
                                    subset_data = {k: parsed[k] for k in grp_data.keys() if k in parsed}
                                    if subset_data:
                                        save_group_to_csv(output_dir / fname, subset_data)

                if success:
                    print(f"  -> {Fore.GREEN}Completed.{Fore.RESET}")
                    processed_count += 1
                else:
                    print(f"  -> {Fore.RED}Failed.{Fore.RESET}")
                    failed_count += 1
                    if error:
                        error_text = error.read_text(encoding='utf-8').strip()
                        print(f"      Reason: {Fore.RED}{error_text}{Fore.RESET}")
                
                time.sleep(0.1)

    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Process interrupted by user.{Fore.RESET}")
    finally:
        if resorting_needed and failed_count == 0:
            print("\nRe-sorting to match original file order...")
            resort_csv_by_key_order(points_output_path, points_in_signs_master_order)
        
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        if args.fast:
            total_possible_tasks = 1 + len(points_list)
        else:
            total_possible_tasks = (len(grouped_delineations) - 1) + len(points_in_signs_master_order)
        
        skipped_count = total_possible_tasks - len(tasks_to_run)

        print(f"\n{Fore.YELLOW}--- Summary ---{Fore.RESET}")
        print(f"  - Processed: {processed_count} tasks")
        print(f"  - Skipped:   {skipped_count} tasks (already exist)")
        print(f"  - Failed:    {failed_count} tasks")
        
        from config_loader import PROJECT_ROOT
        display_path = os.path.relpath(output_dir, PROJECT_ROOT)

        print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
        print(f"{Fore.CYAN} - Neutralized delineations saved to: {display_path}{Fore.RESET}")

        if failed_count > 0:
            key_metric = f"Finished with {failed_count} failure(s)"
            print(f"\n{Fore.RED}FAILURE: {key_metric}. Re-run the script to automatically retry.{Fore.RESET}\n")
        else:
            key_metric = f"Processed {processed_count} task(s)"
            print(f"\n{Fore.GREEN}SUCCESS: {key_metric}. Neutralization completed successfully.{Fore.RESET}\n")

def debug_and_exit(prompt, worker_result, pbar, temp_dir):
    """Prints debug info and halts the script."""
    response_path, error_path = worker_result
    if pbar:
        pbar.close()
        sys.stdout.write('\x1b[2K\r') 
        
    print(f"\n\n{Fore.CYAN}--- DEBUG MODE: FIRST PROMPT AND RESPONSE ---{Fore.RESET}")
    print(f"\n{Fore.YELLOW}--- PROMPT SENT TO LLM ---{Fore.RESET}")
    print(prompt)
    if error_path:
        print(f"\n{Fore.RED}--- ERROR RECEIVED ---{Fore.RESET}")
        print(error_path.read_text(encoding='utf-8'))
    elif response_path:
        print(f"\n{Fore.GREEN}--- RESPONSE RECEIVED ---{Fore.RESET}")
        print(response_path.read_text(encoding='utf-8'))
    else:
        print(f"\n{Fore.RED}--- NO RESPONSE OR ERROR FILE GENERATED ---{Fore.RESET}")
    print(f"\n{Fore.CYAN}--- HALTING EXECUTION ---{Fore.RESET}")
    
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    sys.exit(0)

def run_llm_worker(script_dir, temp_dir, task_name, prompt):
    """A helper to run the llm_prompter.py worker and return file paths."""
    query_file = temp_dir / "query.txt"
    response_file = temp_dir / "response.txt"
    error_file = temp_dir / "error.txt"
    config_file = temp_dir / "temp_config.ini"

    # Clean up from previous run in loop
    if response_file.exists(): response_file.unlink()
    if error_file.exists(): error_file.unlink()

    query_file.write_text(prompt, encoding="utf-8")
    
    worker_cmd = [
        sys.executable, str(script_dir / "llm_prompter.py"), task_name,
        "--input_query_file", str(query_file),
        "--output_response_file", str(response_file),
        "--output_error_file", str(error_file),
        "--config_path", str(config_file),
        "--quiet",
    ]
    result = subprocess.run(worker_cmd, check=False, capture_output=True, text=True, encoding='utf-8')

    # If the worker crashed without writing its own error file, capture its output.
    error_file_exists = error_file.exists() and error_file.stat().st_size > 0
    if result.returncode != 0 and not error_file_exists:
        crash_log = f"LLM worker crashed with exit code {result.returncode}.\n"
        if result.stdout:
            crash_log += f"\n--- STDOUT ---\n{result.stdout}\n"
        if result.stderr:
            crash_log += f"\n--- STDERR ---\n{result.stderr}\n"
        error_file.write_text(crash_log, encoding='utf-8')

    error = error_file if error_file.exists() and error_file.stat().st_size > 0 else None
    response = response_file if response_file.exists() else None
    return response, error

if __name__ == "__main__":
    main()

# === End of src/neutralize_delineations.py ===

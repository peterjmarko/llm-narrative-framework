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

# Initialize colorama
init(autoreset=True)

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(message)s")

# --- Config Loader ---
try:
    from config_loader import APP_CONFIG, get_config_value
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from config_loader import APP_CONFIG, get_config_value


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
    sign_strong_keys = {f"{sign} Strong" for sign in signs}

    groups = {
        "balances_quadrants.csv": {k: v for k, v in all_dels.items() if k.startswith("Quadrant") and is_balance_delineation(k)},
        "balances_hemispheres.csv": {k: v for k, v in all_dels.items() if k.startswith("Hemisphere") and is_balance_delineation(k)},
        "balances_elements.csv": {k: v for k, v in all_dels.items() if k.startswith("Element") and is_balance_delineation(k)},
        "balances_modes.csv": {k: v for k, v in all_dels.items() if k.startswith("Mode") and is_balance_delineation(k)},
        "balances_signs.csv": {k: v for k, v in all_dels.items() if k in sign_strong_keys},
        "points_in_signs.csv": get_points_in_signs_delineations(all_dels, points),
    }
    return groups


def parse_llm_response(response_filepath: Path) -> Dict[str, str]:
    """
    Parses a delineation file (*Key / Text format) into a dictionary.
    This is used for both the initial library and the LLM response.
    """
    delineations = {}
    current_key = None
    current_text = []

    if not response_filepath.exists():
        return delineations

    with open(response_filepath, "r", encoding="utf-8", errors="ignore") as f:
        # Read all lines to allow lookahead for the next key
        lines = f.readlines()

    for line in lines:
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith(";"):
            continue

        if stripped_line.startswith("*"):
            # If we were building a key, save it now.
            if current_key:
                delineations[current_key] = " ".join(current_text).strip()
            
            # Start the new key.
            current_key = stripped_line[1:].strip()
            current_text = []
        elif current_key:
            # Append text only if we are inside a key block.
            cleaned_line = stripped_line.replace("|", " ").strip()
            if cleaned_line:
                current_text.append(cleaned_line)

    # Save the very last entry after the loop finishes.
    if current_key:
        delineations[current_key] = " ".join(current_text).strip()

    return delineations


def save_group_to_csv(filepath: Path, data: Dict[str, str]):
    """Saves a group of key-value delineations to a CSV file with all fields quoted."""
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        for key, text in data.items():
            writer.writerow([key, text])


def main():
    """Main function to orchestrate the neutralization process."""
    # --- Config and Arguments ---
    default_model = get_config_value(APP_CONFIG, "DataGeneration", "neutralization_model", "anthropic/claude-3.5-sonnet")
    default_points_str = "Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Ascendant, Midheaven"
    points_to_process = get_config_value(APP_CONFIG, "DataGeneration", "points_for_neutralization", default_points_str)
    points_list = [p.strip() for p in points_to_process.split(',')]
    
    parser = argparse.ArgumentParser(description="Neutralize raw astrological delineations using an LLM.")
    parser.add_argument("-i", "--input-file", default="data/foundational_assets/sf_delineations_library.txt")
    parser.add_argument("-o", "--output-dir", default="data/foundational_assets/neutralized_delineations")
    parser.add_argument("--model", default=default_model)
    parser.add_argument("--force", action="store_true", help="Force re-processing of all groups.")
    parser.add_argument("--debug-first-prompt", action="store_true", help="Process only the first item, print prompt/response, and exit.")
    args = parser.parse_args()
    
    # --- File Handling and Backup ---
    input_path, output_dir = Path(args.input_file), Path(args.output_dir)
    if not input_path.exists():
        logging.error(f"{Fore.RED}FATAL: Input file not found: {input_path}")
        sys.exit(1)

    if args.force and output_dir.exists():
        print(f"\n{Fore.YELLOW}WARNING: You are about to overwrite all neutralized delineation files.{Fore.RESET}")
        confirm = input("A backup will be created. Are you sure? (Y/N): ").lower()
        if confirm != "y":
            print("Operation cancelled by user."); sys.exit(0)
        try:
            backup_dir = Path("data/backup")
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{output_dir.name}_{timestamp}.zip"
            shutil.make_archive(str(backup_dir / backup_name.replace('.zip','')), 'zip', output_dir)
            logging.info(f"Successfully created backup at: {backup_dir / backup_name}")
            shutil.rmtree(output_dir)
        except Exception as e:
            logging.error(f"{Fore.RED}Failed to back up or remove directory: {e}"); sys.exit(1)

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
    
    processed_count, skipped_count, failed_count = 0, 0, 0
    pbar = None
    is_first_item_for_debug = True
    
    # --- Main Processing Loop ---
    try:
        with tqdm(total=len(grouped_delineations), desc="Processing Groups", ncols=100) as pbar:
            for filename, group_data in grouped_delineations.items():
                pbar.set_postfix_str(filename)
                group_name = filename.replace('.csv', '').replace('balances_', '')
                output_path = output_dir / filename

                if output_path.exists() and not args.force:
                    tqdm.write(f"Skipping {group_name} (already exists)...")
                    skipped_count += 1
                    pbar.update(1)
                    continue

                if filename == "points_in_signs.csv":
                    tqdm.write("Processing Points in Signs...")
                    neutralized_group_data = {}
                    point_failures = 0
                    for point in points_list:
                        tqdm.write(f"  - Neutralizing {point} in Signs...")
                        point_dels = {k: v for k, v in group_data.items() if k.startswith(point)}
                        if not point_dels: continue
                        
                        block = "\n".join([f"*{k}\n{v}" for k, v in point_dels.items()])
                        prompt = NEUTRALIZE_PROMPT_TEMPLATE.format(delineation_block=block)
                        
                        if args.debug_first_prompt and is_first_item_for_debug:
                            debug_and_exit(prompt, run_llm_worker(script_dir, temp_dir, "debug_task", prompt), pbar, temp_dir)

                        response, error = run_llm_worker(script_dir, temp_dir, f"neutralize_{point}", prompt)
                        if response:
                            parsed_response = parse_llm_response(response)
                            if len(parsed_response) == len(point_dels):
                                neutralized_group_data.update(parsed_response)
                            else:
                                point_failures += 1
                        else:
                            point_failures += 1
                        is_first_item_for_debug = False
                            
                    if point_failures == 0:
                        save_group_to_csv(output_path, neutralized_group_data)
                        tqdm.write(f" -> {Fore.GREEN}Points in Signs completed.{Fore.RESET}")
                        processed_count += 1
                    else:
                        tqdm.write(f" -> {Fore.RED}Points in Signs failed ({point_failures} sub-tasks failed).{Fore.RESET}")
                        failed_count += 1
                else: # Standard groups
                    block = "\n".join([f"*{k}\n{v}" for k, v in group_data.items()])
                    prompt = NEUTRALIZE_PROMPT_TEMPLATE.format(delineation_block=block)
                    
                    if args.debug_first_prompt and is_first_item_for_debug:
                        debug_and_exit(prompt, run_llm_worker(script_dir, temp_dir, "debug_task", prompt), pbar, temp_dir)
                    is_first_item_for_debug = False

                    response, error = run_llm_worker(script_dir, temp_dir, f"neutralize_{group_name}", prompt)
                    
                    if response:
                        neutralized_data = parse_llm_response(response)
                        if len(neutralized_data) == len(group_data):
                            save_group_to_csv(output_path, neutralized_data)
                            tqdm.write(f"{Fore.GREEN}{group_name.capitalize()} balances completed.{Fore.RESET}")
                            processed_count += 1
                        else:
                            tqdm.write(f"{Fore.RED}{group_name.capitalize()} balances failed (incomplete response).{Fore.RESET}")
                            failed_count += 1
                    else:
                        tqdm.write(f"{Fore.RED}{group_name.capitalize()} balances failed (no response).{Fore.RESET}")
                        failed_count += 1
                pbar.update(1)
                time.sleep(0.1)

    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Process interrupted by user.{Fore.RESET}")
    finally:
        if 'pbar' in locals() and pbar is not None and not pbar.disable:
            pbar.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\n{Fore.YELLOW}--- Summary ---{Fore.RESET}")
        print(f"Processed: {processed_count} groups")
        print(f"Skipped:   {skipped_count} groups (already exist)")
        print(f"Failed:    {failed_count} groups")
        
        if failed_count > 0:
            print(f"\n{Fore.RED}Neutralization process finished with {failed_count} failure(s). ✨{Fore.RESET}\n")
        else:
            print(f"\n{Fore.GREEN}Neutralization process finished successfully. ✨{Fore.RESET}\n")

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

def debug_and_exit(prompt, response_path, error_path, pbar, temp_dir):
    """Prints debug info and halts the script."""
    if pbar:
        pbar.close()
        # Clear the line where the progress bar was to prevent display artifacts
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
    subprocess.run(worker_cmd, check=False, capture_output=True)

    error = error_file if error_file.exists() and error_file.stat().st_size > 0 else None
    response = response_file if response_file.exists() else None
    return response, error

if __name__ == "__main__":
    main()

# === End of src/neutralize_delineations.py ===

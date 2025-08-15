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
# Filename: src/validate_wikipedia_pages.py

"""
Validates Wikipedia page content and generates the final validation reports.

This is the second and final step in the data validation pipeline. It takes the
intermediate file of Wikipedia links (`adb_wiki_links.csv`) and performs an
intensive, content-level validation for each page.

The script's validation process includes:
1.  **Resolving Redirects:** Follows all HTTP redirects, meta-refresh tags, and
    canonical URL declarations to find the true source page.
2.  **Handling Disambiguation:** Detects disambiguation pages and intelligently
    searches for the correct subject link using their birth year.
3.  **Validating Names:** Performs a fuzzy string comparison between the ADB name
    and the Wikipedia article title to check for mismatches.
4.  **Verifying Death Date:** Uses a multi-strategy approach to confirm that the
    subject is deceased by checking infoboxes, categories, and text patterns.

Upon completion, it produces two key outputs:
- A detailed, machine-readable CSV report (`adb_validation_report.csv`).
- A human-readable text summary (`adb_validation_summary.txt`).

The script is fully resumable, interrupt-safe, and includes a `--report-only`
flag to regenerate the text summary from an existing CSV report.
"""

import argparse
import csv
import logging
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from datetime import datetime
from pathlib import Path
from threading import Lock
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from colorama import Fore, init
from requests.adapters import HTTPAdapter
from thefuzz import fuzz
from tqdm import tqdm
from urllib3.util.retry import Retry

# Initialize colorama
init(autoreset=True)

# --- Globals & Constants ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT = 15
MAX_WORKERS = 5
REQUEST_DELAY = 0.1
NAME_MATCH_THRESHOLD = 90
MAX_DISAMBIGUATION_DEPTH = 3

# --- Resilient Session Management ---
SESSION = requests.Session()
retry_strategy = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retry_strategy)
SESSION.mount("https://", adapter)
SESSION.mount("http://", adapter)

# --- Logging Setup ---
class TqdmLoggingHandler(logging.Handler):
    def emit(self, record):
        try:
            tqdm.write(self.format(record))
        except Exception:
            self.handleError(record)

class CustomFormatter(logging.Formatter):
    log_format = f"%(levelname)s: %(message)s"
    FORMATS = {logging.INFO: log_format, logging.WARNING: Fore.YELLOW + log_format, logging.ERROR: Fore.RED + log_format}
    def format(self, record):
        return logging.Formatter(self.FORMATS.get(record.levelno, self.log_format)).format(record)

# --- Helper Functions ---

def fetch_page_content(url: str) -> BeautifulSoup | None:
    """Fetches and parses a web page, handling meta-refresh redirects."""
    try:
        headers = {'User-Agent': USER_AGENT}
        response = SESSION.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile(r"refresh", re.I)})
        if meta_refresh and "content" in meta_refresh.attrs:
            match = re.search(r'url\s*=\s*(.*?)\s*$', meta_refresh["content"], re.I)
            if match:
                new_url = urljoin(response.url, match.group(1).strip("'\""))
                logging.info(f"Following meta-refresh from {url} -> {new_url}")
                return fetch_page_content(new_url)
        return soup
    except requests.exceptions.RequestException as e:
        logging.warning(f"Request failed for {url}: {e}")
        return None

def follow_all_redirects(url: str, max_redirects: int = 10) -> tuple[str, BeautifulSoup]:
    """Follows redirects to reach the final destination page."""
    current_url = url
    for _ in range(max_redirects):
        soup = fetch_page_content(current_url)
        if not soup: return current_url, None
            
        canonical_link = soup.find('link', rel='canonical')
        if canonical_link and canonical_link.get('href') != current_url:
            current_url = canonical_link['href']
            continue
        
        return current_url, soup
    return current_url, soup

def is_disambiguation_page(soup: BeautifulSoup) -> bool:
    """Detects if a Wikipedia page is a disambiguation page."""
    return any([
        soup.find('div', id='disambiguation'),
        soup.find(class_=re.compile(r'\bdisambiguation\b', re.I)),
        soup.find(string=re.compile(r"may refer to:", re.I))
    ])

def find_matching_disambiguation_link(soup: BeautifulSoup, birth_year: str) -> str | None:
    """Finds the correct link on a disambiguation page using birth year."""
    for item in soup.find_all('li'):
        if birth_year in item.get_text():
            link = item.find('a', href=re.compile(r"/wiki/"))
            if link:
                return urljoin("https://en.wikipedia.org", link['href'])
    return None

def validate_name(adb_name: str, soup: BeautifulSoup) -> tuple[str, int]:
    """Extracts Wikipedia name and compares it to the ADB name."""
    wp_name_tag = soup.find('h1', id='firstHeading')
    wp_name = wp_name_tag.get_text(strip=True) if wp_name_tag else "Name Not Found"
    
    adb_base_name = re.sub(r'\s*\(\d{4}\)$', '', adb_name).strip()
    if ',' in adb_base_name:
        adb_base_name = ' '.join(reversed(adb_base_name.split(',', 1))).strip()

    wp_base_name = re.sub(r'\s*\(.*\)$', '', wp_name).strip()
    return wp_name, fuzz.ratio(adb_base_name.lower(), wp_base_name.lower())

def validate_death_date(soup: BeautifulSoup) -> bool:
    """Checks for evidence of a death date on the Wikipedia page."""
    if soup.find('div', id='mw-normal-catlinks', string=re.compile(r'\bLiving people\b')):
        return False
    if soup.find('div', id='mw-normal-catlinks', string=re.compile(r'\d{4} deaths')):
        return True
    
    infobox = soup.find('table', class_='infobox')
    if infobox and infobox.find(lambda tag: tag.name == 'th' and re.search(r'\bDied\b', tag.get_text())):
        return True
    
    first_p = soup.find('p')
    if first_p and re.search(r'\([^)]*\b\d{3,4}\b[^)]*–[^)]*\b\d{3,4}\b[^)]*\)', first_p.get_text()):
        return True
    return False

def process_wikipedia_page(url: str, adb_name: str, birth_year: str, pbar: tqdm, depth=0) -> dict:
    """Scrapes and validates a Wikipedia page with robust disambiguation handling."""
    if depth >= MAX_DISAMBIGUATION_DEPTH:
        return {'status': 'FAIL', 'notes': 'Max disambiguation depth reached'}

    final_url, soup = follow_all_redirects(url)
    if not soup:
        return {'status': 'ERROR', 'notes': 'Failed to fetch Wikipedia page'}

    if is_disambiguation_page(soup):
        logging.info(f"Disambiguation page for {adb_name}. Searching for birth year '{birth_year}'...")
        matching_url = find_matching_disambiguation_link(soup, birth_year)
        if matching_url:
            return process_wikipedia_page(matching_url, adb_name, birth_year, pbar, depth + 1)
        return {'status': 'FAIL', 'notes': f"Disambiguation page, no link with year {birth_year} found"}

    wp_name, name_score = validate_name(adb_name, soup)
    death_date_found = validate_death_date(soup)
    
    return {
        'status': 'OK', 'final_url': final_url, 'wp_name': wp_name,
        'name_score': name_score, 'death_date_found': death_date_found
    }

def worker_task(row: dict, pbar: tqdm, index: int) -> dict:
    """Validates a single record from the wiki_links file."""
    time.sleep(REQUEST_DELAY)
    
    # Base result includes all input data
    result = {'Index': index, **row}

    # If a URL is present and there are no pre-existing notes, proceed with validation.
    # Otherwise, pass the record through with its original notes.
    if row.get('Wikipedia_URL') and not row.get('Notes'):
        validation = process_wikipedia_page(row['Wikipedia_URL'], row['ADB_Name'], row['BirthYear'], pbar)
    else:
        status = 'VALID' if row['Entry_Type'] == 'Research' else 'FAIL'
        notes = row.get('Notes') or ('Research entry - Wikipedia not expected' if row['Entry_Type'] == 'Research' else 'No Wikipedia URL found')
        return {**result, 'Status': status, 'Notes': notes}

    validation = process_wikipedia_page(row['Wikipedia_URL'], row['ADB_Name'], row['BirthYear'], pbar)
    
    if validation['status'] != 'OK':
        return {**result, 'Status': validation['status'], 'Notes': validation['notes']}

    # Update result with validation data
    result.update({
        'WP_URL': validation['final_url'], 'WP_Name': validation['wp_name'],
        'Name_Match_Score': validation['name_score'], 'Death_Date_Found': validation['death_date_found']
    })
    
    final_status, notes = 'OK', []
    if result.get('Name_Match_Score', 0) < NAME_MATCH_THRESHOLD:
        final_status = 'FAIL'
        notes.append(f"Name mismatch (Score: {result.get('Name_Match_Score', 0)})")
    if not result.get('Death_Date_Found'):
        final_status = 'FAIL'
        notes.append("Death date not found")

    result['Status'] = 'VALID' if final_status == 'OK' and row['Entry_Type'] != 'Person' else final_status
    result['Notes'] = '; '.join(notes)
    
    return result

def load_and_filter_input(input_path: Path, report_path: Path, force: bool) -> tuple[list, set, int, int, int, int]:
    """Loads input data, filters out processed records, and returns current validation state."""
    if not input_path.exists():
        logging.error(f"Input file not found: {input_path}"); sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        all_records = list(csv.DictReader(f))
    
    total_subjects = len(all_records)

    processed_ids, timed_out_ids, max_index, valid_count = set(), set(), 0, 0
    if not force and report_path.exists():
        with open(report_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'idADB' in row:
                    if row.get('Notes') == 'Processing timeout':
                        timed_out_ids.add(row['idADB'])
                    else:
                        processed_ids.add(row['idADB'])
                        if row.get('Status') in ['OK', 'VALID']:
                            valid_count += 1
                if 'Index' in row:
                    max_index = max(max_index, int(row.get('Index', 0) or 0))

    records_to_process = [rec for rec in all_records if rec['idADB'] not in processed_ids]
    return records_to_process, timed_out_ids, max_index, valid_count, len(processed_ids), total_subjects

def sort_output_file(filepath: Path, fieldnames: list):
    """Reads the output file, sorts it by Index, and writes it back."""
    if not filepath.exists(): return
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            if not f.read(1): return
            f.seek(0)
            all_results = list(csv.DictReader(f))
        
        sorted_results = sorted(all_results, key=lambda r: int(r.get('Index', 0)))
        
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted_results)
    except (IOError, csv.Error, KeyError, ValueError) as e:
        logging.error(f"Could not sort the output file: {e}")

def print_final_summary(output_path: Path, total_subjects: int):
    """Reads the final report file and prints a comprehensive summary."""
    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            final_results = list(csv.DictReader(f))
        
        total_processed = len(final_results)
        total_valid = sum(1 for r in final_results if r.get('Status') in ['OK', 'VALID'])

        percentage_str = "(0%)"
        if total_processed > 0:
            percentage = (total_valid / total_processed) * 100
            percentage_str = f"({percentage:.0f}%)"
        
        summary_msg = f"Validated {total_valid:,} out of {total_subjects:,} total subjects {percentage_str}."
        if total_processed < total_subjects:
            summary_msg = f"Validated {total_valid:,} records across {total_processed:,} processed subjects (out of {total_subjects:,} total) {percentage_str}."

        print(f"\n{Fore.GREEN}SUCCESS: Validation complete.")
        print(summary_msg)
        print(f"Final report is sorted and saved to: {output_path} ✨\n")

    except (IOError, csv.Error) as e:
        logging.error(f"Failed to generate final summary: {e}")

def generate_summary_report(report_path: Path):
    """Reads the detailed CSV report and generates a summary text file."""
    if not report_path.exists():
        print(f"{Fore.RED}ERROR: Input report file not found at '{report_path}'")
        return

    summary_path = report_path.parent / "adb_validation_summary.txt"
    
    if summary_path.exists():
        try:
            backup_dir = Path('data/backup')
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{summary_path.stem}.{timestamp}{summary_path.suffix}.bak"
            shutil.copy2(summary_path, backup_path)
            print(f"Backed up existing summary to: {backup_path}")
        except (IOError, OSError) as e:
            print(f"{Fore.YELLOW}Could not create backup for summary report: {e}")
            
    # Initialize counters
    total_records, valid_records, failed_records = 0, 0, 0
    no_wiki_link, fetch_fail, no_death, name_mismatch, disambiguation_fail = 0, 0, 0, 0, 0
    timeout_error, non_english_error, other_errors = 0, 0, 0
    research_entries, person_entries = 0, 0

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
            total_records = len(rows)

        if total_records == 0:
            print(f"{Fore.YELLOW}Warning: Report is empty. Cannot generate summary.")
            return

        # Aggregate data
        for row in rows:
            if row.get('Entry_Type') == 'Research':
                research_entries += 1
            else:
                person_entries += 1
            
            if row.get('Status') in ['OK', 'VALID']:
                valid_records += 1
            else:
                failed_records += 1
                notes = row.get('Notes', '')
                url_notes = row.get('Wikipedia_URL', '')
                
                # Use a prioritized elif chain to categorize each failure once
                if "TIMEOUT" in url_notes:
                    timeout_error += 1
                elif "NON-ENGLISH" in url_notes:
                    non_english_error += 1
                elif "No Wikipedia URL found" in notes:
                    no_wiki_link += 1
                elif "Failed to fetch" in notes:
                    fetch_fail += 1
                elif "Disambiguation" in notes:
                    disambiguation_fail += 1
                elif "Name mismatch" in notes:
                    name_mismatch += 1
                elif "Death date not found" in notes:
                    no_death += 1
                elif notes.strip():
                    other_errors += 1
        
        # --- Build Formatted Report ---
        title = "Astro-Databank Validation Summary"
        banner_width = 60
        banner = "=" * banner_width
        
        # --- Define Column Widths ---
        label_col = 35
        count_col = 12
        perc_col = 10

        # Overall Statistics
        s2_perc = f"({valid_records/total_records:.1%})" if total_records > 0 else ""
        s3_perc = f"({failed_records/total_records:.1%})" if total_records > 0 else ""

        overall_stats = [
            f"--- Overall Statistics ---",
            f"{'Total Records in Report:':<{label_col}}{total_records:>{count_col},}",
            f"{'Valid Records:':<{label_col}}{valid_records:>{count_col},}{s2_perc:>{perc_col}}",
            f"{'Failed Records:':<{label_col}}{failed_records:>{count_col},}{s3_perc:>{perc_col}}"
        ]
        
        entry_type_stats = [
            f"\n--- Entry Type Breakdown ---",
            f"{'Person Entries:':<{label_col}}{person_entries:>{count_col},}",
            f"{'Research Entries:':<{label_col}}{research_entries:>{count_col},}"
        ]

        failure_analysis = []
        if failed_records > 0:
            failure_analysis.append(f"\n--- Failure Analysis ({failed_records:,} Records) ---")
            fail_data = [
                ("1. No Wikipedia Link Found:", no_wiki_link),
                ("2. Could Not Fetch Page:", fetch_fail),
                ("3. Non-English Link (No Fallback):", non_english_error),
                ("4. Disambiguation Failed:", disambiguation_fail),
                ("5. Name Mismatch:", name_mismatch),
                ("6. Death Date Not Found:", no_death),
                ("7. Processing Timeout:", timeout_error),
                ("8. Other Errors:", other_errors)
            ]
            
            for label, count in fail_data:
                if count > 0:
                    perc_str = f"({count/total_records:.1%})"
                    line = f"{label:<{label_col}}{count:>{count_col},}{perc_str:>{perc_col}}"
                    failure_analysis.append(line)
        
        report_lines = [
            f"{Fore.CYAN}{banner}", f"{title.center(banner_width)}", f"{banner}{Fore.RESET}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            *overall_stats, *entry_type_stats, *failure_analysis,
            f"\n{Fore.CYAN}{banner}{Fore.RESET}"
        ]
        
        summary_content = "\n".join(report_lines)
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_content)

        print("\n" + summary_content + "\n")
        print(f"{Fore.GREEN}SUCCESS: Summary report saved to '{summary_path}' ✨\n")

    except (IOError, csv.Error) as e:
        print(f"{Fore.RED}ERROR: Failed to generate summary report: {e}")


def worker_task_with_timeout(row: dict, pbar: tqdm, index: int) -> dict:
    """Wrapper to add a hard timeout to the worker_task."""
    from queue import Queue
    import threading
    
    result_queue = Queue()

    def task_wrapper():
        try:
            result = worker_task(row, pbar, index)
            result_queue.put(result)
        except Exception as e:
            result_queue.put(e)

    thread = threading.Thread(target=task_wrapper)
    thread.daemon = True
    thread.start()
    thread.join(timeout=60)

    if thread.is_alive():
        tqdm.write(f"{Fore.YELLOW}Worker timeout for idADB {row.get('idADB')} ({row.get('ADB_Name')}). Skipping.")
        # Return a result that preserves input data but marks it as a timeout failure
        return {**row, 'Index': index, 'Status': 'FAIL', 'Notes': 'Processing timeout'}

    result = result_queue.get()
    if isinstance(result, Exception):
        raise result
        
    return result


def main():
    parser = argparse.ArgumentParser(description="Validate Wikipedia page content for ADB subjects.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-i", "--input-file", default="data/processed/adb_wiki_links.csv", help="Path to the CSV file with Wikipedia links.")
    parser.add_argument("-o", "--output-file", default="data/reports/adb_validation_report.csv", help="Path for the final validation report CSV.")
    parser.add_argument("-w", "--workers", type=int, default=MAX_WORKERS, help="Number of parallel worker threads.")
    parser.add_argument("--force", action="store_true", help="Force reprocessing of all records.")
    parser.add_argument("--report-only", action="store_true", help="Generate the summary report for an existing validation CSV and exit.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output.")
    args = parser.parse_args()

    # --- Configure Logging ---
    log_level = logging.INFO if args.verbose else logging.ERROR
    handler = TqdmLoggingHandler()
    handler.setFormatter(CustomFormatter())
    logging.basicConfig(level=log_level, handlers=[handler], force=True)

    input_path, output_path = Path(args.input_file), Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.report_only:
        print(f"\n{Fore.YELLOW}--- Generating Summary Report Only ---")
        generate_summary_report(output_path)
        sys.exit(0)

    def backup_and_overwrite(file_path: Path):
        """Creates a backup of the file and then deletes the original."""
        try:
            backup_dir = Path('data/backup')
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{file_path.stem}.{timestamp}{file_path.suffix}.bak"
            shutil.copy2(file_path, backup_path)
            print(f"{Fore.CYAN}Backed up existing report to: {backup_path}")
            file_path.unlink()
        except (IOError, OSError) as e:
            logging.error(f"Failed to create backup or remove file: {e}")
            sys.exit(1)
            
    # Handle --force flag first for non-interactive overwrite
    if args.force and output_path.exists():
        print(f"{Fore.YELLOW}Forcing overwrite of existing report...")
        backup_and_overwrite(output_path)
    
    # Automatically re-run if the input link file is newer than the report
    elif not args.force and output_path.exists() and input_path.exists():
        if os.path.getmtime(input_path) > os.path.getmtime(output_path):
            print(f"{Fore.YELLOW}Input file '{input_path.name}' is newer than the existing report.")
            print("Stale data detected. Automatically re-running validation...")
            backup_and_overwrite(output_path)
            # Set force=True for the loader to ensure a full re-run
            args.force = True

    records_to_process, timed_out_ids, max_index_before, valid_before, processed_before, total_subjects = load_and_filter_input(input_path, output_path, args.force)
    
    fieldnames = ['Index', 'idADB', 'ADB_Name', 'Entry_Type', 'WP_URL', 'WP_Name', 'Name_Match_Score', 'Death_Date_Found', 'Status', 'Notes']
    
    # If there are timed-out records, they must be retried.
    if timed_out_ids:
        print(f"{Fore.YELLOW}Found {len(timed_out_ids)} records that previously timed out. Retrying them now.")
        temp_path = output_path.with_suffix('.tmp')
        with open(output_path, 'r', encoding='utf-8') as infile, open(temp_path, 'w', encoding='utf-8', newline='') as outfile:
            reader = csv.DictReader(infile)
            writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                if row['idADB'] not in timed_out_ids:
                    writer.writerow(row)
        shutil.move(temp_path, output_path)
        
        # Reload state after cleaning the file
        records_to_process, _, max_index_before, valid_before, processed_before, _ = load_and_filter_input(input_path, output_path, False)

    if not records_to_process:
        # If there are still no records to process after handling timeouts, then we're truly done.
        print(f"\n{Fore.GREEN}All records have already been validated. Output is up to date. ✨")
        
        confirm = input("If you decide to go ahead and overwrite the existing file, a backup will be created first. Do you wish to proceed? (Y/N): ").lower().strip()
        if confirm == 'y':
            print(f"{Fore.YELLOW}Forcing overwrite of existing report...")
            backup_and_overwrite(output_path)
            # Re-initialize state for a full run
            records_to_process, timed_out_ids, max_index_before, valid_before, processed_before, total_subjects = load_and_filter_input(input_path, output_path, True)
        else:
            # Just print the summary of the existing file without modifying it
            print_final_summary(output_path, total_subjects)
            sys.exit(0)
        
    print(f"\n{Fore.YELLOW}--- Validating Wikipedia Pages ---")
    print(f"Found {processed_before:,} already processed records ({valid_before:,} valid).")
    print(f"Now processing {len(records_to_process):,} new records using {args.workers} workers.")
    print(f"{Fore.CYAN}NOTE: Each set of 1,000 records can take a minute or more to process. You can safely interrupt with Ctrl+C at any time to resume later.\n")

    was_interrupted = False
    valid_this_session = 0
    valid_lock = Lock()
    executor = ThreadPoolExecutor(max_workers=args.workers)
    output_file = None

    try:
        output_file = open(output_path, 'a', encoding='utf-8', newline='')
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        if output_file.tell() == 0:
            writer.writeheader()

        with tqdm(total=len(records_to_process), desc="Validating pages", ncols=120, smoothing=0.01) as pbar:
            tasks = [(max_index_before + i + 1, rec) for i, rec in enumerate(records_to_process)]
            futures = {executor.submit(worker_task_with_timeout, rec, pbar, index) for index, rec in tasks}
            
            while futures:
                try:
                    for future in as_completed(futures, timeout=1):
                        res = future.result()
                        if res:
                            if res.get('Status') in ['OK', 'VALID']:
                                with valid_lock:
                                    valid_this_session += 1
                            writer.writerow({k: res.get(k) for k in fieldnames})
                        
                        pbar.update(1)
                        futures.remove(future)
                        
                        # Update progress bar with total counts
                        total_valid = valid_before + valid_this_session
                        total_processed = processed_before + pbar.n
                        percentage = (total_valid / total_processed) * 100 if total_processed > 0 else 0
                        pbar.set_postfix_str(f"Validated: {total_valid:,}/{total_processed:,} ({percentage:.0f}%)")
                except TimeoutError:
                    pass

    except KeyboardInterrupt:
        was_interrupted = True
        print(f"\n{Fore.YELLOW}Processing interrupted by user. Saving and sorting partial results...")
    
    finally:
        if was_interrupted:
            executor.shutdown(wait=False, cancel_futures=True)
        else:
            executor.shutdown(wait=True)
        if output_file and not output_file.closed:
            output_file.close()

    # Always finalize and report on exit.
    if was_interrupted:
        print(f"\n{Fore.YELLOW}Finalizing report...")
        sort_output_file(output_path, fieldnames)
        generate_summary_report(output_path)
        os._exit(1) # Still need a hard exit for hangs
    else:
        sort_output_file(output_path, fieldnames)
        generate_summary_report(output_path)
        print_final_summary(output_path, total_subjects)

if __name__ == "__main__":
    main()

# === End of src/validate_wikipedia_pages.py ===

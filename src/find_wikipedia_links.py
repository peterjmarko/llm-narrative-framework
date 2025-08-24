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
# Filename: src/find_wikipedia_links.py

"""
Finds the best-guess English Wikipedia URL for each subject in the raw ADB export.

This is the first step in the data validation pipeline. It takes the raw export
from Astro-Databank and focuses on a single task: identifying the correct
Wikipedia page for each entry.

The script uses a robust, multi-step process:
1.  **Scrapes the ADB Page:** For each subject, it fetches their Astro-Databank
    page to find a direct link to Wikipedia, trying multiple URL variants
    for research entries.
2.  **Searches Wikipedia:** If no link is found on the ADB page for a "Person"
    entry, it performs a fallback search using the Wikipedia API.
3.  **Resolves to English:** Any non-English Wikipedia links are resolved to their
    English-language equivalent.

The output is an intermediate CSV file (`adb_wiki_links.csv`) that maps each
`idADB` to a `Wikipedia_URL`. This file serves as the input for the next
script in the pipeline, `validate_wikipedia_pages.py`.
"""

import argparse
import csv
import json
import logging
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict
from urllib.parse import unquote, urljoin

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
ADB_MIN_DELAY = 0.2  # Minimum 200ms between ADB requests

# --- Rate Limiting & Session Management ---
ADB_REQUEST_LOCK = Lock()
ADB_LAST_REQUEST_TIME = 0
SESSION = requests.Session()
retry_strategy = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(pool_connections=5, pool_maxsize=5, max_retries=retry_strategy)
SESSION.mount("https://", adapter)
SESSION.mount("http://", adapter)

# --- Research Category Management ---
# We will resolve the full path inside the load function
RESEARCH_CATEGORIES_FILE_REL_PATH = "data/config/adb_research_categories.json"
RESEARCH_CATEGORIES_CACHE = None

# --- Debug Mode ---
DEBUG_MODE = os.environ.get('DEBUG_ADB', '').lower() == 'true'

def debug_log(message: str):
    """Print debug messages when DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        tqdm.write(f"[DEBUG] {message}")

class TqdmLoggingHandler(logging.Handler):
    """A logging handler that redirects all output to tqdm.write()."""
    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)

class CustomFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels."""
    log_format = f"%(levelname)s: %(message)s"
    FORMATS = {
        logging.INFO: log_format,
        logging.WARNING: Fore.YELLOW + log_format,
        logging.ERROR: Fore.RED + log_format
    }
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.log_format)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# --- Helper Functions ---

def load_research_categories() -> Dict:
    """Loads research categories from the configuration file."""
    from config_loader import get_path
    global RESEARCH_CATEGORIES_CACHE
    if RESEARCH_CATEGORIES_CACHE is not None:
        return RESEARCH_CATEGORIES_CACHE

    research_categories_path = Path(get_path(RESEARCH_CATEGORIES_FILE_REL_PATH))
    
    if not research_categories_path.exists():
        research_categories_path.parent.mkdir(parents=True, exist_ok=True)
        default_categories = {
            "categories": {"prefixes": [], "patterns": [], "exact_matches": []},
            "auto_detected": {"entries": []}
        }
        with open(research_categories_path, 'w', encoding='utf-8') as f:
            json.dump(default_categories, f, indent=2)
        RESEARCH_CATEGORIES_CACHE = default_categories
    else:
        with open(research_categories_path, 'r', encoding='utf-8') as f:
            RESEARCH_CATEGORIES_CACHE = json.load(f)
    return RESEARCH_CATEGORIES_CACHE

def is_research_entry(name: str, first_name: str = "") -> bool:
    """Determines if an entry is a Research entry based on known category patterns."""
    # Simplified logic: always construct the full name for consistent matching.
    full_name = f"{name} {first_name}".strip()
    if ',' in name:
        full_name = name
    
    categories = load_research_categories()
    
    if full_name in categories["categories"].get("exact_matches", []): return True
    for prefix in categories["categories"].get("prefixes", []):
        if full_name.lower().startswith(prefix.lower()): return True
    for pattern in categories["categories"].get("patterns", []):
        if re.match(pattern, full_name, re.I): return True
            
    if not ',' in full_name and re.search(r'\s+\d{3,}$', full_name): return True
    return False

def fetch_page_content(url: str) -> BeautifulSoup | None:
    """Fetches and parses a web page with rate limiting for ADB and long-pause retries."""
    global ADB_LAST_REQUEST_TIME
    
    # Long-term retry loop specifically for ADB rate limiting
    for attempt in range(5): # Allow up to 5 long pauses
        if 'astro.com' in url:
            with ADB_REQUEST_LOCK:
                time_since_last = time.time() - ADB_LAST_REQUEST_TIME
                if time_since_last < ADB_MIN_DELAY:
                    time.sleep(ADB_MIN_DELAY - time_since_last)
                ADB_LAST_REQUEST_TIME = time.time()
        
        try:
            headers = {'User-Agent': USER_AGENT}
            response = SESSION.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        
        except requests.exceptions.RequestException as e:
            # Check for HTTP 429 "Too Many Requests", a clear sign of rate limiting
            is_rate_limit = hasattr(e, 'response') and e.response is not None and e.response.status_code == 429

            if 'astro.com' in url and is_rate_limit:
                pause_duration = 60 # 1 minute
                tqdm.write(f"{Fore.YELLOW}WARN: ADB rate limit suspected. Pausing for {pause_duration} seconds... (Attempt {attempt + 1}/5)")
                time.sleep(pause_duration)
                continue # Retry the request after the long pause
            else:
                logging.warning(f"Request failed for {url}: {e}")
                return None # For non-rate-limit errors, fail immediately
    
    logging.error(f"Failed to fetch {url} after 5 long-pause retries. Giving up.")
    return None

def get_initial_wiki_url_from_adb(adb_url: str) -> str | None:
    """Scrapes an ADB page to find the most likely Wikipedia URL."""
    soup = fetch_page_content(adb_url)
    if not soup: return None

    # Prioritized search for the link
    link_texts = soup.find_all(string=re.compile(r"Link to Wikipedia|Wikipedia", re.I))
    for link_text in link_texts:
        parent_anchor = link_text.find_parent('a', href=re.compile(r"https?://\w+\.wikipedia\.org"))
        if parent_anchor: return parent_anchor['href']

    # Fallback to any Wikipedia link on the page
    any_link = soup.find('a', href=re.compile(r"https?://\w+\.wikipedia\.org"))
    return any_link['href'] if any_link else None

def get_english_wiki_url(initial_url: str) -> str | None:
    """Takes any language Wikipedia URL and finds the English equivalent."""
    if 'en.wikipedia.org' in initial_url:
        return unquote(initial_url)

    soup = fetch_page_content(initial_url)
    if soup:
        en_link = soup.find('a', class_='interlanguage-link-target', lang='en')
        if en_link and en_link.has_attr('href'):
            return unquote(en_link['href'])
    return None

def search_wikipedia(name: str) -> list[tuple[str, str]]:
    """Searches Wikipedia for a person by name using the API."""
    try:
        search_name = re.sub(r'\s*\(\d{4}\)$', '', name.split(',', 1)[::-1][0].strip()).strip()
        params = {'action': 'opensearch', 'search': search_name, 'limit': 3, 'format': 'json'}
        response = SESSION.get("https://en.wikipedia.org/w/api.php", params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        return list(zip(data[1], data[3])) if len(data) > 3 else []
    except requests.exceptions.RequestException as e:
        debug_log(f"Wikipedia search failed for '{name}': {e}")
        return []

def find_best_wikipedia_match(name: str, birth_year: str, search_results: list[tuple[str, str]], pbar: tqdm) -> str | None:
    """Finds the best Wikipedia match from search results by checking page content for the birth year."""
    base_name = re.sub(r'\s*\(\d{4}\)$', '', name).strip()
    if ',' in base_name:
        base_name = ' '.join(reversed(base_name.split(',', 1))).strip()

    for title, url in search_results[:3]: # Check top 3 results
        try:
            # First, do a quick check on title similarity to weed out obvious mismatches
            title_clean = re.sub(r'\s*\(.*?\)$', '', title).strip()
            if fuzz.ratio(base_name.lower(), title_clean.lower()) < 60:
                continue

            # If the title is plausible, fetch the page to check for the birth year
            soup = fetch_page_content(url)
            if soup and birth_year in soup.get_text()[:10000]: # Check first 10KB for performance
                # Check if this is a disambiguation page that we can resolve
                if is_disambiguation_page(soup):
                    matching_url = find_matching_disambiguation_link_from_search(soup, birth_year)
                    if matching_url:
                        logging.info(f"  -> Found match for {name} via disambiguation page")
                        return matching_url
                    continue # Disambiguation page but no match
                
                logging.info(f"  -> Confirmed match for {name} via birth year check")
                return url
        except Exception as e:
            logging.warning(f"Error while checking search result {url}: {e}")
            continue
            
    return None

def is_disambiguation_page(soup: BeautifulSoup) -> bool:
    """Detects if a Wikipedia page is a disambiguation page."""
    return any([
        soup.find('div', id='disambiguation'),
        soup.find(class_=re.compile(r'\bdisambiguation\b', re.I)),
        soup.find(string=re.compile(r"may refer to:", re.I))
    ])

def find_matching_disambiguation_link_from_search(soup: BeautifulSoup, birth_year: str) -> str | None:
    """Finds the correct link on a disambiguation page using birth year."""
    for item in soup.find_all('li'):
        if birth_year in item.get_text():
            link = item.find('a', href=re.compile(r"/wiki/"))
            if link:
                return urljoin("https://en.wikipedia.org", link['href'])
    return None

def worker_task(line: str, pbar: tqdm, index: int) -> dict | None:
    """Finds the Wikipedia URL for a single ADB record."""
    time.sleep(REQUEST_DELAY)
    parts = line.strip().split('\t')
    if len(parts) < 19: return None

    id_adb, last_name, first_name, birth_year, adb_url = parts[1], parts[2], parts[3], parts[7], unquote(parts[18])
    adb_name = f"{last_name}, {first_name}".strip(', ')
    full_name = adb_name if adb_name else f"{last_name} {first_name}".strip()
    entry_type = "Research" if is_research_entry(full_name, first_name) else "Person"

    if entry_type == 'Research' and '/astro-databank/' in adb_url and 'research:' not in adb_url.lower():
        base, path = adb_url.split('/astro-databank/', 1)
        adb_url = f"{base}/astro-databank/Research:{path}"

    result = {'Index': index, 'idADB': id_adb, 'ADB_Name': adb_name, 'BirthYear': birth_year, 'Entry_Type': entry_type, 'Wikipedia_URL': '', 'Notes': ''}
    
    wiki_url = get_initial_wiki_url_from_adb(adb_url)
    
    if not wiki_url and entry_type == 'Person':
        logging.info(f"No link on ADB for {adb_name}. Searching Wikipedia...")
        search_results = search_wikipedia(adb_name)
        if search_results:
            wiki_url = find_best_wikipedia_match(adb_name, birth_year, search_results, pbar)

    if wiki_url:
        english_url = get_english_wiki_url(wiki_url)
        if english_url:
            result['Wikipedia_URL'] = english_url
        else:
            result['Notes'] = 'Non-English URL with no fallback'
            logging.warning(f"Could not find English equivalent for: {wiki_url}")
    elif entry_type == 'Person':
        result['Notes'] = 'No Wikipedia URL found'

    return result

def sort_output_file(filepath: Path, fieldnames: list):
    """Reads the output file, sorts it by Index, and writes it back."""
    if not filepath.exists():
        return
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Handle empty file case
            first_char = f.read(1)
            if not first_char:
                return
            f.seek(0)
            all_results = list(csv.DictReader(f))
        
        # Sort by the 'Index' column, converting to an integer
        sorted_results = sorted(all_results, key=lambda r: int(r.get('Index', 0)))
        
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted_results)
    except (IOError, csv.Error, KeyError, ValueError) as e:
        logging.error(f"Could not sort the output file: {e}")


def load_processed_ids(filepath: Path) -> tuple[set, set, int, int, int]:
    """Reads an existing file, returning sets of processed and timed-out IDs, and counts."""
    if not filepath.exists():
        return set(), set(), 0, 0, 0
    
    processed_ids, timed_out_ids, links_found, max_index, timeouts = set(), set(), 0, 0, 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                id_adb = row.get('idADB')
                if not id_adb: continue
                
                notes = row.get('Notes', '')
                if 'Processing timeout' in notes:
                    timeouts += 1
                    timed_out_ids.add(id_adb)
                else:
                    processed_ids.add(id_adb)
                    if row.get('Wikipedia_URL'):
                        links_found += 1

                if row.get('Index'):
                    try:
                        max_index = max(max_index, int(row.get('Index', 0) or 0))
                    except (ValueError, TypeError): pass
    except (IOError, csv.Error) as e:
        logging.error(f"Could not read existing output file: {e}. Starting fresh.")
        return set(), set(), 0, 0, 0
    return processed_ids, timed_out_ids, links_found, max_index, timeouts

def worker_task_with_timeout(line: str, pbar: tqdm, index: int) -> dict:
    """Wrapper to add a hard timeout to the worker_task."""
    from queue import Queue
    
    result_queue = Queue()

    def task_wrapper():
        try:
            result = worker_task(line, pbar, index)
            result_queue.put(result)
        except Exception as e:
            result_queue.put(e) # Put exception in queue to be re-raised

    thread = threading.Thread(target=task_wrapper)
    thread.daemon = True
    thread.start()
    thread.join(timeout=60) # 60-second hard timeout for the entire task

    if thread.is_alive():
        # The worker has hung. Build an error record to be written to the file.
        try:
            parts = line.strip().split('\t')
            id_adb = parts[1]
            name = f"{parts[2]}, {parts[3]}".strip(', ')
            birth_year = parts[7]
            entry_type = "Research" if is_research_entry(name) else "Person"
        except IndexError:
            id_adb, name, birth_year, entry_type = "unknown", "unknown", "", "Person"
        
        tqdm.write(f"{Fore.YELLOW}Worker timeout for idADB {id_adb} ({name}). Skipping.")
        return {'Index': index, 'idADB': id_adb, 'ADB_Name': name, 'BirthYear': birth_year, 'Entry_Type': entry_type, 'Wikipedia_URL': '', 'Notes': 'Processing timeout'}

    # Retrieve result or exception from the queue
    result = result_queue.get()
    if isinstance(result, Exception):
        raise result # Re-raise exception in the main thread
    
    return result

def finalize_and_report(output_path: Path, fieldnames: list, all_lines: list, was_interrupted: bool):
    """Sorts the file, generates the summary, and prints the final status message for all exit conditions."""
    # Step 1: Always sort the file to ensure a consistent state.
    sort_output_file(output_path, fieldnames)
    
    # Step 2: Always generate the detailed summary report.
    # We will capture the final counts from this process for the final console message.
    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            final_results = list(csv.DictReader(f))
        
        found_links = sum(1 for r in final_results if r.get('Wikipedia_URL'))
        processed_count = len(final_results)
        total_subjects = len(all_lines)
        timeouts = sum(1 for r in final_results if r.get('Notes') == 'Processing timeout')

        percentage_str = f"({found_links / processed_count * 100:.0f}%)" if processed_count > 0 else "(0%)"
        
        summary_msg = f"Found {found_links:,} Wikipedia links out of {total_subjects:,} total subjects {percentage_str}."
        if processed_count < total_subjects:
            summary_msg = f"Found {found_links:,} links across {processed_count:,} processed records (out of {total_subjects:,} total) {percentage_str}."

    except (IOError, csv.Error) as e:
        logging.error(f"Failed to read final report for summary: {e}")
        # If we can't read the report, we can't give a detailed summary. Exit gracefully.
        if was_interrupted:
            os._exit(1)
        return

    # Step 3: Print the final status message based on whether the run was interrupted.
    if was_interrupted:
        print(f"\n{Fore.YELLOW}WARNING: Processing interrupted by user.")
        print(summary_msg)
        print(f"Partial results sorted and saved to: {output_path} ✨\n")
        if timeouts > 0:
            print(f"{Fore.YELLOW}NOTE: {timeouts:,} records timed out. Re-run the script to retry them.\n")
        os._exit(1)
    else:
        if timeouts > 0:
            print(f"\n{Fore.YELLOW}WARNING: Link finding incomplete.")
            print(summary_msg)
            print(f"Output saved to: {output_path} ✨")
            print(f"{Fore.YELLOW}NOTE: {timeouts:,} records timed out. Please re-run the script to retry them.\n")
        else:
            from config_loader import PROJECT_ROOT
            # Display path relative to the project root for unambiguous logging.
            display_path = os.path.relpath(output_path, PROJECT_ROOT)
            print(f"\n{Fore.GREEN}SUCCESS: Link finding complete.")
            print(summary_msg)
            print(f"{Fore.CYAN}Output saved to: {display_path} ✨{Fore.RESET}\n")

def main():
    # Import here to allow for sandbox path setting
    from config_loader import get_path
    parser = argparse.ArgumentParser(description="Find Wikipedia links for subjects in the raw ADB export.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--work-dir", default=".", help="Set the working directory for all file operations.")
    parser.add_argument("-i", "--input-file", default=None, help="Path to the raw ADB export file.")
    parser.add_argument("-o", "--output-file", default=None, help="Path for the output CSV with found Wikipedia links.")
    parser.add_argument("-w", "--workers", type=int, default=MAX_WORKERS, help="Number of parallel worker threads.")
    parser.add_argument("--force", action="store_true", help="Force reprocessing of all records, overwriting the existing output file.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output, including warnings.")
    args = parser.parse_args()

    if args.work_dir and os.path.isdir(args.work_dir):
        os.chdir(args.work_dir)

    # --- Configure Logging ---
    log_level = logging.INFO if args.verbose else logging.ERROR
    handler = TqdmLoggingHandler()
    handler.setFormatter(CustomFormatter())
    logging.basicConfig(level=log_level, handlers=[handler], force=True)

    input_path = Path(args.input_file or get_path("data/sources/adb_raw_export.txt"))
    output_path = Path(args.output_file or get_path("data/processed/adb_wiki_links.csv"))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        logging.error(f"Input file not found: {input_path}"); sys.exit(1)

    def backup_and_overwrite(file_path: Path):
        """Creates a backup of the file and then deletes the original."""
        try:
            backup_dir = Path(get_path('data/backup'))
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{file_path.stem}.{timestamp}{file_path.suffix}.bak"
            shutil.copy2(file_path, backup_path)
            print(f"{Fore.CYAN}Backed up existing file to: {backup_path}")
            file_path.unlink()
        except (IOError, OSError) as e:
            logging.error(f"Failed to create backup or remove file: {e}")
            sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()[1:]

    # Handle --force flag first for non-interactive overwrite
    if args.force and output_path.exists():
        print(f"{Fore.YELLOW}Forcing overwrite of existing output file...")
        backup_and_overwrite(output_path)
    
    # Automatically re-run if the raw input is newer than the links file
    elif not args.force and output_path.exists() and input_path.exists():
        if os.path.getmtime(input_path) > os.path.getmtime(output_path):
            print(f"{Fore.YELLOW}Input file '{input_path.name}' is newer than the existing links file.")
            print("Stale data detected. Automatically re-running link finding...")
            backup_and_overwrite(output_path)
            # Set force=True for the loader to ensure a full re-run
            args.force = True
    
    processed_ids, timed_out_ids, links_found_before, max_index_before, timeouts_before = load_processed_ids(output_path)

    # If records timed out previously, they need to be retried.
    if timed_out_ids:
        print(f"{Fore.YELLOW}Found {len(timed_out_ids)} records that previously timed out. Retrying them now.")
        
        # Filter the output file to remove the old timed-out entries before appending new results
        temp_path = output_path.with_suffix('.tmp')
        with open(output_path, 'r', encoding='utf-8') as infile, open(temp_path, 'w', encoding='utf-8', newline='') as outfile:
            reader = csv.DictReader(infile)
            writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                if row['idADB'] not in timed_out_ids:
                    writer.writerow(row)
        
        shutil.move(temp_path, output_path)

        # Reload the state from the cleaned file to get an accurate starting point.
        # Crucially, the timeout count is now correctly reset to 0 for the retry run.
        processed_ids, timed_out_ids, links_found_before, max_index_before = load_processed_ids(output_path)
        timeouts_before = 0

    lines_to_process = [
        line for line in all_lines 
        if line.strip() and line.split('\t')[1] not in processed_ids
    ]

    fieldnames = ['Index', 'idADB', 'ADB_Name', 'BirthYear', 'Entry_Type', 'Wikipedia_URL', 'Notes']
    
    if not lines_to_process:
        print(f"\n{Fore.YELLOW}WARNING: The links data file at `{output_path}` is already up to date. ✨")
        print(f"{Fore.YELLOW}If you decide to go ahead with finding links again, a backup of the existing file will be created first.{Fore.RESET}")
        confirm = input("Do you wish to proceed? (Y/N): ").lower().strip()
        if confirm == 'y':
            print(f"{Fore.YELLOW}Forcing overwrite of existing output file...")
            backup_and_overwrite(output_path)
            # Re-initialize state for a full run
            processed_ids, links_found_before, max_index_before, timeouts_before = set(), 0, 0, 0
            lines_to_process = all_lines
        else:
            print(f"\n{Fore.YELLOW}Operation cancelled by user.{Fore.RESET}\n")
            # We still call finalize here to print the summary of the existing file.
            finalize_and_report(output_path, fieldnames, all_lines, was_interrupted=False)
            sys.exit(0)

    if processed_ids:
        print(f"\n{Fore.YELLOW}--- Resuming Link Finding ---")
        print(f"Found {len(processed_ids):,} already processed records ({links_found_before:,} links found).")
        print(f"Now processing {len(lines_to_process):,} new records using {args.workers} workers.")
    else:
        print("\n--- Finding Wikipedia Links ---")
        print(f"Processing {len(lines_to_process):,} records using {args.workers} workers.")

    print(f"{Fore.YELLOW}NOTE: Each set of 1,000 records can take 3 minutes or more to process.{Fore.RESET}")
    print("You can safely interrupt with Ctrl+C at any time to resume later.\n")

    links_found_this_session, timeouts_this_session = 0, 0
    links_found_lock, timeouts_lock = Lock(), Lock()
    was_interrupted = False
    
    executor = ThreadPoolExecutor(max_workers=args.workers)
    output_file = None
    
    try:
        # Open file in append mode and write header if it's a new file
        is_new_file = not output_path.exists()
        output_file = open(output_path, 'a', encoding='utf-8', newline='')
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        if is_new_file:
            writer.writeheader()

        with tqdm(total=len(lines_to_process), desc="Finding links", ncols=120, smoothing=0.01) as pbar:
            tasks = [(max_index_before + i + 1, line) for i, line in enumerate(lines_to_process)]
            futures = {executor.submit(worker_task_with_timeout, line, pbar, index) for index, line in tasks}
            
            while futures:
                try:
                    for future in as_completed(futures, timeout=1):
                        res = future.result()
                        if res:
                            notes = res.get('Notes', '')
                            if res.get('Wikipedia_URL') and 'timeout' not in notes:
                                with links_found_lock:
                                    links_found_this_session += 1
                            elif 'timeout' in notes:
                                with timeouts_lock:
                                    timeouts_this_session += 1
                            try:
                                writer.writerow(res)
                            except (IOError, csv.Error) as e:
                                logging.error(f"Error writing row for idADB {res.get('idADB')}: {e}")
                        
                        pbar.update(1)
                        futures.remove(future)
                        
                        # Update progress bar with total counts
                        total_links = links_found_before + links_found_this_session
                        total_processed = len(processed_ids) + pbar.n
                        total_timeouts = timeouts_before + timeouts_this_session
                        percentage = (total_links / total_processed) * 100 if total_processed > 0 else 0
                        
                        postfix_str = f"Links found: {total_links:,}/{total_processed:,} ({percentage:.0f}%)"
                        if total_timeouts > 0:
                            postfix_str += f", Timeouts: {total_timeouts:,}"
                        pbar.set_postfix_str(postfix_str)
                except TimeoutError:
                    pass

    except KeyboardInterrupt:
        was_interrupted = True
        # We must finalize here because the finally block might hang and os._exit will prevent
        # the code below from running.
        if output_file and not output_file.closed:
            output_file.close()
        finalize_and_report(output_path, fieldnames, all_lines, was_interrupted=True)
    
    finally:
        if was_interrupted:
            executor.shutdown(wait=False, cancel_futures=True)
        else:
            executor.shutdown(wait=True)
        if output_file and not output_file.closed:
            output_file.close()

    # On successful completion, call finalize_and_report.
    if not was_interrupted:
        finalize_and_report(output_path, fieldnames, all_lines, was_interrupted=False)

if __name__ == "__main__":
    main()

# === End of src/find_wikipedia_links.py ===

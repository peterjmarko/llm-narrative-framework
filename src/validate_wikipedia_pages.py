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
# Filename: src/validate_wikipedia_pages.py

"""
Validates Wikipedia page content and generates the final validation reports.

This script takes the intermediate file of Wikipedia links and performs an
intensive, content-level validation for each page to ensure data quality before
any expensive LLM-based processing occurs.

Key Features:
-   **Sandbox-Aware**: Fully supports sandboxed execution via a `--sandbox-path`
    argument for isolated testing.
-   **Intelligent Validation**: The script's validation process includes:
    1.  **Resolving Redirects:** Follows all HTTP redirects, meta-refresh tags,
        and canonical URL declarations to find the true source page.
    2.  **Handling Disambiguation:** Detects disambiguation pages and
        intelligently searches for the correct subject link using their birth
        year.
    3.  **Validating Names:** Performs a fuzzy string comparison between the ADB
        name and the Wikipedia article title to check for mismatches.
    4.  **Verifying Death Date:** Uses a multi-strategy approach to confirm
        that the subject is deceased by checking infoboxes, categories, and text
        patterns.
-   **Comprehensive Reporting**: Upon completion, it produces two key outputs:
    - A detailed, machine-readable CSV report (`adb_validation_report.csv`).
    - A human-readable text summary (`adb_validation_summary.txt`).
-   **Resumable & Flexible**: The script is fully resumable, interrupt-safe, and
    includes a `--report-only` flag to regenerate the text summary from an
    existing CSV report without re-running the validation.
"""

import argparse
import csv
import json
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

# Ensure the src directory is in the Python path for nested imports
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.file_utils import backup_and_remove  # noqa: E402

# Initialize colorama
init(autoreset=True, strip=False)

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
            msg = self.format(record)
            # Use print instead of tqdm.write to avoid interfering with progress bar
            print(msg)
            self.flush()
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

def validate_name(subject_name: str, soup: BeautifulSoup) -> tuple[str, int]:
    """Extracts Wikipedia name and compares it to the Subject name."""
    wp_name_tag = soup.find('h1', id='firstHeading')
    wp_name = wp_name_tag.get_text(strip=True) if wp_name_tag else "Name Not Found"
    
    # The incoming name is already sanitized, so we just need to handle the format.
    if ',' in subject_name:
        subject_base_name = ' '.join(reversed(subject_name.split(',', 1))).strip()
    else:
        subject_base_name = subject_name.strip()

    wp_base_name = re.sub(r'\s*\(.*\)$', '', wp_name).strip()
    return wp_name, fuzz.ratio(subject_base_name.lower(), wp_base_name.lower())

def validate_death_date(soup: BeautifulSoup) -> bool:
    """Exhaustive death date detection using multiple strategies and locations."""
    # Strategy 1: Check categories first (most reliable for Wikipedia)
    categories_div = soup.find('div', id='mw-normal-catlinks')
    if categories_div:
        cat_text = categories_div.get_text()
        if re.search(r'\bLiving people\b', cat_text):
            return False
        death_category_patterns = [
            r'\d{4} deaths', r'Deaths in \d{4}', r'\d{4} births', r'People who died',
            r'Murdered', r'Executed', r'Suicides', r'Assassination', r'victims'
        ]
        for pattern in death_category_patterns:
            if re.search(pattern, cat_text, re.I):
                return True
    
    # Strategy 2: Infobox check (multiple field names)
    infobox = soup.find('table', class_='infobox')
    if infobox:
        death_headers = [
            r'\bDied\b', r'\bDeath\b', r'\bDeceased\b', r'\bResting place\b',
            r'\bBuried\b', r'\bDeath date\b', r'\bDate of death\b', r'\bDisappeared\b'
        ]
        for header_pattern in death_headers:
            header = infobox.find(lambda tag: tag.name in ['th', 'td', 'caption'] and re.search(header_pattern, tag.get_text(strip=True), re.I))
            if header:
                if re.search(r'\d{4}', header.get_text(strip=True)): return True
                next_cell = header.find_next_sibling()
                if next_cell and re.search(r'\d{4}', next_cell.get_text()): return True
                if header.name == 'th':
                    parent_row = header.find_parent('tr')
                    if parent_row and parent_row.find('td') and re.search(r'\d{4}', parent_row.find('td').get_text()):
                        return True
    
    # Strategy 3: First paragraph analysis
    paragraphs = [p for p in soup.find_all('p') if len(p.get_text(strip=True)) > 20 and not p.get_text(strip=True).startswith('Coordinates:')]
    for p in paragraphs[:10]:
        text = p.get_text()
        if re.search(r'\([^)]*\b\d{3,4}\b[^)]*[–—\-][^)]*\b\d{3,4}\b[^)]*\)', text):
            return True
        if re.search(r'\bwas\s+(?:a|an)\s+\w+', text, re.I) and not re.search(r'was\s+(?:a|an)\s+\w+\s+(?:from|between|during|in\s+\d{4})', text, re.I):
            if re.search(r'\b(?:1[0-9]{3}|20[0-2][0-9])\b', text):
                return True
        death_patterns = [
            r'\b(?:died|d\.)\s+(?:on\s+)?[\w\s,]*\b\d{4}\b', r'†\s*[\w\s,]*\b\d{4}\b',
            r'\b(?:deceased|death)\b.*\b\d{4}\b', r'\b(?:passed away|passing)\b.*\b\d{4}\b',
            r'\b(?:killed|murdered|executed)\b.*\b\d{4}\b', r'\b(?:perished|drowned|crashed)\b.*\b\d{4}\b',
            r'\b(?:suicide|hanged)\b.*\b\d{4}\b', r'\blast seen\b.*\b\d{4}\b',
            r'\b(?:found dead|body found)\b',
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\s*[)–—\-]'
        ]
        for pattern in death_patterns:
            if re.search(pattern, text, re.I):
                return True
    
    # Strategy 4: Check other infobox table formats
    for table in soup.find_all('table', class_=re.compile(r'infobox|biography|vcard', re.I)):
        text = table.get_text()
        if re.search(r'\bDied\b.*\d{4}', text, re.I): return True
        if re.search(r'[–—\-]\s*\d{1,2}\s+\w+\s+\d{4}', text): return True
    
    # Strategy 5: Check hatnotes
    for hatnote in soup.find_all('div', class_=re.compile(r'hatnote')):
        if re.search(r'\b(?:died|deceased)\b.*\d{4}', hatnote.get_text(), re.I):
            return True
    
    # Strategy 6: Check "Death" section headers
    if soup.find_all(['h2', 'h3'], string=re.compile(r'\bDeath\b|\bFinal\b|\bLast\s+years\b|\bPassing\b', re.I)):
        return True
    
    # Strategy 7: Special Wikipedia templates
    if soup.find_all(attrs={'class': re.compile(r'death-date|deathdate|dday', re.I)}):
        return True
    
    # Strategy 8: Check image captions
    for caption in soup.find_all(['div', 'p'], class_=re.compile(r'caption|thumb', re.I)):
        if re.search(r'\b\d{4}\s*[–—\-]\s*\d{4}\b', caption.get_text()):
            return True
    
    return False

def process_wikipedia_page(url: str, subject_name: str, birth_year: str, pbar: tqdm, depth=0) -> dict:
    """Scrapes and validates a Wikipedia page with robust disambiguation handling."""
    if depth >= MAX_DISAMBIGUATION_DEPTH:
        return {'status': 'FAIL', 'notes': 'Max disambiguation depth reached'}

    final_url, soup = follow_all_redirects(url)
    if not soup:
        return {'status': 'ERROR', 'notes': 'Failed to fetch Wikipedia page'}

    if is_disambiguation_page(soup):
        logging.info(f"Disambiguation page for {subject_name}. Searching for birth year '{birth_year}'...")
        matching_url = find_matching_disambiguation_link(soup, birth_year)
        if matching_url:
            return process_wikipedia_page(matching_url, subject_name, birth_year, pbar, depth + 1)
        return {'status': 'FAIL', 'notes': f"Disambiguation page, no link with year {birth_year} found"}

    wp_name, name_score = validate_name(subject_name, soup)
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

    # If the record already has notes from the link-finder, it's a pre-existing failure.
    # Pass it through without modification to preserve the original error reason.
    if row.get('Notes'):
        status = 'VALID' if row['Entry_Type'] == 'Research' else 'FAIL'
        return {**result, 'Status': status, 'Notes': row['Notes']}

    # If there's no URL and no notes, it's a simple "No Link" failure.
    if not row.get('Wikipedia_URL'):
        status = 'VALID' if row['Entry_Type'] == 'Research' else 'FAIL'
        notes = 'Research entry - Wikipedia not expected' if row['Entry_Type'] == 'Research' else 'No Wikipedia URL found'
        return {**result, 'Status': status, 'Notes': notes}

    # Only proceed with validation if a URL is present and there were no prior errors.
    validation = process_wikipedia_page(row['Wikipedia_URL'], row['Subject_Name'], row['BirthYear'], pbar)
    
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
        logging.error(f"\nInput file not found: {input_path}"); sys.exit(1)

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

def finalize_and_report(output_path: Path, fieldnames: list, total_subjects: int, was_interrupted: bool = False):
    """Sorts the final CSV, generates the summary, and prints the final status message."""
    from config_loader import PROJECT_ROOT, get_path
    sort_output_file(output_path, fieldnames)
    generate_summary_report(output_path) # This already prints the full summary to console
    
    # Correctly get the summary path from the config for display purposes
    summary_path = Path(get_path("data/reports")) / "adb_validation_summary.txt"
    
    display_output_path = os.path.relpath(output_path, PROJECT_ROOT).replace('\\', '/')
    display_summary_path = os.path.relpath(summary_path, PROJECT_ROOT).replace('\\', '/')

    if was_interrupted:
        print(f"\n{Fore.YELLOW}WARNING: Validation incomplete.")
        print(f"Partial results have been sorted and saved.")
        print(f"{Fore.CYAN}  - Detailed Report: {display_output_path}")
        print(f"{Fore.CYAN}  - Summary Report:  {display_summary_path}")
        print(f"{Fore.YELLOW}\nPlease re-run the script to resume validation.\n")
        os._exit(1)
    else:
        # Get final counts for the success message
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            total_count = len(rows)
            valid_count = sum(1 for row in rows if row.get('Status') in ['OK', 'VALID'])
        except Exception:
            # Fallback if we can't read/parse the file
            total_count = total_subjects
            valid_count = -1 # Sentinel value

        print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
        print(f"{Fore.CYAN} - Detailed report saved to: {display_output_path}{Fore.RESET}")
        print(f"{Fore.CYAN} - Summary report saved to: {display_summary_path}{Fore.RESET}")

        # Determine success or failure for coloring
        if total_count > 0 and valid_count == 0:
            key_metric = f"Processed {total_count:,} records but found 0 valid subjects"
            print(f"\n{Fore.RED}FAILURE: {key_metric}. Please review the validation summary.{Fore.RESET}\n")
        else:
            key_metric = f"{total_count:,} records processed"
            print(f"\n{Fore.GREEN}SUCCESS: {key_metric}. Validation completed successfully.{Fore.RESET}")

def generate_summary_report(validated_subjects_path: Path):
    """Reads the detailed CSV report and generates a summary text file."""
    from config_loader import get_path, PROJECT_ROOT
    if not validated_subjects_path.exists():
        print(f"{Fore.RED}ERROR: Input file not found at '{validated_subjects_path}'")
        return

    # Correctly define the output path for the summary in the reports directory
    reports_dir = Path(get_path("data/reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)
    summary_path = reports_dir / "adb_validation_summary.txt"
    
    if summary_path.exists():
        try:
            backup_dir = Path(get_path('data/backup'))
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{summary_path.stem}.{timestamp}{summary_path.suffix}.bak"
            shutil.copy2(summary_path, backup_path)
            display_backup_path = os.path.relpath(backup_path, PROJECT_ROOT).replace('\\', '/')
            print(f"Backed up existing summary to: {display_backup_path}")
        except (IOError, OSError) as e:
            print(f"{Fore.YELLOW}Could not create backup for summary report: {e}")
            
    # Initialize counters
    total_records, valid_records, failed_records = 0, 0, 0
    no_wiki_link, fetch_fail, no_death, name_mismatch, disambiguation_fail = 0, 0, 0, 0, 0
    timeout_error, non_english_error, other_errors = 0, 0, 0
    research_entries, person_entries = 0, 0

    try:
        with open(validated_subjects_path, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
            total_records = len(rows)

        if total_records == 0:
            print(f"{Fore.YELLOW}Warning: Validated subjects file is empty. Cannot generate summary.")
            return

        # Aggregate data
        for row in rows:
            if row.get('Entry_Type') == 'Research': research_entries += 1
            else: person_entries += 1
            
            if row.get('Status') in ['OK', 'VALID']:
                valid_records += 1
            else:
                failed_records += 1
                notes = row.get('Notes', '')
                if 'Processing timeout' in notes: timeout_error += 1
                elif 'Non-English URL' in notes: non_english_error += 1
                elif 'No Wikipedia URL' in notes: no_wiki_link += 1
                elif 'Failed to fetch' in notes: fetch_fail += 1
                elif 'Disambiguation' in notes: disambiguation_fail += 1
                elif 'Name mismatch' in notes: name_mismatch += 1
                elif 'Death date not found' in notes: no_death += 1
                else: other_errors += 1
        
        # --- Update Pipeline Completion Info JSON ---
        try:
            completion_info_path = Path(get_path("data/reports/pipeline_completion_info.json"))
            report_path_relative = os.path.relpath(validated_subjects_path, PROJECT_ROOT).replace('\\', '/')
            completion_rate = (valid_records / total_records * 100) if total_records > 0 else 0
            
            step_data = {
                "step_name": "Validate Wikipedia Pages",
                "completion_rate": completion_rate,
                "processed_count": total_records,
                "passed_count": valid_records,
                "failed_count": failed_records,
                "report_path": report_path_relative
            }
            
            pipeline_data = {}
            if completion_info_path.exists():
                with open(completion_info_path, 'r', encoding='utf-8') as f:
                    try:
                        # Handle case where file is empty
                        content = f.read()
                        if content:
                            pipeline_data = json.loads(content)
                    except json.JSONDecodeError:
                        print(f"{Fore.YELLOW}Warning: Could not parse existing completion info JSON. Overwriting.")

            pipeline_data["validate_wikipedia_pages"] = step_data

            with open(completion_info_path, 'w', encoding='utf-8') as f:
                json.dump(pipeline_data, f, indent=2)

        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not update pipeline completion info JSON: {e}")

        # --- Build Formatted Report ---
        title = "Astro-Databank Validation Summary"
        banner_width = 60; banner = "=" * banner_width
        label_col, count_col, perc_col = 35, 12, 10

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
                perc_str = f"({count/total_records:.1%})"
                line = f"{label:<{label_col}}{count:>{count_col},}{perc_str:>{perc_col}}"
                failure_analysis.append(line)
        
        # For the console version, with colors
        report_lines_color = [
            banner, title.center(banner_width), banner,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            *overall_stats, *entry_type_stats, *failure_analysis,
            banner
        ]
        
        # For the file version, strip ANSI color codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        report_lines_plain = [ansi_escape.sub('', line) for line in report_lines_color]
        
        # Write the plain text version to the file
        summary_content_plain = "\n".join(report_lines_plain)
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_content_plain)

        # Print the color version to the console
        summary_content_color = "\n".join(report_lines_color)
        print("\n" + summary_content_color)

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
        tqdm.write(f"{Fore.YELLOW}Worker timeout for idADB {row.get('idADB')} ({row.get('Subject_Name')}). Skipping.")
        # Return a result that preserves input data but marks it as a timeout failure
        return {**row, 'Index': index, 'Status': 'FAIL', 'Notes': 'Processing timeout'}

    result = result_queue.get()
    if isinstance(result, Exception):
        raise result
        
    return result


def main():
    os.system('')
    parser = argparse.ArgumentParser(description="Validate Wikipedia page content for ADB subjects.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--sandbox-path", help="Specify a sandbox directory for all file operations.")
    parser.add_argument("-w", "--workers", type=int, default=MAX_WORKERS, help="Number of parallel worker threads.")
    parser.add_argument("--force", action="store_true", help="Force reprocessing of all records.")
    parser.add_argument("--report-only", action="store_true", help="Generate the summary report for an existing validation CSV and exit.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress bar output for non-interactive runs.")
    args = parser.parse_args()

    # If a sandbox path is provided, set the environment variable.
    # This must be done before any other modules are used.
    if args.sandbox_path:
        os.environ['PROJECT_SANDBOX_PATH'] = os.path.abspath(args.sandbox_path)

    # Now that the environment is set, we can safely load modules that depend on it.
    from config_loader import get_path, PROJECT_ROOT

    # --- Configure Logging ---
    log_level = logging.INFO if args.verbose else logging.ERROR
    handler = TqdmLoggingHandler()
    handler.setFormatter(CustomFormatter())
    logging.basicConfig(level=log_level, handlers=[handler], force=True)

    input_path = Path(get_path("data/processed/adb_wiki_links.csv"))
    output_path = Path(get_path("data/processed/adb_validated_subjects.csv"))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.report_only:
        print(f"\n{Fore.YELLOW}--- Generating Summary Report Only ---")
        generate_summary_report(output_path)
        sys.exit(0)

    # --- Intelligent Startup Logic ---
    # Check for stale data first. If the input is newer, we must force a re-run.
    if not args.force and output_path.exists() and input_path.exists():
        if os.path.getmtime(input_path) > os.path.getmtime(output_path):
            print(f"{Fore.YELLOW}\nInput file '{input_path.name}' is newer than the report. Stale data detected.")
            print("Automatically forcing a re-run...{Fore.RESET}")
            args.force = True

    # If --force is active (either from the command line or stale data),
    # back up and delete the old report before loading the state.
    if args.force and output_path.exists():
        print(f"{Fore.YELLOW}\n--force is active. Backing up and removing existing report to ensure a clean run.{Fore.RESET}")
        backup_and_remove(output_path)
    
    # Now, load the current state. This will be a fresh start if --force was used.
    records_to_process, timed_out_ids, max_index_before, valid_before, processed_before, total_subjects = load_and_filter_input(input_path, output_path, args.force)

    # If there's nothing to do, the process is complete.
    if not records_to_process:
        print(f"\n{Fore.GREEN}All records are already validated and up to date.{Fore.RESET}")
        # An interactive prompt to force a re-run is not needed for this script,
        # as a re-run can be triggered with the --force flag.
        generate_summary_report(output_path)
        sys.exit(0)

    # Propagate the new column name and drop the old one from the fieldnames list
    fieldnames = ['Index', 'idADB', 'Subject_Name', 'Entry_Type', 'WP_URL', 'WP_Name', 'Name_Match_Score', 'Death_Date_Found', 'Status', 'Notes']
        
    print(f"\n{Fore.YELLOW}--- Validating Wikipedia Pages ---")
    print(f"Found {processed_before:,} already processed records ({valid_before:,} valid).")
    print(f"Now processing {len(records_to_process):,} new records using {args.workers} workers.")
    print(f"{Fore.YELLOW}NOTE: Each set of 10,000 records can take 15 minutes or more to process.")
    print(f"You can safely interrupt with Ctrl+C at any time to resume later.\n")

    was_interrupted = False
    valid_this_session = 0
    valid_lock = Lock()
    executor = ThreadPoolExecutor(max_workers=args.workers)
    output_file = None

    try:
        # Determine file mode: 'w' if no file exists, 'a' if resuming
        is_new_file = not output_path.exists()
        file_mode = 'w' if is_new_file else 'a'
        output_file = open(output_path, file_mode, encoding='utf-8', newline='')
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        if is_new_file:
            writer.writeheader()

        with tqdm(total=len(records_to_process), desc="Validating pages", ncols=100, smoothing=0.01, disable=args.quiet) as pbar:
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
                        
                        # Update progress bar with total counts (less frequently to avoid display issues)
                        if pbar.n % 10 == 0 or pbar.n == len(records_to_process):  # Update every 10 items or at completion
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
    finalize_and_report(output_path, fieldnames, total_subjects, was_interrupted)

if __name__ == "__main__":
    main()

# === End of src/validate_wikipedia_pages.py ===

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
# Filename: src/validate_adb_data.py

"""
Audits the raw Astro-Databank export file against live Wikipedia data.

This script serves as a data quality assurance tool for the foundational
dataset (`adb_raw_export.txt`). For each entry, it performs a series of
automated checks:

1.  **Scrapes the ADB Page:** Visits the subject's Astro-Databank page to
    find the link to their English Wikipedia article, intelligently handling
    non-English links by finding the English equivalent.
2.  **Validates Wikipedia Page:**
    - Confirms that the Wikipedia page exists and can be accessed.
    - Handles disambiguation pages by using the subject's birth year to find
      the correct article.
    - Scrapes the final Wikipedia page to extract the canonical URL, article
      title (name), and infobox/paragraph data.
3.  **Compares Names:** Performs a fuzzy string comparison between the name
    from ADB and the name from the Wikipedia article title to detect typos
    or mismatches.
4.  **Verifies Death Date:** Checks for the presence of a "Died" field in
    the Wikipedia infobox and includes a fallback to search the opening
    paragraphs of the article.

The script produces a detailed CSV report (`adb_validation_report.csv`) that
flags any entries with missing links, name mismatches, or missing death dates,
facilitating manual review and correction of the source data.
"""

import argparse
import csv
import logging
import re
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup
from thefuzz import fuzz
from tqdm import tqdm

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- Global Shutdown Flag ---
shutdown_event = threading.Event()

# --- ANSI Color Codes ---
class Colors:
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RESET = '\033[0m'

# --- Constants ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT = 15
NAME_MATCH_THRESHOLD = 90
MAX_DISAMBIGUATION_DEPTH = 3 # Prevent infinite recursion
MAX_WORKERS = 4 # Number of parallel threads
REQUEST_DELAY = 0.1 # seconds

# --- Helper Functions ---

def get_processed_arns(filepath: Path) -> tuple[set, int]:
    """Reads an existing report and returns a set of ARNs and count of 'OK' statuses."""
    if not filepath.exists():
        return set(), 0
    
    processed_arns = set()
    ok_count = 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('ARN'):
                    processed_arns.add(row['ARN'])
                if row.get('Status') == 'OK':
                    ok_count += 1
        return processed_arns, ok_count
    except (IOError, csv.Error) as e:
        logging.warning(f"Could not read existing report at '{filepath}': {e}. Starting from scratch.")
        return set(), 0

def fetch_page_content(url: str) -> BeautifulSoup | None:
    """Fetches and parses a web page, returning a BeautifulSoup object."""
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException:
        # Suppress verbose logging for common network errors in parallel mode
        return None

def get_initial_wiki_url_from_adb(adb_url: str) -> str | None:
    """Scrapes an ADB page to find any Wikipedia URL."""
    soup = fetch_page_content(adb_url)
    if not soup:
        return None
    
    # Make the 's' in 'https' optional to match both http and https links
    wiki_link = soup.find('a', href=re.compile(r"https?://\w+\.wikipedia\.org/wiki/"))
    return wiki_link['href'] if wiki_link else None

def get_english_wiki_url(initial_url: str) -> str | None:
    """Takes any language Wikipedia URL and finds the English equivalent."""
    if 'en.wikipedia.org' in initial_url:
        return initial_url

    soup = fetch_page_content(initial_url)
    if soup:
        en_link = soup.find('a', class_='interlanguage-link-target', lang='en')
        if en_link and en_link.has_attr('href'):
            return en_link['href']
    return None

def process_wikipedia_page(url: str, adb_name: str, birth_year: str, pbar: tqdm, depth=0) -> dict:
    """
    Scrapes and validates a Wikipedia page, handling disambiguation.
    Returns a dictionary with validation results.
    """
    if depth >= MAX_DISAMBIGUATION_DEPTH:
        return {'status': 'ERROR', 'notes': 'Max disambiguation depth reached'}

    soup = fetch_page_content(url)
    if not soup:
        return {'status': 'ERROR', 'notes': 'Failed to fetch Wikipedia page'}

    # Prioritize the canonical URL
    canonical_link = soup.find('link', rel='canonical')
    final_url = canonical_link['href'] if canonical_link else url

    # --- Disambiguation Check ---
    is_disambiguation = soup.find('div', id='disambiguation') or soup.find(string=re.compile("may refer to:"))
    if is_disambiguation:
        pbar.write(f"INFO: Disambiguation page found for {final_url}. Searching for birth year '{birth_year}'...")
        list_items = soup.find_all('li')
        for item in list_items:
            if birth_year in item.get_text():
                link = item.find('a')
                if link and link.has_attr('href'):
                    new_url = urljoin(final_url, link['href'])
                    pbar.write(f"INFO:   -> Found matching link: {new_url}")
                    return process_wikipedia_page(new_url, adb_name, birth_year, pbar, depth + 1)
        return {'status': 'FAIL', 'notes': f"Disambiguation page, but no link with year {birth_year} found"}

    # --- Standard Validation on a non-disambiguation page ---
    wp_name, name_score = validate_name(adb_name, soup)
    death_date_found = validate_death_date(soup)
    
    return {
        'status': 'OK',
        'final_url': final_url,
        'wp_name': wp_name,
        'name_score': name_score,
        'death_date_found': death_date_found
    }

def validate_name(adb_name: str, soup: BeautifulSoup) -> tuple[str, int]:
    """Extracts Wikipedia name and compares it to the ADB name."""
    wp_name_tag = soup.find('h1', id='firstHeading')
    wp_name = wp_name_tag.get_text(strip=True) if wp_name_tag else "Name Not Found"
    
    # Create a "base name" for the ADB entry by removing parenthetical year
    adb_base_name = re.sub(r'\s*\(\d{4}\)$', '', adb_name).strip()
    if ',' in adb_base_name:
        adb_base_name = ' '.join(reversed(adb_base_name.split(',', 1))).strip()

    # Create a "base name" for the Wikipedia entry by removing any parenthetical
    wp_base_name = re.sub(r'\s*\(.*\)$', '', wp_name).strip()
        
    # Perform fuzzy match on the base names
    score = fuzz.ratio(adb_base_name.lower(), wp_base_name.lower())
    return wp_name, score

def validate_death_date(soup: BeautifulSoup) -> bool:
    """Checks for a death date in the infobox or opening paragraphs."""
    # 1. Check infobox
    infobox = soup.find('table', class_='infobox')
    if infobox and infobox.find('th', string=re.compile(r'\bDied\b', re.I)):
        return True

    # 2. Fallback: Check first few paragraphs for a date range
    for p in soup.find_all('p', limit=3):
        if re.search(r'\(\s*c?\.\s*\d{4}\s*–\s*\d{4}\s*\)', p.get_text()):
            return True
            
    return False

def sort_report_by_arn(filepath: Path, fieldnames: list):
    """Reads the report CSV, sorts it by ARN, and writes it back."""
    if not filepath.exists():
        return

    try:
        with open(filepath, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            # Read all rows and convert ARN to int for correct sorting
            data = sorted(list(reader), key=lambda row: int(row['ARN']))
        
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    except (IOError, csv.Error, KeyError, ValueError) as e:
        logging.error(f"Could not sort the final report file: {e}")


def worker_task(line: str, pbar: tqdm) -> dict:
    """The main validation logic for a single line, designed to be run in a thread."""
    if shutdown_event.is_set():
        return None # Exit early if shutdown is requested

    time.sleep(REQUEST_DELAY) # Add a small delay to be a polite scraper
    parts = line.strip().split('\t')
    if len(parts) < 4: return None

    arn, adb_name_raw, birth_date = parts[0], unquote(parts[1]), parts[3]
    birth_year = birth_date.split('-')[0]
    
    match = re.match(r'^(.*?)\s*\((http.*?)\)$', adb_name_raw)
    if not match:
        return {'ARN': arn, 'Status': 'ERROR', 'Notes': 'Could not parse Name/URL field'}

    adb_name, adb_url = match.groups()
    result = {'ARN': arn, 'ADB_Name': adb_name.strip()}

    initial_wiki_url = get_initial_wiki_url_from_adb(adb_url)
    if not initial_wiki_url:
        return {**result, 'Status': 'ERROR', 'Notes': 'No Wikipedia link found on ADB page'}
    
    english_wiki_url = get_english_wiki_url(initial_wiki_url)
    if not english_wiki_url:
        return {**result, 'Status': 'ERROR', 'Notes': 'Found non-English WP link, but no English equivalent'}
    
    validation_data = process_wikipedia_page(english_wiki_url, adb_name, birth_year, pbar)

    if validation_data['status'] != 'OK':
        return {**result, 'Status': validation_data['status'], 'Notes': validation_data['notes']}
    
    final_status, notes = 'OK', []
    if validation_data['name_score'] < NAME_MATCH_THRESHOLD:
        final_status = 'FAIL'
        notes.append(f"Name mismatch (Score: {validation_data['name_score']})")
    if not validation_data['death_date_found']:
        final_status = 'FAIL'
        notes.append("Death date not found")

    return {
        **result, 'WP_URL': validation_data['final_url'], 'WP_Name': validation_data['wp_name'],
        'Name_Match_Score': validation_data['name_score'], 'Death_Date_Found': validation_data['death_date_found'],
        'Status': final_status, 'Notes': '; '.join(notes)
    }

def main():
    os.system('') # Enables ANSI escape codes on Windows
    parser = argparse.ArgumentParser(description="Validate raw ADB export data against live Wikipedia pages.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-i", "--input-file", default="data/sources/adb_raw_export.txt", help="Path to the raw ADB export file.")
    parser.add_argument("-o", "--output-file", default="data/reports/adb_validation_report.csv", help="Path for the output validation report CSV.")
    parser.add_argument("--start-from", type=int, default=1, help="The ARN to start processing from (inclusive).")
    parser.add_argument("--stop-at", type=int, default=0, help="The ARN to stop processing at (inclusive). 0 for no limit.")
    parser.add_argument("-w", "--workers", type=int, default=MAX_WORKERS, help="Number of parallel worker threads.")
    args = parser.parse_args()
    
    input_path, output_path = Path(args.input_file), Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        logging.error(f"Input file not found: {input_path}"); sys.exit(1)

    fieldnames = ['ARN', 'ADB_Name', 'WP_URL', 'WP_Name', 'Name_Match_Score', 'Death_Date_Found', 'Status', 'Notes']
    if output_path.exists():
        sort_report_by_arn(output_path, fieldnames)

    processed_arns, initial_ok_count = get_processed_arns(output_path)
    
    with open(input_path, 'r', encoding='utf-8') as infile:
        all_lines = infile.readlines()[1:]

    lines_to_process = []
    for line in all_lines:
        try:
            arn = line.split('\t')[0]
            arn_val = int(arn)
            if arn in processed_arns or arn_val < args.start_from or (args.stop_at > 0 and arn_val > args.stop_at):
                continue
            lines_to_process.append(line)
        except (IndexError, ValueError):
            continue

    if not lines_to_process:
        logging.info("All records in the specified range have already been processed.")
        sort_report_by_arn(output_path, fieldnames)
        return

    print("-" * 70)
    print("NOTE: This script performs live web scraping for thousands of records")
    print("      and may take over an hour to complete the first time.")
    print("      You can safely interrupt with 'Ctrl+C' and resume at any time.")
    print("-" * 70)
    
    if not processed_arns:
        start_msg = f"Starting validation for {len(all_lines):,} records using {args.workers} workers. Output will be saved to '{output_path}'."
    else:
        start_msg = f"Found {len(processed_arns):,} previously processed records ({initial_ok_count:,} valid). Resuming validation of {len(lines_to_process):,} records using {args.workers} workers."
    print(f"{Colors.YELLOW}INFO: {start_msg}{Colors.RESET}")
    
    file_exists = output_path.exists() and len(processed_arns) > 0
    was_interrupted = False
    pbar = tqdm(total=len(lines_to_process), desc="Validating records", ncols=80, smoothing=0.01)
    session_ok_count = 0
    executor = ThreadPoolExecutor(max_workers=args.workers)
    futures = {executor.submit(worker_task, line, pbar) for line in lines_to_process}
    
    try:
        with open(output_path, 'a', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()

            for future in as_completed(futures):
                pbar.update(1)
                try:
                    res = future.result()
                    if res:
                        writer.writerow(res)
                        if res.get('Status') == 'OK':
                            session_ok_count += 1
                except Exception as exc:
                    logging.error(f'An exception occurred while processing a result: {exc}')

    except KeyboardInterrupt:
        was_interrupted = True
        if pbar: pbar.close()
        print(f"\n{Colors.YELLOW}WARNING: Shutdown signal received. Cancelling pending tasks...{Colors.RESET}")
        shutdown_event.set()
        for f in futures:
            if not f.done():
                f.cancel()
    finally:
        if pbar and not pbar.disable:
             pbar.close()
        executor.shutdown(wait=True)
        
        # Always sort the report file at the end of the run
        sort_report_by_arn(output_path, fieldnames)

        total_ok_count = initial_ok_count + session_ok_count
        processed_this_session = pbar.n if pbar else 0
        total_processed = len(processed_arns) + processed_this_session
        remaining_records = len(all_lines) - total_processed

        if not was_interrupted:
            final_msg = f"Processing of {len(all_lines):,} records finished ({total_ok_count:,} valid). Full report saved at: {output_path}"
            print(f"{Colors.GREEN}INFO: {final_msg}{Colors.RESET}")
        else:
            final_msg = (
                f"Process interrupted. {processed_this_session:,} records processed this session. "
                f"Total valid: {total_ok_count:,}. Remaining: {remaining_records:,}."
            )
            print(f"{Colors.YELLOW}INFO: {final_msg}{Colors.RESET}")

if __name__ == "__main__":
    main()

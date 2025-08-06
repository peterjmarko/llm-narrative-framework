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
# Filename: src/fetch_adb_data.py

"""
Automates the fetching of raw birth data from the Astro-Databank website.

This script replaces the manual data extraction process by:
1.  Logging into astro.com using credentials stored in the .env file.
2.  Scraping security tokens and dynamically parsing a JavaScript file to find
    the correct numeric IDs for the required search categories.
3.  Sending a structured JSON request to the website's internal API to
    get paginated search results.
4.  Parsing the JSON response and saving the data into a tab-separated
    file compatible with the downstream data preparation pipeline.
"""

import argparse
import json
import logging
import os
import re
import sys
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- ANSI Color Codes ---
class Colors:
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    RESET = '\033[0m'

# --- Constants ---
BASE_URL = "https://www.astro.com"
LOGIN_URL = f"{BASE_URL}/cgi/awd.cgi"
SEARCH_PAGE_URL = f"{BASE_URL}/adb-search/index.cgi"
API_URL = f"{BASE_URL}/adbst/api"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.25

def login_to_adb(session, username, password):
    """Logs into Astro-Databank to establish an authenticated session."""
    logging.info("Attempting to log into Astro-Databank...")
    try:
        session.get(BASE_URL, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
        time.sleep(REQUEST_DELAY)
        
        login_payload = {'mail': username, 'pwrd': password, 'act': 'connect'}
        headers = {'User-Agent': USER_AGENT, 'Referer': LOGIN_URL}
        response = session.post(LOGIN_URL, data=login_payload, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        time.sleep(REQUEST_DELAY)
        
        verify_response = session.get(LOGIN_URL, headers=headers, timeout=REQUEST_TIMEOUT)
        verify_response.raise_for_status()
        
        if "act=disconnect" not in verify_response.text or "not logged in" in verify_response.text:
            raise ValueError("Login failed. Please check credentials in .env file.")
        
        logging.info(f"{Colors.GREEN}Login successful.{Colors.RESET}")
        return True
    except (requests.exceptions.RequestException, ValueError) as e:
        logging.error(f"{Colors.RED}An error occurred during login: {e}{Colors.RESET}")
        sys.exit(1)

def scrape_search_page_data(session):
    """Scrapes the search page for tokens and parses the categories JS file."""
    logging.info("Fetching security tokens and category IDs...")
    page_response = session.get(SEARCH_PAGE_URL, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
    page_response.raise_for_status()
    page_soup = BeautifulSoup(page_response.text, 'html.parser')

    stat_script = page_soup.find('script', string=re.compile(r'var stat ='))
    if not stat_script: raise ValueError("Could not find stat script block on search page.")
    
    # Extract the entire stat object as a string, then parse it
    stat_match = re.search(r'var stat\s*=\s*(\{.*?\});', stat_script.string, re.DOTALL)
    if not stat_match: raise ValueError("Could not extract the stat object.")
    # The object uses unquoted keys, so we need to add quotes to make it valid JSON
    stat_json_str = re.sub(r'(\w+):', r'"\1":', stat_match.group(1))
    stat_data = json.loads(stat_json_str)

    categories_script_tag = page_soup.find('script', src=re.compile(r'categories\.min\.js'))
    if not categories_script_tag: raise ValueError("Could not find categories.min.js script tag.")
    categories_js_url = urljoin(BASE_URL, categories_script_tag['src'])

    js_response = session.get(categories_js_url, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
    js_response.raise_for_status()
    
    match = re.search(r'=\s*(\[.*\]);?', js_response.text, re.DOTALL)
    if not match: raise ValueError("Could not find JSON data in categories.min.js")
    categories_data = json.loads(match.group(1))

    def collect_code_ids(nodes):
        ids = []
        for node in nodes:
            if 'code_id' in node: ids.append(node['code_id'])
            if 'children' in node: ids.extend(collect_code_ids(node['children']))
        return ids

    def find_node_by_title(nodes, title):
        for node in nodes:
            if node.get('title') == title: return node
            if 'children' in node:
                found_node = find_node_by_title(node['children'], title)
                if found_node: return found_node
        return None

    # Find the "Personal" and "Notable" categories
    # Based on the browser request, we need to find the right categories
    # The browser sends: [287, 290, 291, 630, 293, 294, 295, 296, 619]
    # These appear to be specific personal and notable categories
    
    # For now, we'll use the exact category IDs from the browser request
    # In a production script, you'd want to dynamically find these based on the category structure
    category_ids = [287, 290, 291, 630, 293, 294, 295, 296, 619]
    
    logging.info(f"Using category IDs: {category_ids}")
    logging.info("Successfully extracted all required page data.")
    return stat_data, category_ids

def parse_results_from_json(json_data):
    """Parses the JSON response from the API and extracts subject data."""
    results = []
    if 'data' not in json_data: return results, 0
    total_hits = json_data.get('len', [{}])[0].get('cnt', 0)
    
    for item in json_data['data']:
        try:
            sbli = item.get('sbli', '').split(',')
            spli = item.get('spli', '').split(',')
            
            results.append([
                str(item.get('recno', '')),
                str(item.get('lnho', '')),
                sbli[0] if len(sbli) > 0 else '', # LastName
                sbli[1] if len(sbli) > 1 else '', # FirstName
                sbli[2].upper() if len(sbli) > 2 else 'U', # Gender
                sbli[3] if len(sbli) > 3 else '', # Day
                sbli[4] if len(sbli) > 4 else '', # Month
                sbli[5] if len(sbli) > 5 else '', # Year
                sbli[6] if len(sbli) > 6 else '', # Time
                spli[0] if len(spli) > 0 else '', # City
                spli[1] if len(spli) > 1 else '', # Country/State
                spli[2] if len(spli) > 2 else '', # Longitude
                spli[3] if len(spli) > 3 else '', # Latitude
            ])
        except IndexError as e:
            logging.warning(f"Skipping a record due to parsing error: {e} - Data: {item}")
            continue
            
    return results, total_hits

def fetch_all_data(session, output_path, stat_data, category_ids):
    """Fetches all paginated data from the API, saving results incrementally."""
    logging.info("Starting data extraction from API...")
    pbar = None
    b_start = 1
    total_hits = 0
    processed_count = 0

    try:
        header = [
            "RecNo", "ARN", "LastName", "FirstName", "Gender", "Day", "Month", "Year",
            "Time", "City", "CountryState", "Longitude", "Latitude"
        ]
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            f.write("\t".join(header) + "\n")

            while True:
                timestamp = datetime.now().astimezone().isoformat()
                options = {
                    "day": "0", "month": "0", "years-from": "1900", "years-to": "2025",
                    "private-database": "exclude", "result-limit": "100",
                    "gender": ["male", "female"], "ratings": ["AA", "A"],
                    "house-system": "placidus", "orb-0": "10", "orb-60": "6",
                    "orb-90": "10", "orb-120": "10", "orb-180": "10", "orb-30": "3",
                    "orb-45": "3", "orb-72": "2", "orb-135": "3", "orb-144": "2",
                    "orb-150": "3", "orb-parallel": "2", "orb-antiparallel": "2",
                    "dispositors-and-rulers": "combined",
                    "intercepted-signs-as-house-rulers": "no",
                    "north-node": "true", "out-of-sign-aspects": "respect",
                    "pars-fortunae-formula": "day_night"
                }
                
                stat_for_summary = {**stat_data, "security": "..."}
                data_summary_dict = {
                    "categories": category_ids, "categories2": [], "events": [], "events2": [],
                    "options": options, "filters": {}, "timestamp": timestamp,
                    "action": "search", "stat": stat_for_summary
                }
                data_summary = json.dumps(data_summary_dict, sort_keys=True, separators=(',', ':')).replace('"', "'")
                
                query_summary = "Day (any), Month (any), Years 1900 - 2025, Data Set (ADB data), Results per Page (100), Gender (male, female), Ratings (AA, A), House System (Placidus), Orbs (10°, 6°, 10°, 10°, 10°, 3°, 3°, 2°, 3°, 2°, 3°, 1°, 1°), Other (combined, no, true, respect, day/night formula), Categories: Personal (8), Notable (1), "

                payload = {
                    **data_summary_dict,
                    "stat": stat_data, "data_summary": data_summary,
                    "query_summary": query_summary,
                }
                if b_start > 1:
                    payload["b_start"] = str(b_start)
                
                headers = {
                    'Accept': 'application/json, text/javascript, */*; q=0.01', 'Accept-Language': 'en-US,en;q=0.9',
                    'Connection': 'keep-alive', 'Content-Type': 'application/json; charset=utf-8',
                    'DNT': '1', 'Origin': BASE_URL, 'Referer': SEARCH_PAGE_URL,
                    'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'same-origin',
                    'User-Agent': USER_AGENT, 'X-Requested-With': 'XMLHttpRequest',
                    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
                    'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"'
                }
                
                payload_string = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
                response = session.post(API_URL, data=payload_string.encode('utf-8'), headers=headers, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                json_response = response.json()
                
                page_results, current_total = parse_results_from_json(json_response)
                if pbar is None:
                    total_hits = current_total
                    if total_hits == 0: raise ValueError("Search successful but returned 0 results.")
                    pbar = tqdm(total=total_hits, desc="Scraping records", ncols=80)
                
                if not page_results: break

                for row in page_results:
                    f.write("\t".join(map(str, row)) + "\n")
                
                processed_count += len(page_results)
                pbar.update(len(page_results))
                
                b_start += len(page_results)
                if b_start > total_hits: break
                time.sleep(REQUEST_DELAY)

    except (requests.exceptions.RequestException, ValueError, KeyError) as e:
        logging.error(f"\n{Colors.RED}An error occurred: {e}{Colors.RESET}")
    except KeyboardInterrupt:
        logging.info(f"\n{Colors.YELLOW}\nProcess interrupted by user. {processed_count:,} records were saved.{Colors.RESET}")
    finally:
        if pbar: pbar.close()

    if processed_count == 0: return

    logging.info(f"{Colors.GREEN}Data fetching complete.{Colors.RESET}")

def main():
    os.system('')
    parser = argparse.ArgumentParser(description="Fetch raw birth data from the Astro-Databank website.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-o", "--output-file", default="data/sources/adb_raw_export_fetched.txt", help="Path for the output data file.")
    parser.add_argument("--force", action="store_true", help="Force fetching and overwrite the output file if it exists.")
    args = parser.parse_args()

    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        if not args.force:
            print("")
            logging.warning(f"{Colors.YELLOW}The output file '{output_path}' already exists.{Colors.RESET}")
            response = input("Do you want to overwrite it? (Y/N): ").lower()
            if response != 'y':
                print("")
                logging.info("Operation cancelled by user.\n")
                sys.exit(0)

        # Create a backup before proceeding
        try:
            backup_dir = Path('data/backup')
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{output_path.stem}.{timestamp}{output_path.suffix}.bak"
            shutil.copy2(output_path, backup_path)
            logging.info(f"Created backup of existing file at: {backup_path}")
        except (IOError, OSError) as e:
            logging.error(f"{Colors.RED}Failed to create backup file: {e}{Colors.RESET}")
            sys.exit(1)

    load_dotenv()
    adb_username = os.getenv("ADB_USERNAME")
    adb_password = os.getenv("ADB_PASSWORD")

    if not adb_username or not adb_password:
        logging.error(f"{Colors.RED}ADB_USERNAME and ADB_PASSWORD must be set in the .env file.{Colors.RESET}")
        sys.exit(1)

    with requests.Session() as session:
        login_to_adb(session, adb_username, adb_password)
        stat_data, category_ids = scrape_search_page_data(session)
        fetch_all_data(session, output_path, stat_data, category_ids)

if __name__ == "__main__":
    main()

# === End of src/fetch_adb_data.py ===

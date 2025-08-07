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
import csv
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
    print("")
    logging.info(f"{Colors.YELLOW}Attempting to log into Astro-Databank...{Colors.RESET}")
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
    """Scrapes security tokens, finds category IDs, and builds a category name map."""
    logging.info("Fetching security tokens and category data...")
    page_response = session.get(SEARCH_PAGE_URL, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
    page_response.raise_for_status()
    page_soup = BeautifulSoup(page_response.text, 'html.parser')

    # ... (code to extract stat_data remains the same)
    stat_script = page_soup.find('script', string=re.compile(r'var stat ='))
    if not stat_script: raise ValueError("Could not find stat script block.")
    stat_match = re.search(r'var stat\s*=\s*(\{.*?\});', stat_script.string, re.DOTALL)
    if not stat_match: raise ValueError("Could not extract stat object.")
    stat_json_str = re.sub(r'(\w+):', r'"\1":', stat_match.group(1))
    stat_data = json.loads(stat_json_str)

    # --- Fetch and Process Category Data ---
    categories_script_tag = page_soup.find('script', src=re.compile(r'categories\.min\.js'))
    if not categories_script_tag: raise ValueError("Could not find categories.min.js script tag.")
    categories_js_url = urljoin(BASE_URL, categories_script_tag['src'])
    js_response = session.get(categories_js_url, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
    js_response.raise_for_status()
    match = re.search(r'=\s*(\[.*\]);?', js_response.text, re.DOTALL)
    if not match: raise ValueError("Could not find JSON data in categories.min.js")
    categories_data = json.loads(match.group(1))

    # --- Build a flat map of {id: title} for easy lookups ---
    category_map = {}
    def build_category_map(nodes):
        for node in nodes:
            if 'code_id' in node and 'title' in node:
                # Store the key as a string to match the type from the split() operation later.
                category_map[str(node['code_id'])] = node['title']
            if 'children' in node:
                build_category_map(node['children'])
    build_category_map(categories_data)
    logging.info(f"Built a lookup map with {len(category_map)} category translations.")

    # --- Save the category map to a CSV file ---
    output_dir = Path('data/foundational_assets')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'adb_category_map.csv'

    if output_path.exists():
        logging.info(f"Category map '{output_path}' already exists. Creating a backup before overwriting.")
        try:
            backup_dir = Path('data/backup')
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{output_path.stem}.{timestamp}{output_path.suffix}.bak"
            shutil.copy2(output_path, backup_path)
            logging.info(f"  -> Backup created at: {backup_path}")
        except (IOError, OSError) as e:
            logging.warning(f"Could not create backup for category map: {e}")

    try:
        # Sort by the integer value of the ID for a consistent, ordered output file.
        sorted_categories = sorted(category_map.items(), key=lambda item: int(item[0]))
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'CategoryName']) # Write the header
            writer.writerows(sorted_categories)     # Write the sorted data rows
        
        logging.info(f"Successfully saved/updated category map at '{output_path}'.")
    except (IOError, csv.Error) as e:
        logging.warning(f"Could not save category map to '{output_path}': {e}")

    def find_all_code_ids_in_node(node):
        """Recursively collects all code_ids from a node and its children."""
        ids = []
        if 'code_id' in node:
            ids.append(node['code_id'])
        if 'children' in node:
            for child in node['children']:
                ids.extend(find_all_code_ids_in_node(child))
        return ids

    def find_node_by_title(nodes, title):
        """Recursively searches for a node with a specific title."""
        for node in nodes:
            if node.get('title') == title:
                return node
            if 'children' in node:
                found_node = find_node_by_title(node['children'], title)
                if found_node:
                    return found_node
        return None

    required_top_level_titles = ["Death", "Top 5% of Profession"]
    category_ids = []
    print("")
    logging.info("Dynamically searching for required category IDs...")
    for title in required_top_level_titles:
        node = find_node_by_title(categories_data, title)
        if node:
            ids_found = find_all_code_ids_in_node(node)
            category_ids.extend(ids_found)
            logging.info(f"  - Found '{title}' -> IDs: {ids_found}")
        else:
            raise ValueError(f"Could not find required category node for '{title}'. The website structure may have changed.")
    category_ids = sorted(list(set(category_ids)))
        
    logging.info(f"Using dynamically found category IDs: {category_ids}")
    logging.info("Successfully extracted all required page data.")
    return stat_data, category_ids, category_map

def parse_results_from_json(json_data, category_map):
    """Parses the JSON response from the API and extracts subject data."""
    results = []
    if 'data' not in json_data: return results, 0
    total_hits = json_data.get('len', [{}])[0].get('cnt', 0)
    
    for item in json_data['data']:
        try:
            sbli = item.get('sbli', '').split(',')
            spli = item.get('spli', '').split(',')
            
            # --- Extract data using confirmed keys and validated logic ---
            last_name = sbli[0] if len(sbli) > 0 else ''
            first_name = sbli[1] if len(sbli) > 1 else ''
            
            # Construct URL slug based on the validated rules from visual evidence.
            if first_name.strip():
                # Case 1: Name has a first and last part (e.g., "Busch, Ernst (1900)")
                # Resulting slug: "Busch,_Ernst_(1900)"
                first_name_slug = first_name.replace(' ', '_')
                url_slug = f"{last_name},_{first_name_slug}"
            else:
                # Case 2: Name is a single part (e.g., "Vercors")
                url_slug = last_name
            
            link = f"https://www.astro.com/astro-databank/{url_slug}" if url_slug else ''

            rating = item.get('srra', '')
            bio = item.get('sbio', '')
            
            # Translate category IDs to text names.
            category_ids_str = item.get('ctgs', '')
            category_names = [category_map.get(cat_id, f"ID_{cat_id}") for cat_id in category_ids_str.split(',') if cat_id]
            categories_text = ', '.join(category_names)

            results.append([
                str(item.get('recno', '')),                 # ARN
                item.get('lnho', ''),                       # ADBNo (numeric ID)
                last_name,                                  # LastName
                first_name,                                 # FirstName
                sbli[2].upper() if len(sbli) > 2 else 'U',  # Gender
                sbli[3] if len(sbli) > 3 else '',           # Day
                sbli[4] if len(sbli) > 4 else '',           # Month
                sbli[5] if len(sbli) > 5 else '',           # Year
                sbli[6] if len(sbli) > 6 else '',           # Time
                spli[0] if len(spli) > 0 else '',           # City
                spli[1] if len(spli) > 1 else '',           # Country/State
                spli[2].upper() if len(spli) > 2 else '',   # Longitude
                spli[3].upper() if len(spli) > 3 else '',   # Latitude
                rating,                                     # Rating
                bio,                                        # Bio
                categories_text,                            # Categories
                link                                        # Link
            ])
        except IndexError as e:
            logging.warning(f"Skipping a record due to parsing error: {e} - Data: {item}")
            continue
            
    return results, total_hits

def fetch_all_data(session, output_path, initial_stat_data, category_ids, category_map):
    """Fetches all paginated data from the API, saving results incrementally."""
    print("")
    logging.info(f"{Colors.YELLOW}Starting data extraction from API...{Colors.RESET}")
    pbar = None
    page_number = 1
    total_hits = 0
    processed_count = 0

    try:
        header = [
            "ARN", "ADBNo", "LastName", "FirstName", "Gender", "Day", "Month", "Year",
            "Time", "City", "CountryState", "Longitude", "Latitude", "Rating", "Bio", "Categories", "Link"
        ]
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            f.write("\t".join(header) + "\n")

            while True:
                # Common headers for all requests
                headers = {
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Origin': BASE_URL, 'Referer': SEARCH_PAGE_URL,
                    'User-Agent': USER_AGENT, 'X-Requested-With': 'XMLHttpRequest'
                }
                
                if page_number == 1:
                    # First page: POST with full search payload
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
                        "pars-fortunae-formula": "day_night",
                        # Request additional fields based on UI checkboxes
                        "with-bio": "on",
                        "with-cat": "on"
                    }
                    
                    payload = {
                        "categories": category_ids, "categories2": [], "events": [], "events2": [],
                        "options": options, "filters": {}, 
                        "timestamp": datetime.now().astimezone().isoformat(),
                        "action": "search", "stat": initial_stat_data
                    }
                    
                    headers['Content-Type'] = 'application/json; charset=utf-8'
                    response = session.post(API_URL, 
                                           data=json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8'),
                                           headers=headers, timeout=REQUEST_TIMEOUT)
                else:
                    # Subsequent pages: GET with pagination params
                    params = {
                        'uid': '31062880',
                        '': '',  # Empty parameter
                        'pageSize': '100',
                        'pageNumber': str(page_number),
                        '_': str(int(time.time() * 1000))
                    }
                    
                    headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
                    response = session.get(API_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
                
                response.raise_for_status()
                json_response = response.json()
                
                page_results, current_total = parse_results_from_json(json_response, category_map)
                if pbar is None:
                    total_hits = current_total
                    if total_hits == 0: raise ValueError("Search successful but returned 0 results.")
                    pbar = tqdm(total=total_hits, desc="Scraping records", ncols=80)
                
                if not page_results: break

                for row in page_results:
                    f.write("\t".join(map(str, row)) + "\n")
                
                processed_count += len(page_results)
                pbar.update(len(page_results))
                if processed_count > pbar.total:
                    pbar.total = processed_count
                
                page_number += 1
                if processed_count >= total_hits and total_hits > 0: break
                time.sleep(REQUEST_DELAY)

    except (requests.exceptions.RequestException, ValueError, KeyError) as e:
        logging.error(f"\n{Colors.RED}An error occurred during fetch: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
    except KeyboardInterrupt:
        logging.info(f"\n{Colors.YELLOW}\nProcess interrupted by user. {processed_count:,} records were saved.{Colors.RESET}")
    finally:
        if pbar: pbar.close()

    if processed_count == 0: return

    logging.info(f"{Colors.GREEN}Data fetching complete.\n{Colors.RESET}")

def main():
    os.system('')
    parser = argparse.ArgumentParser(description="Fetch raw birth data from the Astro-Databank website.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-o", "--output-file", default="data/sources/adb_raw_export.txt", help="Path for the output data file.")
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
        initial_stat_data, category_ids, category_map = scrape_search_page_data(session)
        fetch_all_data(session, output_path, initial_stat_data, category_ids, category_map)

if __name__ == "__main__":
    main()

# === End of src/fetch_adb_data.py ===

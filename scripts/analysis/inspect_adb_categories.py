#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
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
# Filename: scripts/analysis/inspect_adb_categories.py

"""
A diagnostic tool to inspect the structure of Astro-Databank's search categories.

This script logs into astro.com, downloads the 'categories.min.js' file that
defines the search filters, and saves the parsed data as a human-readable JSON
file. This allows developers to inspect the exact titles and code_ids used by
the website, which is necessary for building a robust dynamic category lookup.
"""

import json
import logging
import os
import re
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- ANSI Color Codes ---
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'

# --- Constants ---
BASE_URL = "https://www.astro.com"
LOGIN_URL = f"{BASE_URL}/cgi/awd.cgi"
SEARCH_PAGE_URL = f"{BASE_URL}/adb-search/index.cgi"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"

def main():
    """Main function to run the inspector."""
    # Load credentials
    load_dotenv()
    adb_username = os.getenv("ADB_USERNAME")
    adb_password = os.getenv("ADB_PASSWORD")
    if not adb_username or not adb_password:
        logging.error(f"{Colors.RED}ADB_USERNAME and ADB_PASSWORD must be set in the .env file.")
        return 1

    with requests.Session() as session:
        # Step 1: Login
        logging.info("Logging into Astro-Databank...")
        session.post(LOGIN_URL, data={'mail': adb_username, 'pwrd': adb_password, 'act': 'connect'}, headers={'User-Agent': USER_AGENT})
        
        # Step 2: Get the search page to find the script URL
        logging.info(f"Fetching search page: {SEARCH_PAGE_URL}")
        page_response = session.get(SEARCH_PAGE_URL, headers={'User-Agent': USER_AGENT})
        page_response.raise_for_status()
        page_soup = BeautifulSoup(page_response.text, 'html.parser')

        # Step 3: Find and download categories.min.js
        categories_script_tag = page_soup.find('script', src=re.compile(r'categories\.min\.js'))
        if not categories_script_tag:
            logging.error(f"{Colors.RED}Could not find categories.min.js script tag on the search page.")
            return 1
        
        categories_js_url = urljoin(BASE_URL, categories_script_tag['src'])
        logging.info(f"Downloading category data from: {categories_js_url}")
        js_response = session.get(categories_js_url, headers={'User-Agent': USER_AGENT})
        js_response.raise_for_status()

        # Step 4: Parse the JavaScript to extract the JSON data
        match = re.search(r'=\s*(\[.*\]);?', js_response.text, re.DOTALL)
        if not match:
            logging.error(f"{Colors.RED}Could not find JSON data in categories.min.js")
            return 1
        
        categories_data = json.loads(match.group(1))

        # Step 5: Save the data to a file for inspection
        output_path = "debug/adb_categories_structure.json"
        logging.info(f"Saving category structure to: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(categories_data, f, indent=2, ensure_ascii=False)

        logging.info(f"\n{Colors.GREEN}Diagnostic complete. Please open '{output_path}' and search for the correct titles for your search filters (e.g., 'Death').")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

# === End of scripts/analysis/inspect_adb_categories.py ===

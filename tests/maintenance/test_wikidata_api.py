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
# Filename: tests/maintenance/test_wikidata_api.py

"""
A small, targeted integration test to verify the Wikidata API connection.
This script directly calls the relevant functions from qualify_subjects.py
to ensure that the User-Agent header fix allows for successful API calls.
"""

import sys
from pathlib import Path

# Add the 'src' directory to the Python path to allow importing the script
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'src'))

# Import the specific functions and the session object we need to test
from qualify_subjects import (
    SESSION,
    fetch_page_content,
    get_wikidata_qid,
    is_deceased_via_wikidata
)

# --- Test Cases ---
# We use subjects with stable, well-known Wikipedia/Wikidata entries.
TEST_SUBJECTS = [
    {
        "name": "Albert Einstein",
        "url": "https://en.wikipedia.org/wiki/Albert_Einstein",
        "expected_deceased": True
    },
    {
        "name": "Tim Berners-Lee",
        "url": "https://en.wikipedia.org/wiki/Tim_Berners-Lee",
        "expected_deceased": False
    },
    {
        "name": "Marie Curie",
        "url": "https://en.wikipedia.org/wiki/Marie_Curie",
        "expected_deceased": True
    }
]

def run_test(subject):
    """Runs the validation logic for a single test subject."""
    print(f"--- Testing: {subject['name']} (Expected Deceased: {subject['expected_deceased']}) ---")
    
    # 1. Fetch the Wikipedia page content
    print(f"1. Fetching Wikipedia page: {subject['url']}")
    soup = fetch_page_content(subject['url'])
    if not soup:
        print("   [FAIL] Could not fetch Wikipedia page.")
        return False
    print("   [SUCCESS] Page fetched.")

    # 2. Extract the Wikidata QID
    print("2. Extracting Wikidata QID...")
    qid = get_wikidata_qid(soup)
    if not qid:
        print("   [FAIL] Could not find Wikidata QID on the page.")
        return False
    print(f"   [SUCCESS] Found QID: {qid}")

    # 3. Query Wikidata and check life status
    print(f"3. Querying Wikidata for death date (P570) for {qid}...")
    is_deceased = is_deceased_via_wikidata(qid)
    
    if is_deceased is None:
        print("   [FAIL] Wikidata query failed. The API might have blocked the request.")
        return False

    print(f"   [SUCCESS] Wikidata API returned: is_deceased = {is_deceased}")

    # 4. Final verification
    if is_deceased == subject['expected_deceased']:
        print(f"\n✅ PASSED: {subject['name']} correctly identified.\n")
        return True
    else:
        print(f"\n❌ FAILED: {subject['name']} was incorrectly identified.")
        print(f"   Expected: {subject['expected_deceased']}, Got: {is_deceased}\n")
        return False

def main():
    print("Starting Wikidata API Integration Test...")
    print(f"Using User-Agent: {SESSION.headers.get('User-Agent')}\n")
    
    all_passed = True
    for subject in TEST_SUBJECTS:
        if not run_test(subject):
            all_passed = False
    
    if all_passed:
        print("="*40)
        print("✅ ALL TESTS PASSED SUCCESSFULLY.")
        print("="*40)
        sys.exit(0)
    else:
        print("="*40)
        print("❌ SOME TESTS FAILED.")
        print("="*40)
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of tests/maintenance/test_wikidata_api.py ===

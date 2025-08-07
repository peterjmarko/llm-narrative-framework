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
automated checks with enhanced robustness based on proven VBA macro patterns:

1.  **Scrapes the ADB Page:** Visits the subject's Astro-Databank page to
    find the link to their Wikipedia article using multiple strategies:
    - Prioritizes "Link to Wikipedia" text anchors (most reliable)
    - Falls back to general Wikipedia link detection
    - Intelligently handles non-English links by finding English equivalents

2.  **Validates Wikipedia Page:**
    - Follows all redirects including HTTP 3xx and meta-refresh tags
    - Extracts and prioritizes canonical URLs from Wikipedia pages
    - Detects disambiguation pages using multiple pattern matches
    - Resolves disambiguation using flexible birth year matching patterns
    - Handles nested redirects up to a configurable depth limit

3.  **Compares Names:** Performs a fuzzy string comparison between the name
    from ADB and the Wikipedia article title to detect typos or mismatches,
    with intelligent handling of name formatting variations.

4.  **Verifies Death Date:** Uses multiple strategies to detect death dates:
    - Primary: Checks for "Died" field in Wikipedia infobox
    - Fallback: Searches opening paragraphs for date ranges
    - Pattern matching for various death date formats (d., †, died, etc.)

The script produces a detailed CSV report (`adb_validation_report.csv`) that
flags any entries with missing links, name mismatches, or missing death dates,
facilitating manual review and correction of the source data. The validation
process is resumable and supports parallel processing for efficiency.
"""

import argparse
import csv
import logging
import re
import os
import sys
import time
import shutil
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from thefuzz import fuzz
from tqdm import tqdm
from urllib3.util.retry import Retry
import json
from typing import Dict, List, Set

# --- Rate Limiting for ADB Requests ---
import time
from threading import Lock

ADB_REQUEST_LOCK = Lock()
ADB_LAST_REQUEST_TIME = 0
ADB_MIN_DELAY = 0.2  # Minimum 200ms between ADB requests

# --- Research Category Management ---
RESEARCH_CATEGORIES_FILE = Path("data/config/adb_research_categories.json")
RESEARCH_CATEGORIES_CACHE = None

def load_research_categories() -> Dict:
    """
    Loads research categories from the configuration file.
    Creates the file with defaults if it doesn't exist.
    
    Returns:
        Dictionary containing research category patterns
    """
    global RESEARCH_CATEGORIES_CACHE
    
    if RESEARCH_CATEGORIES_CACHE is not None:
        return RESEARCH_CATEGORIES_CACHE
    
    if not RESEARCH_CATEGORIES_FILE.exists():
        # Create default file
        RESEARCH_CATEGORIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        default_categories = {
            "description": "Research categories in Astro-Databank that require 'Research:' URL prefix",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "categories": {
                "prefixes": [
                    "Accident:", "Birth Defect:", "Crime:", "Death:", "Disaster:",
                    "Disease:", "Event:", "Fire:", "Homicide:", "Medical:",
                    "Murder:", "School:", "Suicide:", "Twin:", "UFO:", "Victim:",
                    "Earthquake:", "Explosion:", "Flood:", "Hurricane:", "Tornado:",
                    "Volcano:", "War:", "Attack:", "Shooting:", "Bombing:",
                    "Crash:", "Shipwreck:", "Plane Crash:", "Train Wreck:"
                ],
                "patterns": [
                    "^\\d{4} .+",  # Year followed by text (events)
                    "^Case \\d+",   # Case numbers
                    "^Unknown .+",  # Unknown entities
                    "^Baby [A-Z]",  # Anonymous babies
                    "^Child [A-Z]", # Anonymous children
                    "^Infant [A-Z]" # Anonymous infants
                ],
                "exact_matches": [
                    "Unknown", "Anonymous", "Unidentified"
                ]
            },
            "auto_detected": {
                "description": "Patterns automatically detected from failed URLs",
                "entries": []
            }
        }
        
        with open(RESEARCH_CATEGORIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_categories, f, indent=2)
        
        logging.info(f"Created research categories file: {RESEARCH_CATEGORIES_FILE}")
        RESEARCH_CATEGORIES_CACHE = default_categories
    else:
        # Load existing file
        try:
            with open(RESEARCH_CATEGORIES_FILE, 'r', encoding='utf-8') as f:
                RESEARCH_CATEGORIES_CACHE = json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f"Error loading research categories: {e}")
            # Return minimal defaults on error
            RESEARCH_CATEGORIES_CACHE = {"categories": {"prefixes": [], "patterns": [], "exact_matches": []}}
    
    return RESEARCH_CATEGORIES_CACHE

def is_research_entry(name: str, first_name: str = "") -> bool:
    """
    Determines if an entry is a Research entry based on known category patterns.
    
    Handles both explicit categories (like "Accident:") and implicit ones
    (like "Homosexual 1234" or "AIDS 456").
    
    Args:
        name: The full name or last name from ADB
        first_name: The first name field (may be empty)
        
    Returns:
        True if this matches a known Research entry pattern
    """
    # Get the full name for checking
    full_name = name if ',' in name else f"{name} {first_name}".strip()
    
    # First check if it's definitely a person (blacklist)
    if is_definitely_person(full_name):
        return False
    
    categories = load_research_categories()
    
    # Check exact matches
    if full_name in categories["categories"].get("exact_matches", []):
        return True
    
    # Check if it starts with a known Research category prefix
    for prefix in categories["categories"].get("prefixes", []):
        if full_name.lower().startswith(prefix.lower()):
            return True
    
    # Check regex patterns
    for pattern in categories["categories"].get("patterns", []):
        try:
            if re.match(pattern, full_name, re.I):
                return True
        except re.error:
            logging.warning(f"Invalid regex pattern in config: {pattern}")
    
    # Additional heuristic: If it contains a number at the end (like "Homosexual 3943")
    # and doesn't have a comma (not a proper name), it's likely a Research entry
    if not ',' in full_name and re.search(r'\s+\d{3,}(\s+[A-Z\.]+)?$', full_name):
        debug_log(f"Detected likely Research entry by number pattern: {full_name}")
        return True
    
    # Check for category-like patterns (word followed by colon)
    if ':' in full_name and not ',' in full_name:
        # Get the part before the colon
        category_part = full_name.split(':', 1)[0]
        # If it's a single word or two words, likely a category
        if len(category_part.split()) <= 2:
            debug_log(f"Detected likely Research entry by colon pattern: {full_name}")
            return True
    
    return False

def build_adb_url_variants(base_url: str, path: str, name: str) -> list[str]:
    """
    Builds multiple URL variants to try for an ADB entry.
    
    Args:
        base_url: The base ADB URL (https://www.astro.com/astro-databank/)
        path: The path component after /astro-databank/
        name: The name of the entry
        
    Returns:
        List of URL variants to try in order
    """
    variants = []
    
    # Original URL
    original = f"{base_url}/{path}"
    variants.append(original)
    
    # Check if this might be a Research entry
    if is_research_entry(name, ""):
        # Try with Research: prefix
        if not path.startswith('Research:'):
            research_url = f"{base_url}/Research:{path}"
            variants.append(research_url)
    
    # For entries with spaces and numbers, try URL encoding variations
    if ' ' in path:
        # Try with underscores instead of %20
        underscore_path = path.replace(' ', '_')
        variants.append(f"{base_url}/{underscore_path}")
        
        if is_research_entry(name, ""):
            variants.append(f"{base_url}/Research:{underscore_path}")
    
    return variants

def is_definitely_person(name: str) -> bool:
    """
    Checks if a name is definitely a person (not a Research entry).
    
    Args:
        name: The name to check
        
    Returns:
        True if this is definitely a person's name
    """
    categories = load_research_categories()
    
    # Check the blacklist of known person names
    not_research = categories.get("definitely_not_research", {}).get("names", [])
    
    # Check against full name and common variations
    name_variations = [
        name,
        name.replace(',', '').strip(),
        name.replace('_', ' '),
    ]
    
    for variant in name_variations:
        if variant in not_research:
            return True
    
    return False

def add_detected_research_pattern(url: str, name: str) -> None:
    """
    Adds a newly detected research pattern to the auto-detected list.
    This helps identify new patterns for manual review.
    
    Args:
        url: The URL that failed without Research: prefix
        name: The name of the entry
    """
    categories = load_research_categories()
    
    # Extract the entry type if possible (e.g., "Accident:" from "Accident: Car Crash")
    potential_prefix = None
    if ':' in name:
        potential_prefix = name.split(':', 1)[0] + ':'
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "name": name,
        "url": url,
        "potential_prefix": potential_prefix
    }
    
    # Check if this pattern is already in auto_detected
    auto_detected = categories.get("auto_detected", {}).get("entries", [])
    
    # Avoid duplicates (check by name)
    if not any(e.get("name") == name for e in auto_detected):
        auto_detected.append(entry)
        
        # Keep only the last 100 auto-detected entries
        if len(auto_detected) > 100:
            auto_detected = auto_detected[-100:]
        
        # Update the cache and file
        categories["auto_detected"]["entries"] = auto_detected
        
        try:
            with open(RESEARCH_CATEGORIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(categories, f, indent=2)
            
            logging.info(f"Added new potential research pattern: {name}")
        except IOError as e:
            logging.warning(f"Could not update research categories file: {e}")

def print_research_categories_summary():
    """Prints a summary of loaded research categories."""
    categories = load_research_categories()
    
    print(f"\n{Colors.YELLOW}Research Categories Loaded:{Colors.RESET}")
    print(f"  - Prefixes: {len(categories['categories'].get('prefixes', []))}")
    print(f"  - Patterns: {len(categories['categories'].get('patterns', []))}")
    print(f"  - Exact matches: {len(categories['categories'].get('exact_matches', []))}")
    
    auto_detected = categories.get('auto_detected', {}).get('entries', [])
    if auto_detected:
        print(f"  - Auto-detected entries: {len(auto_detected)}")
        
        # Show recent potential prefixes
        recent_prefixes = set()
        for entry in auto_detected[-10:]:
            if entry.get('potential_prefix'):
                recent_prefixes.add(entry['potential_prefix'])
        
        if recent_prefixes:
            print(f"  - Recent potential prefixes to review: {', '.join(recent_prefixes)}")

def search_wikipedia(name: str, birth_year: str = None) -> list[tuple[str, str]]:
    """
    Searches Wikipedia for a person by name using the Wikipedia API.
    
    Args:
        name: The person's name to search for
        birth_year: Optional birth year to help identify the right person
        
    Returns:
        List of tuples (page_title, page_url) for potential matches
    """
    try:
        # Clean up the name for searching
        search_name = name
        if ',' in search_name:
            # Convert "Last, First" to "First Last"
            parts = search_name.split(',', 1)
            search_name = f"{parts[1].strip()} {parts[0].strip()}"
        
        # Remove any year in parentheses
        search_name = re.sub(r'\s*\(\d{4}\)$', '', search_name).strip()
        
        # Wikipedia API search endpoint
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            'action': 'opensearch',
            'search': search_name,
            'limit': 5,  # Reduced from 10 to speed up
            'namespace': 0,
            'format': 'json'
        }
        
        response = SESSION.get(search_url, params=params, timeout=3)  # Short timeout
        response.raise_for_status()
        
        data = response.json()
        # data[1] contains titles, data[3] contains URLs
        if len(data) >= 4 and data[1] and data[3]:
            results = list(zip(data[1], data[3]))
            return results[:3]  # Only return top 3 results
        
        return []
        
    except requests.exceptions.Timeout:
        debug_log(f"Wikipedia search timeout for '{name}'")
        return []
    except Exception as e:
        debug_log(f"Wikipedia search failed for '{name}': {e}")
        return []


def find_best_wikipedia_match(name: str, birth_year: str, search_results: list[tuple[str, str]], pbar: tqdm) -> str | None:
    """
    Finds the best Wikipedia match from search results by checking page content.
    
    Args:
        name: Original name from ADB
        birth_year: Birth year to verify
        search_results: List of (title, url) tuples from search
        pbar: Progress bar for status updates
        
    Returns:
        URL of the best matching Wikipedia page, or None if no good match
    """
    if not search_results:
        return None
    
    # Clean up the name for comparison
    base_name = name
    if ',' in base_name:
        parts = base_name.split(',', 1)
        base_name = f"{parts[1].strip()} {parts[0].strip()}"
    base_name = re.sub(r'\s*\(\d{4}\)$', '', base_name).strip()
    
    # Only check first 2 results to avoid hanging
    for i, (title, url) in enumerate(search_results[:2]):
        try:
            # Quick name similarity check first
            title_clean = re.sub(r'\s*\(.*?\)$', '', title).strip()
            name_score = fuzz.ratio(base_name.lower(), title_clean.lower())
            
            # If name is very different, skip this result
            if name_score < 60:
                continue
            
            # Use a dedicated short timeout for checking pages
            headers = {'User-Agent': USER_AGENT}
            response = SESSION.get(url, headers=headers, timeout=3, allow_redirects=True)
            response.raise_for_status()
            
            # Quick check in page text for birth year (don't parse full page)
            page_text = response.text[:10000]  # Only check first 10KB
            
            # Look for birth year patterns
            if birth_year in page_text:
                # Do a more careful check with BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check if this is a disambiguation page
                if is_disambiguation_page(soup):
                    # Try to find the right link on the disambiguation page
                    matching_url = find_matching_disambiguation_link(soup, birth_year)
                    if matching_url:
                        pbar.write(f"INFO: Found match via disambiguation page: {matching_url}")
                        return matching_url
                    continue
                
                pbar.write(f"INFO: Found Wikipedia match via search: {url}")
                return url
                
        except requests.exceptions.Timeout:
            debug_log(f"Timeout checking Wikipedia page: {url}")
            continue
        except Exception as e:
            debug_log(f"Error checking Wikipedia result: {e}")
            continue
    
    return None


def get_wikipedia_url_with_fallback(adb_url: str, name: str, birth_year: str, pbar: tqdm) -> str | None:
    """
    Gets Wikipedia URL from ADB page, or searches Wikipedia as fallback.
    
    Args:
        adb_url: The ADB page URL
        name: Person's name
        birth_year: Person's birth year
        pbar: Progress bar for status updates
        
    Returns:
        Wikipedia URL if found via ADB or search, None otherwise
    """
    # First try to get from ADB page
    initial_url = get_initial_wiki_url_from_adb(adb_url)
    if initial_url:
        return initial_url
    
    # No link on ADB page - try searching Wikipedia
    debug_log(f"No Wikipedia link on ADB page for {name}, trying Wikipedia search...")
    pbar.write(f"INFO: No Wikipedia link found on ADB for {name}. Searching Wikipedia...")
    
    search_results = search_wikipedia(name, birth_year)
    if not search_results:
        debug_log(f"No Wikipedia search results for {name}")
        return None
    
    # Try to find the best match
    best_match = find_best_wikipedia_match(name, birth_year, search_results, pbar)
    return best_match

# --- Debug Mode ---
DEBUG_MODE = os.environ.get('DEBUG_ADB', '').lower() == 'true'

def debug_log(message: str):
    """Print debug messages when DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        tqdm.write(f"[DEBUG] {message}")

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- Global Shutdown Flag ---
shutdown_event = threading.Event()

# --- ANSI Color Codes ---
class Colors:
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    RESET = '\033[0m'

# --- Constants ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT = 15  # Seconds to wait for HTTP requests
NAME_MATCH_THRESHOLD = 90  # Fuzzy match score threshold for name validation
MAX_DISAMBIGUATION_DEPTH = 3  # Maximum recursion depth for disambiguation resolution
MAX_WORKERS = 5  # Number of parallel worker threads for concurrent processing
REQUEST_DELAY = 0.1  # Delay between requests to be a polite scraper (seconds)

# --- Create a Resilient Session with Retry Logic ---
SESSION = requests.Session()
retry_strategy = Retry(
    total=5,  # Total number of retries
    backoff_factor=1,  # Wait 1s, 2s, 4s, 8s, 16s between retries
    status_forcelist=[429, 500, 502, 503, 504],  # Retry on these server errors
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
# Reduce pool size to avoid overwhelming servers
adapter = HTTPAdapter(pool_connections=5, pool_maxsize=5, max_retries=retry_strategy)
SESSION.mount("https://", adapter)
SESSION.mount("http://", adapter)

# --- Helper Functions ---

def load_existing_records(filepath: Path) -> tuple[list, set, set]:
    """
    Reads an existing report, separating valid records from those that need retrying.
    Returns a tuple containing:
    - A list of valid record dicts.
    - A set of all ARNs that have been processed.
    - An integer count of the valid records.
    """
    if not filepath.exists():
        return [], set(), 0

    valid_records, processed_arns = [], set()
    ok_count = 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                arn = row.get('ARN')
                if not arn: continue
                
                processed_arns.add(arn)
                if row.get('Status') in ['OK', 'VALID']:
                    valid_records.append(row)
                    ok_count += 1
        return valid_records, processed_arns, ok_count
    except (IOError, csv.Error) as e:
        logging.warning(f"Could not read existing report at '{filepath}': {e}. Starting from scratch.")
        return [], set(), 0

def fetch_page_content(url: str) -> BeautifulSoup | None:
    """
    Fetches and parses a web page, handling meta-refresh redirects.
    
    Uses a resilient session with automatic retries for HTTP requests
    and additionally handles HTML meta-refresh tags.
    Implements rate limiting for ADB requests to avoid overwhelming the server.
    
    Args:
        url: The URL to fetch
        
    Returns:
        BeautifulSoup object of the final page, or None on error
    """
    # Rate limit ADB requests
    global ADB_LAST_REQUEST_TIME
    if 'astro.com' in url:
        with ADB_REQUEST_LOCK:
            time_since_last = time.time() - ADB_LAST_REQUEST_TIME
            if time_since_last < ADB_MIN_DELAY:
                time.sleep(ADB_MIN_DELAY - time_since_last)
            ADB_LAST_REQUEST_TIME = time.time()
    
    try:
        headers = {'User-Agent': USER_AGENT}
        # Use longer timeout for ADB
        timeout = 30 if 'astro.com' in url else REQUEST_TIMEOUT
        response = SESSION.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Handle meta-refresh redirects, which `requests` does not do automatically.
        meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile(r"refresh", re.I)})
        if meta_refresh and meta_refresh.get("content"):
            content = meta_refresh["content"]
            match = re.search(r'url\s*=\s*([\'"]?)(.*?)\1', content, re.I)
            if match:
                new_url = match.group(2)
                new_url = urljoin(response.url, new_url)
                logging.info(f"Following meta-refresh redirect from {url} -> {new_url}")
                time.sleep(REQUEST_DELAY)
                response = SESSION.get(new_url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                response.raise_for_status()
                return BeautifulSoup(response.text, 'html.parser')

        return soup
    except requests.exceptions.RequestException as e:
        # Use tqdm.write for thread-safe printing that doesn't mess up the progress bar.
        tqdm.write(f"WARNING: Request failed for URL {url} after multiple retries: {e}")
        return None

def fetch_adb_page_with_backoff(url: str, max_retries: int = 5) -> BeautifulSoup | None:
    """
    Fetches ADB page with exponential backoff on failures.
    
    Args:
        url: The ADB URL to fetch
        max_retries: Maximum number of retry attempts
        
    Returns:
        BeautifulSoup object of the page, or None on error
    """
    for attempt in range(max_retries):
        soup = fetch_page_content(url)
        if soup:
            return soup
        
        # Exponential backoff: 1s, 2s, 4s, 8s, 16s
        wait_time = 2 ** attempt
        debug_log(f"ADB request failed for {url}, waiting {wait_time}s before retry {attempt+1}/{max_retries}")
        time.sleep(wait_time)
    
    return None

def fetch_adb_page_with_fallback(adb_url: str) -> tuple[str, BeautifulSoup]:
    """
    Fetches an ADB page, trying Research: prefix if the initial URL fails.
    
    Returns:
        Tuple of (working_url, soup) where soup may be None on error
    """
    # Try the original URL first
    soup = fetch_page_content(adb_url)
    if soup:
        return adb_url, soup
    
    # If it failed and doesn't already have Research:, try adding it
    if '/astro-databank/' in adb_url and 'Research:' not in adb_url:
        base_url, path = adb_url.split('/astro-databank/', 1)
        research_url = f"{base_url}/astro-databank/Research:{path}"
        debug_log(f"Original URL failed, trying Research URL: {research_url}")
        
        soup = fetch_page_content(research_url)
        if soup:
            return research_url, soup
    
    return adb_url, None

def follow_all_redirects(url: str, max_redirects: int = 10) -> tuple[str, BeautifulSoup]:
    """
    Follows all types of redirects to reach the final destination page.
    
    Handles HTTP redirects (via requests library), meta-refresh tags,
    and canonical URL declarations. Implements redirect limiting to
    prevent infinite loops.
    
    Args:
        url: Starting URL to follow
        max_redirects: Maximum number of redirects to follow
        
    Returns:
        Tuple of (final_url, soup) where soup may be None on error
    """
    current_url = url
    
    for _ in range(max_redirects):
        soup = fetch_page_content(current_url)
        if not soup:
            return current_url, None
            
        # Check for canonical URL first
        canonical_link = soup.find('link', rel='canonical')
        if canonical_link and canonical_link.has_attr('href'):
            canonical_url = canonical_link['href']
            if canonical_url != current_url:
                current_url = canonical_url
                continue
                
        # Check for meta refresh (if not already handled by fetch_page_content)
        meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile(r"refresh", re.I)})
        if meta_refresh and meta_refresh.get("content"):
            content = meta_refresh["content"]
            match = re.search(r'url\s*=\s*([\'"]?)(.*?)\1', content, re.I)
            if match:
                new_url = urljoin(current_url, match.group(2))
                if new_url != current_url:
                    current_url = new_url
                    time.sleep(REQUEST_DELAY)
                    continue
        
        # No more redirects found
        return current_url, soup
    
    return current_url, soup

def get_canonical_url(soup: BeautifulSoup, fallback_url: str) -> str:
    """
    Extracts the canonical URL from a Wikipedia page.
    
    Wikipedia pages often declare their canonical URL in a link tag,
    which represents the preferred URL for the content. This handles
    cases where multiple URLs might point to the same content.
    
    Args:
        soup: BeautifulSoup object of the page
        fallback_url: URL to return if no canonical link is found
        
    Returns:
        The canonical URL if found, otherwise the fallback URL
    """
    canonical_link = soup.find('link', rel='canonical')
    if canonical_link and canonical_link.has_attr('href'):
        return canonical_link['href']
    return fallback_url

def get_initial_wiki_url_from_adb(adb_url: str) -> str | None:
    """
    Scrapes an ADB page to find Wikipedia URL with intelligent URL resolution.
    
    First attempts to fetch the page, automatically trying alternative URL formats
    if the initial request fails:
    - Adds 'Research:' prefix for detected Research entries
    - Tries underscore variants for URLs with spaces
    - Handles URL encoding issues
    
    Once a valid page is fetched, uses multiple Wikipedia link detection strategies
    in priority order:
    1. "Link to Wikipedia" text with associated anchor (most reliable)
    2. Links in External/References sections
    3. Any Wikipedia link in the main content
    4. Links in JavaScript/embedded content
    5. Links in data attributes or onclick handlers
    6. Links in biography/notes sections
    
    Also tracks successful Research entry patterns for future reference.
    
    Args:
        adb_url: The Astro-Databank page URL to scrape (may be modified internally
                 to handle Research entries and encoding issues)
        
    Returns:
        The Wikipedia URL if found, None otherwise
    """
    # Try to fetch with the original URL (with backoff for ADB)
    if 'astro.com' in adb_url:
        soup = fetch_adb_page_with_backoff(adb_url, max_retries=3)
    else:
        soup = fetch_page_content(adb_url)
    
    # If failed, try alternative URL formats
    if not soup and '/astro-databank/' in adb_url:
        base_url, path = adb_url.split('/astro-databank/', 1)
        
        # Extract name from path for analysis
        name_part = path.split('/')[-1].replace('_', ' ').replace('%20', ' ')
        name_part = unquote(name_part)  # Decode URL encoding
        
        # Build URL variants to try
        variants = []
        
        # If it might be a Research entry, try that first
        if is_research_entry(name_part, ""):
            if not path.startswith('Research:'):
                variants.append(f"{base_url}/astro-databank/Research:{path}")
        
        # Try with underscores instead of spaces
        if '%20' in path or ' ' in path:
            underscore_path = path.replace('%20', '_').replace(' ', '_')
            variants.append(f"{base_url}/astro-databank/{underscore_path}")
            if is_research_entry(name_part, ""):
                variants.append(f"{base_url}/astro-databank/Research:{underscore_path}")
        
        # Try each variant
        for variant_url in variants:
            debug_log(f"Trying URL variant: {variant_url}")
            if 'astro.com' in variant_url:
                soup = fetch_adb_page_with_backoff(variant_url, max_retries=3)
            else:
                soup = fetch_page_content(variant_url)
            if soup:
                # Track successful Research patterns
                if 'Research:' in variant_url and 'Research:' not in adb_url:
                    add_detected_research_pattern(adb_url, name_part)
                break
    
    if not soup:
        return None
    
    # [Rest of the function remains the same - all the Wikipedia link detection strategies]
    
    # Strategy 1: Look for "Link to Wikipedia" and related text patterns
    wiki_text_patterns = [
        r"Link to Wikipedia",
        r"Wikipedia",
        r"Wiki",
        r"Biography",
        r"External [Ll]ink",
    ]
    
    for pattern in wiki_text_patterns:
        link_texts = soup.find_all(string=re.compile(pattern, re.I))
        for link_text in link_texts:
            # Check parent anchor
            parent_anchor = link_text.find_parent('a', href=re.compile(r"https?://\w+\.wikipedia\.org"))
            if parent_anchor:
                return parent_anchor['href']
            
            # Check previous sibling anchor (text might be after the link)
            parent = link_text.parent
            if parent:
                prev_anchor = parent.find_previous_sibling('a', href=re.compile(r"https?://\w+\.wikipedia\.org"))
                if prev_anchor:
                    return prev_anchor['href']
                # Check next sibling anchor (text might be before the link)
                next_anchor = parent.find_next_sibling('a', href=re.compile(r"https?://\w+\.wikipedia\.org"))
                if next_anchor:
                    return next_anchor['href']
    
    # Strategy 2: Check specific sections like External Links, References, Biography
    section_headers = soup.find_all(['h1', 'h2', 'h3', 'h4'], 
                                   string=re.compile(r"External|Link|Reference|Biography|Source|Note", re.I))
    for header in section_headers:
        # Check the next few elements after the header
        next_element = header.find_next_sibling()
        for _ in range(5):  # Check up to 5 siblings
            if next_element:
                wiki_link = next_element.find('a', href=re.compile(r"https?://\w+\.wikipedia\.org"))
                if wiki_link:
                    return wiki_link['href']
                next_element = next_element.find_next_sibling()
            else:
                break
    
    # Strategy 3: Look in div or section with specific IDs/classes
    content_areas = soup.find_all(['div', 'section'], 
                                 class_=re.compile(r"content|biography|notes|external|links|references", re.I))
    for area in content_areas:
        wiki_link = area.find('a', href=re.compile(r"https?://\w+\.wikipedia\.org"))
        if wiki_link:
            return wiki_link['href']
    
    # Strategy 4: Check all links but prioritize those with Wikipedia text
    all_links = soup.find_all('a', href=re.compile(r"https?://\w+\.wikipedia\.org"))
    for link in all_links:
        # Prioritize links that have Wikipedia-related text
        link_text = link.get_text(strip=True).lower()
        if any(word in link_text for word in ['wiki', 'biography', 'article']):
            return link['href']
    
    # Strategy 5: Any Wikipedia link on the page (original fallback)
    if all_links:
        return all_links[0]['href']
    
    # Strategy 6: Check in JavaScript or embedded content
    for script in soup.find_all('script'):
        if script.string:
            # Look for Wikipedia URLs in JavaScript
            matches = re.findall(r'https?://\w+\.wikipedia\.org/wiki/[^"\'>\s]+', script.string)
            if matches:
                return matches[0]
    
    # Strategy 7: Check data attributes and onclick handlers
    elements_with_data = soup.find_all(attrs={'data-href': re.compile(r"wikipedia\.org")})
    if elements_with_data:
        return elements_with_data[0]['data-href']
    
    elements_with_onclick = soup.find_all(attrs={'onclick': re.compile(r"wikipedia\.org")})
    for element in elements_with_onclick:
        onclick = element.get('onclick', '')
        match = re.search(r'https?://\w+\.wikipedia\.org/wiki/[^"\'>\s]+', onclick)
        if match:
            return match.group(0)
    
    # Strategy 8: Check for obfuscated or encoded URLs
    all_anchors = soup.find_all('a', href=True)
    for anchor in all_anchors:
        href = anchor['href']
        # Check for URL-encoded Wikipedia links
        if 'wikipedia' in href.lower() or 'wiki' in href.lower():
            # Try to decode and extract
            try:
                from urllib.parse import unquote
                decoded = unquote(href)
                if 'wikipedia.org' in decoded:
                    match = re.search(r'https?://\w+\.wikipedia\.org/wiki/[^\s]+', decoded)
                    if match:
                        return match.group(0)
            except:
                pass
    
    return None

def get_english_wiki_url(initial_url: str) -> str | None:
    """Takes any language Wikipedia URL and finds the English equivalent."""
    if 'en.wikipedia.org' in initial_url:
        return initial_url

    soup = fetch_page_content(initial_url)
    if soup:
        en_link = soup.find('a', class_='interlanguage-link-target', lang='en')
        if en_link and en_link.has_attr('href'):
            # Unquote the URL to handle special characters correctly.
            return unquote(en_link['href'])
    return None

def is_disambiguation_page(soup: BeautifulSoup) -> bool:
    """
    Detects if a Wikipedia page is a disambiguation page.
    
    Uses multiple detection patterns including div IDs, CSS classes,
    and text content patterns. This comprehensive approach ensures
    disambiguation pages are reliably detected across different
    Wikipedia page formats.
    
    Args:
        soup: BeautifulSoup object of the Wikipedia page
        
    Returns:
        True if the page is a disambiguation page, False otherwise
    """
    patterns = [
        soup.find('div', id='disambiguation'),
        soup.find('div', id='Disambiguation'),  # Case variation
        soup.find(class_=re.compile(r'\bdisambiguation\b', re.I)),
        soup.find(string=re.compile(r"may refer to:", re.I)),
        soup.find(string=re.compile(r"This page lists articles associated with the same title", re.I)),
        soup.find(string=re.compile(r"This disambiguation page", re.I)),
    ]
    
    return any(patterns)

def find_matching_disambiguation_link(soup: BeautifulSoup, birth_year: str) -> str | None:
    """
    Finds the correct link on a disambiguation page using birth year.
    
    Searches list items on the page for various patterns containing the
    birth year, including exact matches, year with dashes, parentheses,
    and common biographical patterns like "born YYYY" or "b. YYYY".
    
    Args:
        soup: BeautifulSoup object of the disambiguation page
        birth_year: Year string to search for
        
    Returns:
        Full Wikipedia URL of the matching article, or None if not found
    """
    list_items = soup.find_all('li')
    
    # Create multiple year patterns to match (like VBA)
    year_patterns = [
        birth_year,                    # Exact year
        f"{birth_year}–",              # Year with en-dash
        f"{birth_year}-",              # Year with hyphen  
        f"({birth_year}",              # Year in parentheses
        f"{birth_year})",              # Year closing parentheses
        f" {birth_year} ",             # Year with spaces
        f"born {birth_year}",          # Common pattern
        f"b. {birth_year}",            # Abbreviated born
    ]
    
    for item in list_items:
        item_text = item.get_text()
        # Check all patterns
        for pattern in year_patterns:
            if pattern in item_text:
                link = item.find('a', href=re.compile(r"/wiki/"))
                if link and link.has_attr('href'):
                    return urljoin("https://en.wikipedia.org", link['href'])
    
    return None

def process_wikipedia_page(url: str, adb_name: str, birth_year: str, pbar: tqdm, depth=0) -> dict:
    """
    Scrapes and validates a Wikipedia page with robust disambiguation handling.
    
    Follows all redirects to reach the final page, extracts canonical URLs,
    detects disambiguation pages using multiple patterns, and resolves them
    using flexible birth year matching. Implements depth limiting to prevent
    infinite recursion in complex redirect chains.
    
    Args:
        url: Wikipedia URL to process
        adb_name: Name from Astro-Databank for comparison
        birth_year: Birth year for disambiguation resolution
        pbar: Progress bar for status updates
        depth: Current recursion depth for disambiguation handling
        
    Returns:
        Dictionary with status, final URL, name match score, and death date info
    """
    if depth >= MAX_DISAMBIGUATION_DEPTH:
        return {'status': 'ERROR', 'notes': 'Max disambiguation depth reached'}

    # Follow all redirects and get final page
    final_url, soup = follow_all_redirects(url)
    if not soup:
        return {'status': 'ERROR', 'notes': 'Failed to fetch Wikipedia page'}

    # Extract canonical URL
    final_url = get_canonical_url(soup, final_url)

    # Check for disambiguation
    if is_disambiguation_page(soup):
        pbar.write(f"INFO: Disambiguation page found for {final_url}. Searching for birth year '{birth_year}'...")
        
        matching_url = find_matching_disambiguation_link(soup, birth_year)
        if matching_url:
            pbar.write(f"INFO:   -> Found matching link: {matching_url}")
            return process_wikipedia_page(matching_url, adb_name, birth_year, pbar, depth + 1)
        
        return {'status': 'FAIL', 'notes': f"Disambiguation page, but no link with year {birth_year} found"}

    # Standard validation
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
    """
    Exhaustive death date detection using multiple strategies and locations.
    
    Checks infobox fields, opening paragraphs, categories, and various
    text patterns to determine if a person is deceased. Also checks for
    negative signals like "Living people" category.
    
    Args:
        soup: BeautifulSoup object of the Wikipedia page
        
    Returns:
        True if a death date is found, False otherwise
    """
    # Strategy 1: Check categories first (most reliable for Wikipedia)
    categories_div = soup.find('div', id='mw-normal-catlinks')
    if categories_div:
        cat_text = categories_div.get_text()
        
        # Negative signal - person is alive
        if re.search(r'\bLiving people\b', cat_text):
            return False
        
        # Positive signals - person is deceased
        death_category_patterns = [
            r'\d{4} deaths',               # "1980 deaths"
            r'Deaths in \d{4}',            # "Deaths in 1980"
            r'\d{4} births',               # If we see births category but no living people, likely dead
            r'People who died',            # Various death categories
            r'Murdered',                   # Specific death categories
            r'Executed',
            r'Suicides',
            r'Assassination',
            r'victims',
        ]
        
        for pattern in death_category_patterns:
            if re.search(pattern, cat_text, re.I):
                return True
    
    # Strategy 2: Infobox check (multiple field names)
    infobox = soup.find('table', class_='infobox')
    if infobox:
        # Check multiple death-related headers
        death_headers = [
            r'\bDied\b',
            r'\bDeath\b',
            r'\bDeceased\b',
            r'\bResting place\b',
            r'\bBuried\b',
            r'\bDeath date\b',
            r'\bDate of death\b',
            r'\bDisappeared\b',  # For missing persons presumed dead
        ]
        
        for header_pattern in death_headers:
            header = infobox.find(lambda tag: tag.name in ['th', 'td', 'caption'] and 
                                 re.search(header_pattern, tag.get_text(strip=True), re.I))
            if header:
                # Verify there's actual date content (not just the header)
                header_text = header.get_text(strip=True)
                # Check the header itself or the next cell for a year
                if re.search(r'\d{4}', header_text):
                    return True
                # Check the next sibling cell
                next_cell = header.find_next_sibling()
                if next_cell and re.search(r'\d{4}', next_cell.get_text()):
                    return True
                # Check the parent row's td if this is a th
                if header.name == 'th':
                    parent_row = header.find_parent('tr')
                    if parent_row:
                        td = parent_row.find('td')
                        if td and re.search(r'\d{4}', td.get_text()):
                            return True
    
    # Strategy 3: First paragraph analysis (most biographies state death in opening)
    # Get the first real paragraph (skip coordinate paragraphs)
    paragraphs = soup.find_all('p')
    content_paragraphs = []
    for p in paragraphs:
        # Skip empty or coordinate paragraphs
        text = p.get_text(strip=True)
        if len(text) > 20 and not text.startswith('Coordinates:'):
            content_paragraphs.append(p)
        if len(content_paragraphs) >= 10:  # Check up to 10 content paragraphs
            break
    
    for p in content_paragraphs:
        text = p.get_text()
        
        # Pattern 1: Birth-death date ranges (highest confidence)
        if re.search(r'\([^)]*\b\d{3,4}\b[^)]*[–—\-][^)]*\b\d{3,4}\b[^)]*\)', text):
            return True
        
        # Pattern 2: "was a/an" (past tense usually indicates deceased)
        if re.search(r'\bwas\s+(?:a|an)\s+\w+', text, re.I):
            # Double-check it's not about a past role
            if not re.search(r'was\s+(?:a|an)\s+\w+\s+(?:from|between|during|in\s+\d{4})', text, re.I):
                # Check if there's also a year mentioned nearby (stronger signal)
                if re.search(r'\b(?:1[0-9]{3}|20[0-2][0-9])\b', text):
                    return True
        
        # Pattern 3: Explicit death keywords with years
        death_patterns = [
            r'\b(?:died|d\.)\s+(?:on\s+)?[\w\s,]*\b\d{4}\b',  # died/d. with year
            r'†\s*[\w\s,]*\b\d{4}\b',                          # Death symbol with year
            r'\b(?:deceased|death)\b.*\b\d{4}\b',              # deceased/death with year
            r'\b(?:passed away|passing)\b.*\b\d{4}\b',         # passed away with year
            r'\b(?:killed|murdered|executed)\b.*\b\d{4}\b',    # violent death with year
            r'\b(?:perished|drowned|crashed)\b.*\b\d{4}\b',    # accident death with year
            r'\b(?:suicide|hanged)\b.*\b\d{4}\b',              # suicide with year
            r'\blast seen\b.*\b\d{4}\b',                       # missing persons
            r'\b(?:found dead|body found)\b',                  # found dead
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\s*[)–—\-]',  # Date followed by dash/paren
        ]
        
        for pattern in death_patterns:
            if re.search(pattern, text, re.I):
                return True
    
    # Strategy 4: Check other infobox table formats (some templates differ)
    all_tables = soup.find_all('table', class_=re.compile(r'infobox|biography|vcard', re.I))
    for table in all_tables:
        table_text = table.get_text()
        # Look for death patterns in the entire table text
        if re.search(r'\bDied\b.*\d{4}', table_text, re.I):
            return True
        if re.search(r'[–—\-]\s*\d{1,2}\s+\w+\s+\d{4}', table_text):  # dash followed by death date
            return True
    
    # Strategy 5: Check hatnotes (disambiguation notes at top)
    hatnotes = soup.find_all('div', class_=re.compile(r'hatnote'))
    for hatnote in hatnotes:
        if re.search(r'\b(?:died|deceased)\b.*\d{4}', hatnote.get_text(), re.I):
            return True
    
    # Strategy 6: Check "Death" or "Later life and death" sections
    section_headers = soup.find_all(['h2', 'h3'], string=re.compile(r'\bDeath\b|\bFinal\b|\bLast\s+years\b|\bPassing\b', re.I))
    if section_headers:
        return True
    
    # Strategy 7: Special Wikipedia templates
    # Some articles use specific templates for death information
    death_templates = soup.find_all(attrs={'class': re.compile(r'death-date|deathdate|dday', re.I)})
    if death_templates:
        return True
    
    # Strategy 8: Check image captions (often contain life dates)
    captions = soup.find_all(['div', 'p'], class_=re.compile(r'caption|thumb', re.I))
    for caption in captions:
        caption_text = caption.get_text()
        if re.search(r'\b\d{4}\s*[–—\-]\s*\d{4}\b', caption_text):
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


def generate_summary_report(report_path: Path):
    """Reads the detailed CSV report and generates a summary text file with aligned formatting."""
    if not report_path.exists():
        logging.info("Validation report not found. Skipping summary generation.")
        return

    summary_path = report_path.parent / "adb_validation_summary.txt"
    
    # --- Create a backup of the existing summary report before overwriting ---
    if summary_path.exists():
        logging.info(f"Validation summary '{summary_path}' already exists. Creating a backup.")
        try:
            backup_dir = Path('data/backup')
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{summary_path.stem}.{timestamp}{summary_path.suffix}.bak"
            shutil.copy2(summary_path, backup_path)
            logging.info(f"  -> Backup created at: {backup_path}")
        except (IOError, OSError) as e:
            logging.warning(f"Could not create backup for summary report: {e}")
            
    total_records, valid_records, failed_records = 0, 0, 0
    no_wiki_link, fetch_fail, no_death, name_mismatch, other_errors = 0, 0, 0, 0, 0
    research_entries, person_entries = 0, 0
    research_valid, research_failed = 0, 0

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            total_records = len(rows)
            if total_records == 0:
                logging.warning("Report is empty. Cannot generate summary.")
                return

            for row in rows:
                # Count entry types
                entry_type = row.get('Entry_Type', 'Person')  # Default to Person for old reports
                if entry_type == 'Research':
                    research_entries += 1
                    if row.get('Status') in ['OK', 'VALID']:
                        research_valid += 1
                    else:
                        research_failed += 1
                else:
                    person_entries += 1
                
                # Count validation status
                if row.get('Status') in ['OK', 'VALID']:
                    valid_records += 1
                else:
                    failed_records += 1
                    notes = row.get('Notes', '')
                    if "No Wikipedia link found on ADB page" in notes: no_wiki_link += 1
                    elif "Research entry - Wikipedia not expected" in notes: continue  # Don't count as error
                    elif "Failed to fetch Wikipedia page" in notes: fetch_fail += 1
                    elif "Name mismatch" in notes: name_mismatch += 1
                    elif "Death date not found" in notes: no_death += 1
                    else: other_errors += 1
        
        # --- Build Formatted Report ---
        title = "Astro-Databank Validation Summary"
        banner_width = 48
        banner = "=" * banner_width
        centered_title = title.center(banner_width)

        # Overall Statistics
        max_count_width = len(f"{total_records:,}")
        s1_label = "Total Records in Report:"
        s2_label = "Valid Records:"
        s3_label = "Failed Records:"
        s2_perc = f"({valid_records/total_records:.1%})" if total_records > 0 else "(0.0%)"
        s3_perc = f"({failed_records/total_records:.1%})" if total_records > 0 else "(0.0%)"
        
        # Define column widths for alignment
        stat_label_width = 26
        stat_num_width = max_count_width
        stat_perc_width = 8 # e.g., "(100.0%)"

        overall_stats = [
            f"--- Overall Statistics ---",
            f"{s1_label:<{stat_label_width}}{total_records:>{stat_num_width},}",
            f"{s2_label:<{stat_label_width}}{valid_records:>{stat_num_width},d} {s2_perc:>{stat_perc_width}}",
            f"{s3_label:<{stat_label_width}}{failed_records:>{stat_num_width},d} {s3_perc:>{stat_perc_width}}"
        ]
        
        # Entry Type Breakdown
        entry_type_stats = []
        if research_entries > 0 or person_entries > 0:
            entry_type_stats.append(f"--- Entry Type Breakdown ---")
            p1_label = "Person Entries:"
            p2_label = "Research Entries:"
            p1_perc = f"({person_entries/total_records:.1%})" if total_records > 0 else "(0.0%)"
            p2_perc = f"({research_entries/total_records:.1%})" if total_records > 0 else "(0.0%)"
            
            entry_type_stats.extend([
                f"{p1_label:<{stat_label_width}}{person_entries:>{stat_num_width},d} {p1_perc:>{stat_perc_width}}",
                f"{p2_label:<{stat_label_width}}{research_entries:>{stat_num_width},d} {p2_perc:>{stat_perc_width}}"
            ])
            
            if research_entries > 0:
                entry_type_stats.append("")
                entry_type_stats.append("Research Entry Details:")
                r1_label = "  Valid Research:"
                r2_label = "  Failed Research:"
                r1_perc = f"({research_valid/research_entries:.1%})" if research_entries > 0 else "(0.0%)"
                r2_perc = f"({research_failed/research_entries:.1%})" if research_entries > 0 else "(0.0%)"
                
                entry_type_stats.extend([
                    f"{r1_label:<{stat_label_width}}{research_valid:>{stat_num_width},d} {r1_perc:>{stat_perc_width}}",
                    f"{r2_label:<{stat_label_width}}{research_failed:>{stat_num_width},d} {r2_perc:>{stat_perc_width}}"
                ])

        # Failure Analysis
        failure_analysis = []
        if failed_records > 0:
            failure_analysis.append(f"--- Failure Analysis ({failed_records:,} Records) ---")
            
            fail_data = [
                ("1. No Wikipedia Link on ADB Page:", no_wiki_link),
                ("2. Could Not Fetch Wikipedia Page:", fetch_fail),
                ("3. Death Date Not Found:", no_death),
                ("4. Name Mismatch:", name_mismatch),
                ("5. Other Errors (e.g., Disambig.):", other_errors)
            ]
            
            # Use dynamic padding for perfect alignment
            max_num_width = len(f"{max(d[1] for d in fail_data):,}") if fail_data else 1
            perc_width = 8 # e.g., " (10.0%)"

            for label, count in fail_data:
                perc_str = f"({count/total_records:.1%})" if total_records > 0 else "(0.0%)"
                # Create the right-aligned part of the string
                right_part = f"{count:>{max_num_width},d} {perc_str:>{perc_width}}"
                # Calculate padding needed to fill the rest of the banner width
                padding = " " * (banner_width - len(label) - len(right_part))
                line = f"{label}{padding}{right_part}"
                failure_analysis.append(line)
        
        # Note about Research entries
        notes = []
        if research_entries > 0:
            notes.extend([
                "",
                "Note: Research entries typically lack Wikipedia pages",
                "      as they represent anonymous cases, events, or",
                "      medical conditions rather than individuals."
            ])
        
        # Assemble all report lines into a single list
        report_lines = [
            banner,
            centered_title,
            banner,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            *overall_stats,
            "",
            *entry_type_stats,
            "",
            *failure_analysis,
            *notes,
            banner
        ]
        
        summary_content = "\n".join(report_lines)
        
        # Write to file
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_content)

        # Print to console
        print("\n")
        print(summary_content)
        print("\n")
        logging.info(f"Summary report saved to '{summary_path}'")

    except (IOError, csv.Error) as e:
        logging.error(f"Failed to generate summary report: {e}")

import signal
from contextlib import contextmanager

@contextmanager
def timeout(seconds):
    """Context manager to timeout any operation."""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    # Set the timeout handler
    if hasattr(signal, 'SIGALRM'):
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # On Windows, we can't use SIGALRM, so just yield without timeout
        # This is why it might hang on Windows
        yield

def worker_task_with_timeout(line: str, pbar: tqdm) -> dict:
    """Wrapper to add timeout to worker_task."""
    import threading
    import queue
    
    result_queue = queue.Queue()
    exception_queue = queue.Queue()
    
    def target():
        try:
            result = worker_task(line, pbar)
            result_queue.put(result)
        except Exception as e:
            exception_queue.put(e)
    
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout=60)  # 60 second timeout per record (increased for slow ADB responses)
    
    if thread.is_alive():
        # Thread is still running, it's hung
        try:
            parts = line.strip().split('\t')
            arn = parts[0] if parts else "unknown"
            name = f"{parts[2]}, {parts[3]}" if len(parts) > 3 else "unknown"
        except:
            arn, name = "unknown", "unknown"
        
        tqdm.write(f"ERROR: Worker timeout for ARN {arn} ({name})")
        return {'ARN': arn, 'ADB_Name': name, 'Status': 'ERROR', 'Notes': 'Processing timeout (30s)'}
    
    # Check for exceptions
    if not exception_queue.empty():
        e = exception_queue.get()
        tqdm.write(f"ERROR: Worker exception: {e}")
        return None
    
    # Get result
    if not result_queue.empty():
        return result_queue.get()
    
    return None

def worker_task(line: str, pbar: tqdm) -> dict:
    """
    Validates a single ADB record against Wikipedia data.
    
    Implements the complete validation pipeline for one record:
    extracts data from the line, fetches the ADB page, finds Wikipedia
    links, resolves to English Wikipedia, handles redirects and
    disambiguation, and performs name/death validation.
    
    Args:
        line: Tab-delimited line from the ADB export file
        pbar: Progress bar for status updates
        
    Returns:
        Dictionary with validation results for CSV output
    """

    import traceback
    
    # Extract ARN for debugging
    try:
        parts = line.strip().split('\t')
        arn = parts[0] if parts else "unknown"
    except:
        arn = "unknown"
    
    debug_log(f"[{arn}] Starting worker_task")

    if shutdown_event.is_set():
        return None # Exit early if shutdown is requested

    time.sleep(REQUEST_DELAY) # Add a small delay to be a polite scraper
    parts = line.strip().split('\t')
    # The new input format has 17 columns, with the link at the end.
    if len(parts) < 17: return None

    # --- Extract data fields by their index from the new format ---
    arn, last_name, first_name, birth_year = parts[0], parts[2], parts[3], parts[7]
    
    # Unquote the URL immediately to handle all special characters (e.g., %C3%A9 for é).
    adb_url = unquote(parts[16])

    # Reconstruct name for validation and logging purposes.
    adb_name = f"{last_name}, {first_name}".strip(', ')
    
    # Determine entry type
    full_name = adb_name if adb_name else f"{last_name} {first_name}".strip()
    entry_type = "Research" if is_research_entry(full_name, first_name) else "Person"
    
    # Initialize result with entry type
    result = {
        'ARN': arn, 
        'ADB_Name': adb_name.strip(),
        'Entry_Type': entry_type
    }
    
    if not adb_url:
        return {**result, 'Status': 'ERROR', 'Notes': 'Missing ADB URL in source file'}
    
    # Build the appropriate URL based on entry type
    full_name = adb_name if adb_name else f"{last_name} {first_name}".strip()
    
    # For entries that look like Research entries, try Research: prefix first
    if is_research_entry(full_name, first_name) and '/astro-databank/' in adb_url:
        base_url, path = adb_url.split('/astro-databank/', 1)
        if not path.startswith('Research:'):
            # Try Research URL first for known patterns
            research_url = f"{base_url}/astro-databank/Research:{path}"
            debug_log(f"ARN {arn}: Trying Research URL for '{full_name}': {research_url}")
            
            # Quick check if Research URL exists
            test_response = SESSION.head(research_url, headers={'User-Agent': USER_AGENT}, 
                                        timeout=5, allow_redirects=True)
            if test_response.status_code == 200:
                adb_url = research_url
                debug_log(f"ARN {arn}: Research URL confirmed: {research_url}")
            else:
                debug_log(f"ARN {arn}: Research URL failed, using original: {adb_url}")
    
    # Check if Wikipedia search is disabled
    skip_wiki_search = os.environ.get('NO_WIKI_SEARCH', '').lower() == 'true'
    
    debug_log(f"[{arn}] Fetching ADB page: {adb_url}")
    
    # Get Wikipedia URL with optional search fallback
    try:
        initial_wiki_url = get_initial_wiki_url_from_adb(adb_url)
        debug_log(f"[{arn}] ADB page fetched, wiki URL: {initial_wiki_url}")
    except Exception as e:
        debug_log(f"[{arn}] ERROR fetching ADB page: {e}")
        return {**result, 'Status': 'ERROR', 'Notes': f'Failed to fetch ADB page: {str(e)[:100]}'}
    
    if not initial_wiki_url:
        # Research entries often don't have Wikipedia pages
        if entry_type == 'Research':
            debug_log(f"ARN {arn}: Research entry - no Wikipedia link expected")
            return {**result, 'Status': 'VALID', 'WP_URL': '', 
                   'Notes': 'Research entry - Wikipedia not expected'}
        else:
            # For person entries, try Wikipedia search if enabled
            if not skip_wiki_search:
                debug_log(f"[{arn}] Starting Wikipedia search for: {adb_name}")
                
                try:
                    search_results = search_wikipedia(adb_name, birth_year)
                    debug_log(f"[{arn}] Search returned {len(search_results)} results")
                    
                    if search_results:
                        debug_log(f"[{arn}] Checking search results for best match...")
                        initial_wiki_url = find_best_wikipedia_match(adb_name, birth_year, search_results, pbar)
                        debug_log(f"[{arn}] Best match result: {initial_wiki_url}")
                except Exception as e:
                    debug_log(f"[{arn}] Wikipedia search failed: {e}")
                    initial_wiki_url = None
            
            # Check if we found anything
            if not initial_wiki_url:
                if skip_wiki_search:
                    notes = 'No Wikipedia link found on ADB page'
                else:
                    notes = 'No Wikipedia link on ADB; Wikipedia search found no matches'
                debug_log(f"ARN {arn}: {notes}")
                return {**result, 'Status': 'ERROR', 'Notes': notes}
    
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
    parser.add_argument("--force", action="store_true", help="Force reprocessing of all records, overwriting the existing report.")
    parser.add_argument("--report-only", action="store_true", help="Generate the summary report for an existing validation CSV and exit.")
    parser.add_argument("--retry-failed", action="store_true", help="Re-process only the records marked as FAIL or ERROR in the existing report.")
    parser.add_argument("--show-research-categories", action="store_true", help="Display loaded research categories and exit.")
    parser.add_argument("--export-undetected", action="store_true", help="Export entries that failed but might be research entries.")
    parser.add_argument("--no-wiki-search", action="store_true", 
                       help="Disable Wikipedia search fallback when no link found on ADB page.")
    args = parser.parse_args()
    
    # Handle research categories display
    if args.show_research_categories:
        print_research_categories_summary()
        categories = load_research_categories()
        print(f"\nCategories file location: {RESEARCH_CATEGORIES_FILE}")
        print("Edit this file to add new patterns.\n")
        sys.exit(0)
    
    input_path, output_path = Path(args.input_file), Path(args.output_file)
    
    if args.report_only:
        print("\n--- Generating Summary Report Only ---")
        generate_summary_report(output_path)
        sys.exit(0)
        
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        logging.error(f"Input file not found: {input_path}"); sys.exit(1)

    fieldnames = ['ARN', 'ADB_Name', 'Entry_Type', 'WP_URL', 'WP_Name', 'Name_Match_Score', 'Death_Date_Found', 'Status', 'Notes']
    
    valid_records, processed_arns, initial_ok_count = load_existing_records(output_path)
    
    with open(input_path, 'r', encoding='utf-8') as infile:
        all_lines = infile.readlines()[1:]
    
    # Create a quick lookup map of ARN -> line for efficient filtering
    arn_to_line_map = {line.split('\t')[0]: line for line in all_lines if line.strip()}

    lines_to_process = []
    if args.retry_failed:
        failed_arns = processed_arns - {rec['ARN'] for rec in valid_records}
        if not failed_arns:
            print(f"\n{Colors.GREEN}No failed records to retry. All {len(processed_arns)} processed records are valid.{Colors.RESET}")
            generate_summary_report(output_path)
            sys.exit(0)
            
        for arn in sorted(failed_arns, key=int):
            if arn in arn_to_line_map:
                lines_to_process.append(arn_to_line_map[arn])
    else:
        for line in all_lines:
            try:
                arn = line.split('\t')[0]
                arn_val = int(arn)
                if arn in processed_arns or arn_val < args.start_from or (args.stop_at > 0 and arn_val > args.stop_at):
                    continue
                lines_to_process.append(line)
            except (IndexError, ValueError):
                continue

    all_records_processed = not lines_to_process

    # If all records are processed and --force is not used, ask interactively.
    if all_records_processed and not args.force:
        print("")
        print(f"{Colors.GREEN}All records in the specified range have already been processed.{Colors.RESET}")
        print(f"{Colors.YELLOW}You can force reprocessing, but this will overwrite the existing report.{Colors.RESET}")
        response = input("Proceed with full reprocessing? (Y/N): ").lower()
        if response == 'y':
            args.force = True # Trigger the force logic below
        else:
            print("\nExiting without reprocessing.\n")
            sort_report_by_arn(output_path, fieldnames)
            generate_summary_report(output_path)
            return

    # If --force is active (either from CLI or interactive prompt), handle file deletion and state reset.
    if args.force:
        if output_path.exists():
            print("")
            print(f"{Colors.YELLOW}WARNING: This will re-validate all records and overwrite the report at '{output_path}'.")
            print(f"This operation can take over an hour to complete.{Colors.RESET}")
            confirm = input("Are you sure you want to proceed? (Y/N): ").lower()
            if confirm != 'y':
                print("\nOperation cancelled by user.\n")
                return

            # Create a timestamped backup before deleting the original
            try:
                backup_dir = Path('data/backup')
                backup_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"{output_path.stem}.{timestamp}{output_path.suffix}.bak"
                shutil.copy2(output_path, backup_path)
                print("")
                logging.info(f"Created backup of existing report at: {backup_path}")
            except (IOError, OSError) as e:
                logging.error(f"{Colors.RED}Failed to create backup file: {e}{Colors.RESET}")
                sys.exit(1)

            try:
                output_path.unlink()
                logging.info(f"Deleted existing report: {output_path}")
            except OSError as e:
                logging.error(f"{Colors.RED}Could not delete existing report file: {e}{Colors.RESET}")
                sys.exit(1)
        
        # Reset state to re-process everything within the specified range
        processed_arns.clear()
        initial_ok_count = 0
        lines_to_process.clear()
        for line in all_lines:
            try:
                arn = line.split('\t')[0]
                arn_val = int(arn)
                if arn_val < args.start_from or (args.stop_at > 0 and arn_val > args.stop_at):
                    continue
                lines_to_process.append(line)
            except (IndexError, ValueError):
                continue
        
    if not lines_to_process:
        print("")
        print(f"{Colors.GREEN}All records in the specified range have already been processed.{Colors.RESET}")
        sort_report_by_arn(output_path, fieldnames)
        generate_summary_report(output_path)
        return

    # Set environment variable for Wikipedia search control
    if args.no_wiki_search:
        os.environ['NO_WIKI_SEARCH'] = 'true'
    else:
        os.environ['NO_WIKI_SEARCH'] = 'false'
    
    # --- Print startup banner ---
    if args.retry_failed:
        print(f"\n{Colors.YELLOW}--- Running in Retry-Failed Mode ---{Colors.RESET}")
        print(f"Found {len(valid_records):,} valid records to keep and {len(lines_to_process):,} failed records to re-process.")
    elif not processed_arns:
        print(f"{Colors.YELLOW}Starting enhanced validation for {len(all_lines):,} records using {args.workers} workers.{Colors.RESET}")
        print(f"Output will be saved to '{output_path}'.")
    else:
        print(f"{Colors.YELLOW}\nResuming validation: {len(processed_arns):,} records already processed ({initial_ok_count:,} valid).{Colors.RESET}")
        print(f"Now processing the remaining {len(lines_to_process):,} records using {args.workers} workers.")

    print("-" * 70)
    print(f"{Colors.YELLOW}NOTE: This script performs live web scraping for thousands of records")
    print(f"      and can take over an hour to complete.")
    print(f"      You can safely interrupt with 'Ctrl+C' and resume at any time.{Colors.RESET}")
    print("-" * 70)
    
    was_interrupted = False
    pbar = tqdm(total=len(lines_to_process), desc="Validating records", ncols=120, smoothing=0.01)
    session_ok_count = 0
    session_research_count = 0  # Track Research entries
    newly_processed_results = []
    newly_valid_count = 0  # Track newly valid in retry mode
    
    executor = ThreadPoolExecutor(max_workers=args.workers)
    futures = {executor.submit(worker_task_with_timeout, line, pbar) for line in lines_to_process}
    
    try:
        # Determine the output stream based on the mode.
        # In normal mode, we append directly to the file.
        # In retry mode, we collect results in memory first.
        output_file = None
        writer = None
        if not args.retry_failed:
            file_exists = output_path.exists() and len(processed_arns) > 0
            output_file = open(output_path, 'a', encoding='utf-8', newline='')
            writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()

        # Track total records differently for retry-failed mode
        if args.retry_failed:
            # In retry mode: total = kept valid records + retried records
            total_records_count = len(valid_records) + len(lines_to_process)
            # Track newly valid from this session
            newly_valid_count = 0
        else:
            total_processed_before_session = len(processed_arns)
        
        for future in as_completed(futures):
            pbar.update(1)
            try:
                res = future.result()
                if not res: continue

                # Either write to file or append to list based on mode
                if args.retry_failed:
                    newly_processed_results.append(res)
                    if res.get('Status') in ['OK', 'VALID']:
                        newly_valid_count += 1
                else:
                    writer.writerow(res)

                if res.get('Status') in ['OK', 'VALID']:
                    session_ok_count += 1
                
                # Count Research entries
                if res.get('Entry_Type') == 'Research':
                    session_research_count += 1
                
                # Update postfix based on mode
                if args.retry_failed:
                    # Show: previously valid + newly valid / total expected
                    total_valid = len(valid_records) + newly_valid_count
                    percentage = (total_valid / total_records_count) * 100 if total_records_count > 0 else 0
                    postfix_str = f"{total_valid:,}/{total_records_count:,}={percentage:.0f}%, newly valid: {newly_valid_count:,}"
                else:
                    total_ok_count = initial_ok_count + session_ok_count
                    total_processed_so_far = total_processed_before_session + pbar.n
                    if total_processed_so_far > 0:
                        percentage = (total_ok_count / total_processed_so_far) * 100
                        postfix_str = f"{total_ok_count:,}/{total_processed_so_far:,}={percentage:.0f}%, research: {session_research_count:,}"
                    else:
                        postfix_str = "0/0=0%, research: 0"
                pbar.set_postfix_str(f"valid: {postfix_str}")

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
        
        # Ensure the file handle is closed if it was opened
        if output_file:
            output_file.close()

        # In retry-failed mode, we now combine and overwrite the report file.
        if args.retry_failed and newly_processed_results:
            print(f"\n{Colors.YELLOW}Rebuilding and sorting the final report...{Colors.RESET}")
            combined_results = valid_records + newly_processed_results
            try:
                # Overwrite the file with the combined, sorted data
                with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
                    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(sorted(combined_results, key=lambda r: int(r['ARN'])))
            except (IOError, csv.Error) as e:
                logging.error(f"Failed to write the rebuilt report file: {e}")
        else:
            # In normal mode, we just sort the existing file.
            sort_report_by_arn(output_path, fieldnames)
        
        # Generate the final summary report
        generate_summary_report(output_path)

        processed_this_session = pbar.n if pbar else 0
        
        print("") # Add a newline for clean summary output
        if was_interrupted:
            if args.retry_failed:
                # In retry mode, show how many failed records were retried
                final_msg = (
                    f"Process interrupted. {processed_this_session:,} failed records were retried this session.\n"
                    f"Run the script again with --retry-failed to continue retrying.\n"
                )
            else:
                total_ok_count = initial_ok_count + session_ok_count
                total_processed_so_far = len(processed_arns) + processed_this_session
                final_msg = (
                    f"Process interrupted. {processed_this_session:,} records were processed this session.\n"
                    f"Total processed so far: {total_processed_so_far:,} records ({total_ok_count:,} valid).\n"
                    f"Run the script again to resume.\n"
                )
            print(f"{Colors.YELLOW}INFO: {final_msg}{Colors.RESET}")
        else:
            if args.retry_failed:
                # Count final results from the combined data
                final_valid_count = len([r for r in (valid_records + newly_processed_results) if r.get('Status') in ['OK', 'VALID']])
                total_records = len(valid_records) + len(newly_processed_results)
                final_msg = (
                    f"Retry complete. {processed_this_session:,} failed records were reprocessed.\n"
                    f"Final result: {final_valid_count:,} valid out of {total_records:,} total records.\n"
                    f"Full report saved at: {output_path}."
                )
            else:
                total_ok_count = initial_ok_count + session_ok_count
                final_msg = (
                    f"Finished processing all {len(all_lines):,} records ({total_ok_count:,} valid).\n"
                    f"Full report saved at: {output_path}."
                )
            print(f"{Colors.GREEN}INFO: {final_msg}{Colors.RESET}")

if __name__ == "__main__":
    main()

# === End of src/validate_adb_data.py ===

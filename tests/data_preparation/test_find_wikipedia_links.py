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
# Filename: tests/data_preparation/test_find_wikipedia_links.py

"""
Unit tests for the Wikipedia link-finding script (src/find_wikipedia_links.py).

This test suite covers the script's core logic, including the identification of
research entries, parsing of HTML content for disambiguation pages, handling
of mocked API calls to Wikipedia, and comprehensive input file validation to
ensure graceful handling of malformed or corrupted ADB data.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup
from tqdm import tqdm
# Import the entire module so we can patch objects within it
from src import find_wikipedia_links
from src.find_wikipedia_links import (
    find_best_wikipedia_match,
    find_matching_disambiguation_link_from_search,
    get_english_wiki_url,
    is_disambiguation_page,
    is_research_entry,
    load_processed_ids,
    search_wikipedia,
    worker_task,
)


@pytest.fixture
def mock_research_config(tmp_path: Path) -> Path:
    """Creates a temporary research categories JSON file for testing."""
    config_content = {
        "categories": {
            "prefixes": ["Earthquakes:"],
            "patterns": [r"Airplane Crashes \d{4}'s"],
            "exact_matches": ["Comets 1900-1982"]
        },
        "auto_detected": {"entries": []}
    }
    config_file = tmp_path / "adb_research_categories.json"
    config_file.write_text(json.dumps(config_content))
    return config_file


@pytest.mark.parametrize("name, first_name, expected", [
    ("Comets 1900-1982", "", True),         # Exact match
    ("Earthquakes: Chile", "", True),        # Prefix match
    ("Airplane Crashes 1980's", "", True),   # Pattern match
    ("Some Event 1950", "", True),           # Trailing year match (implicit rule)
    ("Smith, John", "John", False),          # Standard person name
    ("Vercors", "", False),                   # Single name, no year
    ("A normal name", "", False),            # Non-matching name
])
def test_is_research_entry(name, first_name, expected, mocker, mock_research_config):
    """
    Tests the is_research_entry function against various name patterns.
    """
    # Load the mock config content into a dictionary
    with open(mock_research_config, 'r') as f:
        mock_categories_data = json.load(f)

    # Directly mock the load_research_categories function to return our test data.
    # This is the most robust way to test this function's logic.
    mocker.patch('src.find_wikipedia_links.load_research_categories', return_value=mock_categories_data)
    
    # We no longer need to reload the module or reset the cache.
    assert find_wikipedia_links.is_research_entry(name, first_name) == expected


# --- Tests for HTML parsing helpers ---

@pytest.mark.parametrize("html_content, expected", [
    # Case 1: Standard disambiguation page with an ID
    ('<div><div id="disambiguation"></div></div>', True),
    # Case 2: Common class name
    ('<div><p class="disambiguation">This is a list</p></div>', True),
    # Case 3: Common text indicator
    ('<html><body>This page may refer to:</body></html>', True),
    # Case 4: A normal page without any indicators
    ('<html><body><h1>A normal article</h1><p>Content.</p></body></html>', False),
])
def test_is_disambiguation_page(html_content, expected):
    """Tests the detection of Wikipedia disambiguation pages from HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    assert is_disambiguation_page(soup) == expected


def test_find_matching_disambiguation_link_from_search():
    """Tests finding the correct link from a disambiguation page's list."""
    html_content = """
    <ul>
      <li><a href="/wiki/Person_A">Person A</a> (born 1950), a scientist</li>
      <li>Some other text without a link (1960)</li>
      <li><a href="/wiki/Person_B">Person B</a>, an artist born in 1970</li>
    </ul>
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Case 1: Should find a match with a clear birth year
    result_url = find_matching_disambiguation_link_from_search(soup, "1950")
    assert result_url == "https://en.wikipedia.org/wiki/Person_A"

    # Case 2: Should find a match where the year is part of the text
    result_url_2 = find_matching_disambiguation_link_from_search(soup, "1970")
    assert result_url_2 == "https://en.wikipedia.org/wiki/Person_B"

    # Case 3: Should return None when no match is found for the given year
    result_url_3 = find_matching_disambiguation_link_from_search(soup, "1999")
    assert result_url_3 is None


# --- Tests for Wikipedia API interaction (mocked) ---

def test_get_english_wiki_url(mocker):
    """Tests the logic for finding an English Wikipedia link."""
    # Case 1: Already an English URL
    assert get_english_wiki_url("https://en.wikipedia.org/wiki/Test") == "https://en.wikipedia.org/wiki/Test"

    # Case 2: Non-English URL with a valid English interlanguage link
    mock_soup = BeautifulSoup('<a class="interlanguage-link-target" lang="en" href="https://en.wikipedia.org/wiki/English_Test"></a>', 'html.parser')
    mocker.patch('src.find_wikipedia_links.fetch_page_content', return_value=mock_soup)
    assert get_english_wiki_url("https://de.wikipedia.org/wiki/Test") == "https://en.wikipedia.org/wiki/English_Test"

    # Case 3: Non-English URL with no English link
    mock_soup_no_link = BeautifulSoup('<div>No link here</div>', 'html.parser')
    mocker.patch('src.find_wikipedia_links.fetch_page_content', return_value=mock_soup_no_link)
    assert get_english_wiki_url("https://fr.wikipedia.org/wiki/Test") is None


def test_search_wikipedia(mocker):
    """Tests the Wikipedia search functionality with a mocked API response."""
    mock_session_get = mocker.patch('src.find_wikipedia_links.SESSION.get')
    mock_response = mocker.MagicMock()
    # Simulate a successful API response
    mock_response.json.return_value = [
        "QueryName",
        ["Result One", "Result Two"],
        ["Description one", "Description two"],
        ["https://en.wikipedia.org/wiki/One", "https://en.wikipedia.org/wiki/Two"]
    ]
    mock_session_get.return_value = mock_response

    results = search_wikipedia("Da Vinci, Leonardo (1452)")
    assert len(results) == 2
    assert results[0] == ("Result One", "https://en.wikipedia.org/wiki/One")
    
    # Check that the name was cleaned correctly for the search API call
    called_params = mock_session_get.call_args.kwargs.get('params', {})
    assert called_params.get('search') == "Leonardo"


def test_find_best_wikipedia_match(mocker):
    """Tests the logic for finding the best match from Wikipedia search results."""
    mock_pbar = MagicMock(spec=tqdm)
    mock_fetch = mocker.patch('src.find_wikipedia_links.fetch_page_content')

    search_results = [
        ("Leonardo da Vinci", "https://en.wikipedia.org/wiki/Leonardo_da_Vinci"),
        ("Mona Lisa", "https://en.wikipedia.org/wiki/Mona_Lisa"), # low similarity
    ]

    # Case 1: Successful match with birth year in content
    mock_soup_success = BeautifulSoup("<html><body>...born 1452...</body></html>", 'html.parser')
    mock_fetch.return_value = mock_soup_success
    mocker.patch('src.find_wikipedia_links.is_disambiguation_page', return_value=False)

    result = find_best_wikipedia_match("Da Vinci, Leonardo", "1452", search_results, mock_pbar)
    assert result == "https://en.wikipedia.org/wiki/Leonardo_da_Vinci"
    mock_fetch.assert_called_once_with("https://en.wikipedia.org/wiki/Leonardo_da_Vinci")

    # Case 2: No match because birth year is not found
    mock_fetch.reset_mock()
    mock_soup_fail = BeautifulSoup("<html><body>...born 1999...</body></html>", 'html.parser')
    mock_fetch.return_value = mock_soup_fail

    result = find_best_wikipedia_match("Da Vinci, Leonardo", "1452", search_results, mock_pbar)
    assert result is None
    # It should have checked the first plausible result and failed.
    # The second result ("Mona Lisa") should be skipped due to low title similarity.
    mock_fetch.assert_called_once_with("https://en.wikipedia.org/wiki/Leonardo_da_Vinci")

    # Case 3: Match via a disambiguation page
    mock_fetch.reset_mock()
    # The mock soup MUST contain the birth year to pass the initial content check
    mock_soup_disambig = BeautifulSoup("<html><body>Disambiguation page for people born in 1974.</body></html>", 'html.parser')
    mock_fetch.return_value = mock_soup_disambig
    mocker.patch('src.find_wikipedia_links.is_disambiguation_page', return_value=True)
    mocker.patch('src.find_wikipedia_links.find_matching_disambiguation_link_from_search', return_value="https://en.wikipedia.org/wiki/Resolved_Link")

    disambig_search_results = [("Leonardo (disambiguation)", "https://en.wikipedia.org/wiki/Leonardo_(disambiguation)")]
    result = find_best_wikipedia_match("Leonardo", "1974", disambig_search_results, mock_pbar)
    assert result == "https://en.wikipedia.org/wiki/Resolved_Link"


@pytest.mark.parametrize("adb_link, search_result, expected_url, expected_notes", [
    # Case 1: Direct link found on ADB page
    ("https://de.wikipedia.org/wiki/Test", None, "https://en.wikipedia.org/wiki/English_Test", ""),
    # Case 2: No link on ADB, but found via search
    (None, "https://en.wikipedia.org/wiki/Search_Result", "https://en.wikipedia.org/wiki/Search_Result", ""),
    # Case 3: No link found anywhere
    (None, None, "", "No Wikipedia URL found"),
    # Case 4: Research entry, no link found (should have no notes)
    (None, None, "", ""),
])
def test_worker_task(mocker, adb_link, search_result, expected_url, expected_notes):
    """Tests the main worker_task logic under various mocked scenarios."""
    mock_pbar = MagicMock(spec=tqdm)
    mocker.patch('src.find_wikipedia_links.get_initial_wiki_url_from_adb', return_value=adb_link)
    mocker.patch('src.find_wikipedia_links.search_wikipedia', return_value=[("Some Result", "some_url")])
    mocker.patch('src.find_wikipedia_links.find_best_wikipedia_match', return_value=search_result)
    mocker.patch('src.find_wikipedia_links.get_english_wiki_url', return_value="https://en.wikipedia.org/wiki/English_Test" if adb_link else search_result)
    
    # Mock the new dependencies introduced in the worker_task validation logic
    mock_soup = MagicMock()
    mock_h1 = MagicMock()
    mock_h1.get_text.return_value = "Doe, John" # A name that will pass the fuzz ratio
    mock_soup.find.return_value = mock_h1
    mocker.patch('src.find_wikipedia_links.fetch_page_content', return_value=mock_soup)
    mocker.patch('thefuzz.fuzz.ratio', return_value=95) # Assume a good match
    is_research = (expected_notes == "" and expected_url == "")
    entry_name = "Research Event 2000" if is_research else "Doe, John"
    
    line = f"1\t123\t{entry_name.split(', ')[0]}\t{entry_name.split(', ')[1] if ',' in entry_name else ''}\tM\t1\t1\t1999\t12:00\t...\t00:00\tCity\tCountry\tLON\tLAT\tAA\tBio\tCat\thttps://www.astro.com/astro-databank/{entry_name}"
    
    # Mock is_research_entry to return True only for the specific research case
    mocker.patch('src.find_wikipedia_links.is_research_entry', return_value=is_research)
    
    result = find_wikipedia_links.worker_task(line, mock_pbar, 1)

    assert result is not None
    assert result['Wikipedia_URL'] == expected_url
    assert result['Notes'] == expected_notes


def test_load_processed_ids(tmp_path):
    """Tests reading an existing output file to correctly resume processing."""
    output_file = tmp_path / "adb_wiki_links.csv"

    # Case 1: File does not exist, should return empty sets and zero counts.
    p_ids, t_ids, links, max_idx, timeouts = load_processed_ids(output_file)
    assert p_ids == set()
    assert t_ids == set()
    assert links == 0
    assert max_idx == 0
    assert timeouts == 0

    # Case 2: File exists with a mix of processed, timed-out, and linkless records.
    csv_content = (
        'Index,idADB,ADB_Name,BirthYear,Entry_Type,Wikipedia_URL,Notes\n'
        '1,101,"Test, A",1900,Person,http://a.com,\n'
        '2,102,"Test, B",1901,Person,,\n'
        '3,103,"Test, C",1902,Person,,"Processing timeout"\n'
        '4,104,"Test, D",1903,Person,http://d.com,\n'
        '5,105,"Test, E",1904,Person,,"Processing timeout"\n'
    )
    output_file.write_text(csv_content)

    p_ids, t_ids, links, max_idx, timeouts = load_processed_ids(output_file)
    assert p_ids == {"101", "102", "104"}
    assert t_ids == {"103", "105"}
    assert links == 2
    assert max_idx == 5
    assert timeouts == 2

class TestInputFileValidation:
    """Tests for input file validation logic in the main function."""
    
    def test_empty_input_file(self, tmp_path, mocker, capsys):
        """Tests that an empty input file causes graceful exit with error message."""
        # Create empty input file
        empty_file = tmp_path / "adb_raw_export.txt"
        empty_file.write_text("")
        
        # Mock sys.argv to avoid argparse issues
        mocker.patch('sys.argv', ['find_wikipedia_links.py'])
        
        # Mock the config_loader to point to our test file
        mocker.patch('config_loader.get_path', return_value=str(empty_file))
        
        # Mock sys.exit to actually raise SystemExit so execution stops
        def mock_exit(code):
            raise SystemExit(code)
        mocker.patch('sys.exit', side_effect=mock_exit)
        
        # Run main function and expect SystemExit
        with pytest.raises(SystemExit) as exc_info:
            find_wikipedia_links.main()
        
        # Verify it exited with error code 1
        assert exc_info.value.code == 1
        
        # Check error message was logged
        captured = capsys.readouterr()
        assert "Input file is empty" in captured.out
        assert "ADB data fetching failed" in captured.out
    
    def test_header_only_file(self, tmp_path, mocker, capsys):
        """Tests that a file with only header causes graceful exit."""
        # Create file with only header
        header_only_file = tmp_path / "adb_raw_export.txt"
        header_only_file.write_text("Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tZoneAbbr\tZoneTimeOffset\tCity\tCountryState\tLongitude\tLatitude\tRating\tBio\tCategories\tLink\n")
        
        mocker.patch('sys.argv', ['find_wikipedia_links.py'])
        mocker.patch('config_loader.get_path', return_value=str(header_only_file))
        
        def mock_exit(code):
            raise SystemExit(code)
        mocker.patch('sys.exit', side_effect=mock_exit)
        
        with pytest.raises(SystemExit) as exc_info:
            find_wikipedia_links.main()
        
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "insufficient data" in captured.out
        assert "Found 1 lines, expected at least 2" in captured.out
    
    def test_malformed_header(self, tmp_path, mocker, capsys):
        """Tests that a file with insufficient columns in header fails validation."""
        # Create file with insufficient columns in header
        malformed_file = tmp_path / "adb_raw_export.txt"
        malformed_file.write_text("Index\tidADB\tLastName\n1\t123\tDoe\n")
        
        mocker.patch('sys.argv', ['find_wikipedia_links.py'])
        mocker.patch('config_loader.get_path', return_value=str(malformed_file))
        
        def mock_exit(code):
            raise SystemExit(code)
        mocker.patch('sys.exit', side_effect=mock_exit)
        
        with pytest.raises(SystemExit) as exc_info:
            find_wikipedia_links.main()
        
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "malformed header" in captured.out
        assert "Expected at least 19 columns, found 3" in captured.out
    
    def test_all_malformed_data_rows(self, tmp_path, mocker, capsys):
        """Tests that a file with all malformed data rows fails validation."""
        # Create file with proper header but all malformed data rows
        malformed_data_file = tmp_path / "adb_raw_export.txt"
        content = "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tZoneAbbr\tZoneTimeOffset\tCity\tCountryState\tLongitude\tLatitude\tRating\tBio\tCategories\tLink\n"
        content += "1\t123\tDoe\n"  # Too few columns
        content += "2\t124\n"       # Too few columns
        malformed_data_file.write_text(content)
        
        mocker.patch('sys.argv', ['find_wikipedia_links.py'])
        mocker.patch('config_loader.get_path', return_value=str(malformed_data_file))
        
        def mock_exit(code):
            raise SystemExit(code)
        mocker.patch('sys.exit', side_effect=mock_exit)
        
        with pytest.raises(SystemExit) as exc_info:
            find_wikipedia_links.main()
        
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No valid data rows found" in captured.out
        assert "All rows appear to be malformed" in captured.out
    
    def test_mixed_valid_invalid_rows(self, tmp_path, mocker, capsys):
        """Tests that a file with some valid rows passes validation and warns about invalid ones."""
        # Create file with mixed valid and invalid rows
        mixed_file = tmp_path / "adb_raw_export.txt"
        content = "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tZoneAbbr\tZoneTimeOffset\tCity\tCountryState\tLongitude\tLatitude\tRating\tBio\tCategories\tLink\n"
        # Valid row with 19 columns
        content += "1\t123\tDoe\tJohn\tM\t1\t1\t1990\t12:00\tEST\t-5:00\tNew York\tUSA\t40.7\t-74.0\tA\tBio\tCat\thttps://example.com\n"
        # Invalid row with too few columns  
        content += "2\t124\tSmith\n"
        # Another valid row
        content += "3\t125\tJones\tMary\tF\t2\t2\t1991\t13:00\tPST\t-8:00\tLA\tUSA\t34.0\t-118.0\tB\tBio2\tCat2\thttps://example2.com\n"
        mixed_file.write_text(content)
        
        # Mock the output path to avoid file operations in test
        output_file = tmp_path / "output.csv"
        
        # Mock all the dependencies that would be called after validation passes
        mocker.patch('sys.argv', ['find_wikipedia_links.py', '--verbose'])  # Enable verbose to see warnings
        mocker.patch('config_loader.get_path', side_effect=lambda x: str(mixed_file) if 'adb_raw_export' in x else str(output_file))
        
        # Mock research categories to avoid JSON decode errors
        mock_categories = {
            "categories": {"prefixes": [], "patterns": [], "exact_matches": []},
            "auto_detected": {"entries": []}
        }
        mocker.patch('src.find_wikipedia_links.load_research_categories', return_value=mock_categories)
        mocker.patch('src.find_wikipedia_links.load_processed_ids', return_value=(set(), set(), 0, 0, 0))
        
        # Mock network calls to prevent actual HTTP requests
        mocker.patch('src.find_wikipedia_links.get_initial_wiki_url_from_adb', return_value=None)
        mocker.patch('src.find_wikipedia_links.search_wikipedia', return_value=[])
        
        # Don't expect SystemExit since validation passes with 2 valid rows
        find_wikipedia_links.main()
        
        captured = capsys.readouterr()
        # Should show validation success
        assert "Validated input file: 2 valid rows found" in captured.out
        # Should warn about malformed row (now visible with --verbose)
        assert "Skipping malformed row 3" in captured.out
        # Should complete successfully 
        assert "SUCCESS:" in captured.out
    
    def test_file_read_error(self, tmp_path, mocker, capsys):
        """Tests handling of file read errors during validation."""
        # Create a file 
        error_file = tmp_path / "adb_raw_export.txt"
        error_file.write_text("test")
        
        mocker.patch('sys.argv', ['find_wikipedia_links.py'])
        mocker.patch('config_loader.get_path', return_value=str(error_file))
        
        # Mock os.path.getsize to pass the empty file check, then make open fail
        mocker.patch('os.path.getsize', return_value=100)  # Non-zero size
        
        # Only mock the specific open call for the input file, not all open calls
        original_open = __builtins__['open']
        def selective_open(*args, **kwargs):
            if args and str(args[0]) == str(error_file):
                raise IOError("Permission denied")
            return original_open(*args, **kwargs)
        mocker.patch('builtins.open', side_effect=selective_open)
        
        def mock_exit(code):
            raise SystemExit(code)
        mocker.patch('sys.exit', side_effect=mock_exit)
        
        with pytest.raises(SystemExit) as exc_info:
            find_wikipedia_links.main()
        
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Failed to read or validate input file" in captured.out
        assert "Permission denied" in captured.out

# === End of tests/data_preparation/test_find_wikipedia_links.py ===

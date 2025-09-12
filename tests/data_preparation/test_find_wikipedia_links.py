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
# Filename: tests/data_preparation/test_find_wikipedia_links.py

"""
Unit tests for the Wikipedia link-finding script (src/find_wikipedia_links.py).

This test suite covers the script's core logic, including the identification of
research entries, parsing of HTML content for disambiguation pages, handling
of mocked API calls to Wikipedia, and comprehensive input file validation to
ensure graceful handling of malformed or corrupted ADB data.
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Import the entire module so we can patch objects within it
from src import find_wikipedia_links
from src.find_wikipedia_links import (
    fetch_page_content,
    finalize_and_report,
    find_best_wikipedia_match,
    is_disambiguation_page,
    is_research_entry,
    load_processed_ids,
    load_research_categories,
    worker_task_with_timeout,
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


@pytest.fixture
def mock_sandbox(tmp_path: Path):
    """Creates a comprehensive sandbox for testing the main function."""
    # Create directories
    (tmp_path / "data" / "sources").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "data" / "config").mkdir(parents=True)
    
    # Create input file
    input_path = tmp_path / "data/sources/adb_raw_export.txt"
    input_content = "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tZoneAbbr\tZoneTimeOffset\tCity\tCountryState\tLongitude\tLatitude\tRating\tBio\tCategories\tLink\n"
    input_content += "1\t101\tDoe\tJohn\tM\t1\t1\t1990\t12:00\tEST\t-5:00\tNY\tUSA\t_lon\t_lat\tA\tBio\tCat\thttps://a.com\n"
    input_content += "2\t102\tSmith\tJane\tF\t2\t2\t1991\t13:00\tPST\t-8:00\tLA\tUSA\t_lon\t_lat\tA\tBio\tCat\thttps://b.com\n"
    input_path.write_text(input_content)

    # Create research categories config
    (tmp_path / "data/config/adb_research_categories.json").write_text('{"categories": {}}')
    
    return tmp_path


@pytest.mark.parametrize("name, first_name, expected", [
    # Test cases from mock_research_config
    ("Comets 1900-1982", "", True),         # Exact match
    ("Airplane Crashes 1980's", "", True),    # Pattern match
    ("Earthquakes: California", "", True),   # Prefix match
    # Test case for the final fallback regex (year at the end)
    ("Mundane Event 1999", "", True),
    # Standard person name should not match
    ("Smith, John", "John", False),
])
def test_is_research_entry(name, first_name, expected, mocker, mock_research_config):
    """Tests the is_research_entry function against various name patterns."""
    with open(mock_research_config, 'r') as f:
        mock_categories_data = json.load(f)
    mocker.patch('src.find_wikipedia_links.load_research_categories', return_value=mock_categories_data)
    assert find_wikipedia_links.is_research_entry(name, first_name) == expected


@pytest.mark.parametrize("html_content, expected", [
    ('<div><div id="disambiguation"></div></div>', True),
    ('<div><p class="disambiguation">Text</p></div>', True),
    ('<html><body>Normal page</body></html>', False),
])
def test_is_disambiguation_page(html_content, expected):
    soup = BeautifulSoup(html_content, 'html.parser')
    assert is_disambiguation_page(soup) == expected


def test_find_best_wikipedia_match_resolves_disambiguation(mocker):
    """
    Tests that the script correctly identifies and resolves a disambiguation page
    by finding the link that matches the subject's birth year.
    """
    name = "Smith, John"
    birth_year = "1950"

    disambiguation_url = "https://en.wikipedia.org/wiki/John_Smith_(disambiguation)"
    correct_person_relative_url = "/wiki/John_Smith_(actor)"
    correct_person_full_url = "https://en.wikipedia.org/wiki/John_Smith_(actor)"

    search_results = [("John Smith (disambiguation)", disambiguation_url)]

    # Mock HTML for the disambiguation page
    disambiguation_html = f"""
    <html><body>
    <h1>John Smith</h1>
    <div id="disambiguation">This is a disambiguation page.</div>
    <ul>
        <li><a href="/wiki/John_Smith_(musician)">John Smith</a> (born 1948), musician</li>
        <li><a href="{correct_person_relative_url}">John Smith</a> (born {birth_year}), actor</li>
        <li><a href="/wiki/John_Smith_(politician)">John Smith</a> (born 1952), politician</li>
    </ul>
    </body></html>
    """
    mock_disambiguation_soup = BeautifulSoup(disambiguation_html, 'html.parser')

    # Mock fetch_page_content to return the disambiguation page soup
    mock_fetch = mocker.patch('src.find_wikipedia_links.fetch_page_content', return_value=mock_disambiguation_soup)

    # Mock fuzz.ratio to be high enough to proceed with the check
    mocker.patch('thefuzz.fuzz.ratio', return_value=90)

    # Use a dummy tqdm object
    pbar = MagicMock()

    result_url = find_best_wikipedia_match(name, birth_year, search_results, pbar)

    assert result_url == correct_person_full_url
    mock_fetch.assert_called_once_with(disambiguation_url)


def test_load_processed_ids(tmp_path):
    """Tests reading an existing output file to correctly resume processing."""
    output_file = tmp_path / "adb_wiki_links.csv"
    csv_content = (
        'Index,idADB,ADB_Name,Wikipedia_URL,Notes\n'
        '1,101,A,http://a.com,\n'
        '2,102,B,,"Processing timeout"\n'
        '3,103,C,,\n'
    )
    output_file.write_text(csv_content)
    p_ids, t_ids, links, max_idx, timeouts = load_processed_ids(output_file)
    assert p_ids == {"101", "103"}
    assert t_ids == {"102"}
    assert links == 1
    assert max_idx == 3
    assert timeouts == 1


def test_fetch_page_content_handles_rate_limit(mocker):
    """Tests that fetch_page_content pauses and retries on an HTTP 429 error."""
    mock_session_get = mocker.patch('src.find_wikipedia_links.SESSION.get')
    mock_time_sleep = mocker.patch('time.sleep')

    mock_response_fail = mocker.MagicMock()
    mock_response_fail.status_code = 429
    mock_response_fail.raise_for_status.side_effect = requests.exceptions.RequestException(response=mock_response_fail)
    
    mock_response_success = mocker.MagicMock(text="<html>Success</html>")
    mock_response_success.raise_for_status.return_value = None

    mock_session_get.side_effect = [mock_response_fail, mock_response_success]

    soup = fetch_page_content("https://www.astro.com/test")
    
    assert soup is not None and "Success" in soup.text
    assert mock_session_get.call_count == 2
    mock_time_sleep.assert_any_call(60)


def test_finalize_and_report(tmp_path, capsys, mocker):
    """Tests the different output messages of the finalize_and_report function."""
    output_path = tmp_path / "output.csv"
    fieldnames = ['Index', 'idADB', 'Wikipedia_URL', 'Notes']
    all_lines = ["h", "l1", "l2", "l3"]
    mocker.patch('os._exit')

    # Case 1: Successful completion
    output_path.write_text("Index,idADB,Wikipedia_URL,Notes\n1,101,http://a.com,\n2,102,,\n3,103,,\n")
    finalize_and_report(output_path, fieldnames, all_lines, was_interrupted=False)
    captured = capsys.readouterr()
    assert "SUCCESS: Found 1 links for 4 subjects" in captured.out

    # Case 2: Interrupted run with timeouts
    output_path.write_text("Index,idADB,Wikipedia_URL,Notes\n1,101,,\"Processing timeout\"\n")
    finalize_and_report(output_path, fieldnames, all_lines, was_interrupted=True)
    captured = capsys.readouterr()
    assert "WARNING: Processing interrupted by user" in captured.out
    assert "NOTE: 1 records timed out" in captured.out

    # Case 3: Failure case (processed records but found 0 links)
    output_path.write_text("Index,idADB,Wikipedia_URL,Notes\n1,101,,\n2,102,,\n")
    finalize_and_report(output_path, fieldnames, all_lines, was_interrupted=False)
    captured = capsys.readouterr()
    assert "FAILURE: Processed 2 subjects but found 0 links" in captured.out


@patch('threading.Thread')
@patch('src.find_wikipedia_links.worker_task')
def test_worker_task_with_timeout_handles_hung_worker(mock_worker_task, mock_thread_class, mocker):
    """
    Tests that the timeout wrapper correctly handles a worker task that hangs
    and generates a timeout record.
    """
    # We mock the Thread instance to control its `is_alive` status
    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = True  # Simulate a hung thread
    mock_thread_class.return_value = mock_thread_instance

    # Mock is_research_entry to avoid dependency on the config file
    mocker.patch('src.find_wikipedia_links.is_research_entry', return_value=False)

    line = "1\t101\tDoe\tJohn\tM\t1\t1\t1990\t12:00\t...\t00:00\tCity\tCountry\tLON\tLAT\tAA\tBio\tCat\thttps://a.com"
    
    result = worker_task_with_timeout(line, MagicMock(), 1)

    # Assert that a timeout record was correctly generated
    assert result is not None
    assert result['idADB'] == '101'
    assert result['ADB_Name'] == 'Doe, John'
    assert result['Notes'] == 'Processing timeout'

    # Verify that the thread was started and joined with the correct timeout
    mock_thread_instance.start.assert_called_once()
    mock_thread_instance.join.assert_called_once_with(timeout=60)


def test_load_research_categories_creates_default_file(tmp_path, mocker):
    """
    Tests that load_research_categories creates a default config file if one
    does not exist.
    """
    # Reset the global cache to ensure the function runs from scratch
    find_wikipedia_links.RESEARCH_CATEGORIES_CACHE = None

    # Use a sandbox where the config file is guaranteed not to exist
    sandbox_path = tmp_path / "sandbox"
    config_path = sandbox_path / "data/config/adb_research_categories.json"

    # Mock get_path to point to our empty sandbox. It is now part of the
    # find_wikipedia_links namespace due to the module-level import.
    mocker.patch('src.find_wikipedia_links.get_path', return_value=config_path)

    # The file and its parent directory should not exist before the call
    assert not config_path.parent.exists()

    # Call the function
    categories = load_research_categories()

    # Assert that the file was created and contains the default structure
    assert config_path.exists()
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert "categories" in data
    assert "auto_detected" in data
    assert categories == data


class TestMainWorkflow:
    """Tests the main orchestration logic of the script."""

    @patch('src.find_wikipedia_links.worker_task_with_timeout')
    def test_main_full_run(self, mock_worker, mock_sandbox, capsys):
        """Tests a full, successful run from scratch."""
        mock_worker.return_value = {'idADB': '101', 'Wikipedia_URL': 'http://a.com'}
        
        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--force"]
        with patch("sys.argv", test_args):
            find_wikipedia_links.main()
        
        captured = capsys.readouterr()
        assert "SUCCESS:" in captured.out
        assert mock_worker.call_count == 2

    @patch('src.find_wikipedia_links.worker_task_with_timeout')
    def test_main_resumes_and_retries_timeouts(self, mock_worker, mock_sandbox, capsys):
        """Tests resuming and retrying records that previously timed out."""
        output_path = mock_sandbox / "data/processed/adb_wiki_links.csv"
        # Pre-populate with one success and one timeout
        output_path.write_text(
            'Index,idADB,ADB_Name,Wikipedia_URL,Notes\n'
            '1,101,"Doe, John",http://a.com,\n'
            '2,102,"Smith, Jane",,"Processing timeout"\n'
        )
        mock_worker.return_value = {'idADB': '102', 'Wikipedia_URL': 'http://b.com'}

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args):
            find_wikipedia_links.main()

        # Should only call the worker for the one timed-out record
        assert mock_worker.call_count == 1
        captured = capsys.readouterr()
        assert "Found 1 records that previously timed out. Retrying them now." in captured.out
        assert "SUCCESS:" in captured.out

    def test_main_handles_stale_file(self, mock_sandbox, mocker, capsys):
        """Tests that a stale output file triggers an automatic re-run."""
        input_path = mock_sandbox / "data/sources/adb_raw_export.txt"
        output_path = mock_sandbox / "data/processed/adb_wiki_links.csv"
        output_path.touch()
        
        # Make input newer
        os.utime(input_path, (output_path.stat().st_mtime + 1, output_path.stat().st_mtime + 1))
        
        # Mock the worker and user input to prevent actual execution
        mocker.patch('src.find_wikipedia_links.worker_task_with_timeout', return_value={})
        mocker.patch('builtins.input', side_effect=EOFError)

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args):
            find_wikipedia_links.main()
            
        captured = capsys.readouterr()
        assert "Stale data detected. Automatically re-running" in captured.out


    @patch('src.find_wikipedia_links.search_wikipedia')
    @patch('thefuzz.fuzz.ratio', return_value=40) # Low score
    @patch('src.find_wikipedia_links.fetch_page_content')
    @patch('src.find_wikipedia_links.get_initial_wiki_url_from_adb', return_value="http://some-wiki.com")
    def test_worker_task_rejects_bad_scraped_link(self, mock_get_initial, mock_fetch, mock_fuzz, mock_search, mocker):
        """Tests that a scraped link is rejected if the title mismatch is too high."""
        mocker.patch('src.find_wikipedia_links.is_research_entry', return_value=False)
        
        mock_soup = MagicMock()
        mock_h1 = MagicMock()
        mock_h1.get_text.return_value = "A Completely Different Person"
        mock_soup.find.return_value = mock_h1
        mock_fetch.return_value = mock_soup

        line = "1\t101\tDoe\tJohn\tM\t1\t1\t1990\t12:00\t...\t00:00\tCity\tCountry\tLON\tLAT\tAA\tBio\tCat\thttps://a.com"
        find_wikipedia_links.worker_task(line, MagicMock(), 1)
        
        # Because the link was rejected, it should fall back to a Wikipedia search
        mock_search.assert_called_once()


    @patch('src.find_wikipedia_links.fetch_page_content', return_value=None)
    @patch('src.find_wikipedia_links.get_initial_wiki_url_from_adb')
    def test_worker_task_transforms_research_url(self, mock_get_initial_url, mock_fetch, mocker):
        """Tests that the worker correctly transforms the URL for a research entry."""
        mocker.patch('src.find_wikipedia_links.is_research_entry', return_value=True)
        line = "1\t123\tResearch Event\t\tM\t1\t1\t1999\t12:00\t...\t00:00\t...\t...\t...\t...\tAA\t...\tCat\thttps://www.astro.com/astro-databank/Event"
        
        find_wikipedia_links.worker_task(line, MagicMock(), 1)
        
        # Assert that the URL passed to the scraper was correctly modified
        mock_get_initial_url.assert_called_once_with("https://www.astro.com/astro-databank/Research:Event")


    def test_fetch_page_content_fails_after_retries(self, mocker):
        """Tests that fetch_page_content returns None after all retries fail."""
        mock_session_get = mocker.patch('src.find_wikipedia_links.SESSION.get')
        mocker.patch('time.sleep')  # Mock sleep to avoid long pauses
        
        mock_response_fail = mocker.MagicMock()
        mock_response_fail.status_code = 429
        mock_response_fail.raise_for_status.side_effect = requests.exceptions.RequestException(response=mock_response_fail)
        mock_session_get.side_effect = [mock_response_fail] * 5

        result = fetch_page_content("https://www.astro.com/test")
        
        assert result is None
        assert mock_session_get.call_count == 5


    @patch('src.find_wikipedia_links.finalize_and_report')
    @patch('src.find_wikipedia_links.worker_task_with_timeout')
    def test_main_handles_keyboard_interrupt(self, mock_worker, mock_finalize, mock_sandbox):
        """Tests graceful shutdown on KeyboardInterrupt."""
        # Have the worker raise the interrupt to simulate a user stopping the process.
        mock_worker.side_effect = KeyboardInterrupt

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--quiet"]
        with patch("sys.argv", test_args):
            find_wikipedia_links.main()

        mock_finalize.assert_called_once()
        assert mock_finalize.call_args.kwargs['was_interrupted'] is True

    @patch('src.find_wikipedia_links.finalize_and_report')
    def test_main_handles_user_cancellation(self, mock_finalize, mock_sandbox, capsys):
        """Tests that the script exits gracefully if the user cancels an overwrite."""
        output_path = mock_sandbox / "data/processed/adb_wiki_links.csv"
        output_path.write_text("Index,idADB\n1,101\n2,102\n") # Simulate a complete file
        
        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args), patch("builtins.input", return_value="n"):
            with pytest.raises(SystemExit) as e:
                find_wikipedia_links.main()
            assert e.value.code == 0

        captured = capsys.readouterr()
        assert "Operation cancelled by user" in captured.out
        # It should still call finalize to report on the existing file
        mock_finalize.assert_called_once()



class TestInputFileValidation:
    """Tests the input file validation logic in the main() function."""

    @pytest.fixture
    def mock_main_env(self, mocker):
        """Mocks shared components for main() tests."""
        mocker.patch('sys.exit', side_effect=SystemExit)
        mocker.patch('src.find_wikipedia_links.worker_task_with_timeout')
        mocker.patch('logging.basicConfig') # Prevent Tqdm handler from overriding caplog
        return

    @pytest.mark.parametrize("case_name, content, expected_error_msg", [
        ("empty file", "", "Input file is empty"),
        ("header only", "h1\th2\th3\th4\th5\th6\th7\th8\th9\th10\th11\th12\th13\th14\th15\th16\th17\th18\th19", "Input file has insufficient data"),
        ("malformed header", "h1\th2\ndummy_data_row", "Input file has malformed header"),
        ("no valid rows", "h1\th2\th3\th4\th5\th6\th7\th8\th9\th10\th11\th12\th13\th14\th15\th16\th17\th18\th19\nd1\td2", "No valid data rows found"),
    ])
    def test_main_handles_bad_input_files(self, case_name, content, expected_error_msg, mock_main_env, mock_sandbox, caplog):
        """Tests that the script exits gracefully with various malformed input files."""
        input_path = mock_sandbox / "data/sources/adb_raw_export.txt"
        input_path.write_text(content)

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit):
                find_wikipedia_links.main()

        assert expected_error_msg in caplog.text

# === End of tests/data_preparation/test_find_wikipedia_links.py ===

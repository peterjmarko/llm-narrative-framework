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
# Filename: tests/data_preparation/test_validate_wikipedia_pages.py

"""
Unit tests for the Wikipedia page validation script (src/validate_wikipedia_pages.py).

This suite validates the critical offline logic of the script, such as name
matching, robust death date detection from various HTML patterns, and the
handling of disambiguation pages.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup
from tqdm import tqdm

# Import the entire module so we can patch objects within it
from src import validate_wikipedia_pages
from src.validate_wikipedia_pages import (
    fetch_page_content,
    find_matching_disambiguation_link,
    follow_all_redirects,
    generate_summary_report,
    is_disambiguation_page,
    load_and_filter_input,
    process_wikipedia_page,
    validate_death_date,
    validate_name,
    worker_task,
    worker_task_with_timeout,
)


@pytest.mark.parametrize("adb_name, wp_title_html, expected_wp_name, expected_score_range", [
    # Case 1: Perfect match
    ("Da Vinci, Leonardo", "<h1>Leonardo da Vinci</h1>", "Leonardo da Vinci", (99, 100)),
    # Case 2: Good match with middle initial
    ("Bush, George W.", "<h1>George W. Bush</h1>", "George W. Bush", (99, 100)),
    # Case 3: ADB name has year, WP name does not
    ("Nixon, Richard (1913)", "<h1>Richard Nixon</h1>", "Richard Nixon", (99, 100)),
    # Case 4: WP name has disambiguation, ADB does not
    ("Smith, John", "<h1>John Smith (explorer)</h1>", "John Smith (explorer)", (99, 100)),
    # Case 5: Poor match
    ("Smith, John", "<h1>Jane Doe</h1>", "Jane Doe", (0, 50)),
])
def test_validate_name(adb_name, wp_title_html, expected_wp_name, expected_score_range):
    """
    Tests the name validation logic, including name cleaning and fuzzy matching.
    """
    # Add the standard h1 id that the script looks for
    soup = BeautifulSoup(wp_title_html.replace("<h1>", "<h1 id='firstHeading'>"), 'html.parser')
    
    wp_name, name_score = validate_name(adb_name, soup)
    
    assert wp_name == expected_wp_name
    assert expected_score_range[0] <= name_score <= expected_score_range[1]


# --- Tests for validate_death_date ---

@pytest.mark.parametrize("html_snippet, expected_result", [
    # --- Positive Cases (Should return True) ---
    # Strategy 1: Categories
    ('<div id="mw-normal-catlinks"><a>2001 deaths</a></div>', True),
    ('<div id="mw-normal-catlinks"><a>Category:People who died in prison</a></div>', True),
    ('<div id="mw-normal-catlinks"><a>Category:1900 births</a></div>', True),
    # Strategy 2: Infobox
    ('<table class="infobox"><tr><th>Died</th><td>2020</td></tr></table>', True),
    # This case now includes a year, making it a valid positive test
    ('<table class="infobox"><tr><td><b>Born</b></td><td>...</td></tr><tr><td><b>Deceased</b></td><td>1 Jan 2021</td></tr></table>', True),
    # Strategy 3: First paragraph date range
    ('<p><b>John Doe</b> (1 January 1900 – 1 January 2000) was a person.</p>', True),
    ('<p>... was an artist (b. 1920, d. 1990) ...</p>', True),
    ('<p>... died on January 1, 2000 ...</p>', True),
    # Strategy 6: Section Headers
    ('<h2>Death</h2>', True),
    ('<h3>Final years and death</h3>', True),
    # Strategy 7: Wikipedia Templates
    ('<span class="death-date">2005-11-25</span>', True),

    # --- Negative Cases (Should return False) ---
    # Living person category
    ('<div id="mw-normal-catlinks"><a>Living people</a></div>', False),
    # No death indicators
    ('<html><body><h1>A Living Person</h1><p>This person is still alive.</p></body></html>', False),
    # Infobox with only a birth date
    ('<table class="infobox"><tr><th>Born</th><td>1990</td></tr></table>', False),
])
def test_validate_death_date(html_snippet, expected_result):
    """
    Tests the death date validation logic against various HTML snippets.
    """
    soup = BeautifulSoup(html_snippet, 'html.parser')
    assert validate_death_date(soup) == expected_result


# --- Tests for Disambiguation Helpers ---

@pytest.mark.parametrize("html_content, expected", [
    # Positive cases
    ('<div><div id="disambiguation"></div></div>', True),
    ('<div><p class="disambiguation">Content</p></div>', True),
    ('<body>This page may refer to:</body>', True),
    # Negative case
    ('<body>A normal article page.</body>', False),
])
def test_is_disambiguation_page(html_content, expected):
    """Tests the detection of disambiguation pages."""
    soup = BeautifulSoup(html_content, 'html.parser')
    assert is_disambiguation_page(soup) == expected


def test_find_matching_disambiguation_link():
    """Tests finding the correct link on a disambiguation page using birth year."""
    html_content = """
    <ul>
      <li><a href="/wiki/Person_A">Person A</a>, born 1950</li>
      <li><a href="/wiki/Person_B">Person B</a> (1960–2010)</li>
    </ul>
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Should find a match
    assert find_matching_disambiguation_link(soup, "1950") == "https://en.wikipedia.org/wiki/Person_A"
    
    # Should return None for a year not present
    assert find_matching_disambiguation_link(soup, "1999") is None


# --- Tests for process_wikipedia_page Orchestrator ---

def test_process_wikipedia_page_success(mocker):
    """Tests a successful validation path for a standard page."""
    mock_pbar = MagicMock(spec=tqdm)
    mock_soup = BeautifulSoup("<html></html>", 'html.parser')
    mocker.patch('src.validate_wikipedia_pages.follow_all_redirects', return_value=("https://final.url/page", mock_soup))
    mocker.patch('src.validate_wikipedia_pages.is_disambiguation_page', return_value=False)
    mocker.patch('src.validate_wikipedia_pages.validate_name', return_value=("WP Name", 95))
    mocker.patch('src.validate_wikipedia_pages.validate_death_date', return_value=True)

    result = process_wikipedia_page("http://start.url", "ADB Name", "1990", mock_pbar)

    assert result['status'] == 'OK'
    assert result['final_url'] == 'https://final.url/page'
    assert result['name_score'] == 95
    assert result['death_date_found'] is True


def test_process_wikipedia_page_fetch_failure(mocker):
    """Tests the case where the page fetch fails."""
    mock_pbar = MagicMock(spec=tqdm)
    mocker.patch('src.validate_wikipedia_pages.follow_all_redirects', return_value=("http://fail.url", None))

    result = process_wikipedia_page("http://fail.url", "ADB Name", "1990", mock_pbar)
    assert result['status'] == 'ERROR'
    assert result['notes'] == 'Failed to fetch Wikipedia page'


def test_process_wikipedia_page_disambiguation_failure(mocker):
    """Tests the case where a disambiguation page cannot be resolved."""
    mock_pbar = MagicMock(spec=tqdm)
    mock_soup = BeautifulSoup("<html></html>", 'html.parser')
    mocker.patch('src.validate_wikipedia_pages.follow_all_redirects', return_value=("http://disambig.url", mock_soup))
    mocker.patch('src.validate_wikipedia_pages.is_disambiguation_page', return_value=True)
    mocker.patch('src.validate_wikipedia_pages.find_matching_disambiguation_link', return_value=None)

    result = process_wikipedia_page("http://start.url", "ADB Name", "1990", mock_pbar)
    assert result['status'] == 'FAIL'
    assert 'Disambiguation page, no link' in result['notes']


# --- Tests for worker_task ---

@pytest.mark.parametrize("input_row, mock_validation, expected_status, expected_notes", [
    # Case 1: Successful validation
    (
        {'Wikipedia_URL': 'http://a.com', 'ADB_Name': 'Test A', 'BirthYear': '1900', 'Entry_Type': 'Person'},
        {'status': 'OK', 'final_url': 'http://a.com', 'wp_name': 'Test A', 'name_score': 95, 'death_date_found': True},
        'OK', ''
    ),
    # Case 2: Name mismatch failure
    (
        {'Wikipedia_URL': 'http://b.com', 'ADB_Name': 'Test B', 'BirthYear': '1901', 'Entry_Type': 'Person'},
        {'status': 'OK', 'final_url': 'http://b.com', 'wp_name': 'Test Z', 'name_score': 50, 'death_date_found': True},
        'FAIL', 'Name mismatch (Score: 50)'
    ),
    # Case 3: Death date not found failure
    (
        {'Wikipedia_URL': 'http://c.com', 'ADB_Name': 'Test C', 'BirthYear': '1902', 'Entry_Type': 'Person'},
        {'status': 'OK', 'final_url': 'http://c.com', 'wp_name': 'Test C', 'name_score': 100, 'death_date_found': False},
        'FAIL', 'Death date not found'
    ),
    # Case 4: No URL to begin with
    (
        {'Wikipedia_URL': '', 'ADB_Name': 'Test D', 'BirthYear': '1903', 'Entry_Type': 'Person', 'Notes': ''},
        None, 'FAIL', 'No Wikipedia URL found'
    ),
    # Case 5: Research entry (should be marked as VALID)
    (
        {'Wikipedia_URL': '', 'ADB_Name': 'Research X', 'BirthYear': '1904', 'Entry_Type': 'Research', 'Notes': ''},
        None, 'VALID', 'Research entry - Wikipedia not expected'
    ),
    # Case 6: Pre-existing notes from link-finder (should be passed through)
    (
        {'Wikipedia_URL': '', 'ADB_Name': 'Test E', 'BirthYear': '1905', 'Entry_Type': 'Person', 'Notes': 'Previous error'},
        None, 'FAIL', 'Previous error'
    ),
])
def test_worker_task_logic(mocker, input_row, mock_validation, expected_status, expected_notes):
    """Tests the decision-making logic of the main worker task."""
    mock_pbar = MagicMock(spec=tqdm)
    mock_process_page = mocker.patch('src.validate_wikipedia_pages.process_wikipedia_page', return_value=mock_validation)
    
    result = worker_task(input_row, mock_pbar, 1)
    
    assert result['Status'] == expected_status
    assert result['Notes'] == expected_notes
    
    # Ensure process_wikipedia_page was only called when it was supposed to be
    if input_row.get('Wikipedia_URL') and not input_row.get('Notes'):
        mock_process_page.assert_called_once()
    else:
        mock_process_page.assert_not_called()


def test_load_and_filter_input(tmp_path):
    """Tests the logic for loading input data and filtering out processed records."""
    input_file = tmp_path / "input.csv"
    report_file = tmp_path / "report.csv"

    # Create a dummy input file
    input_content = (
        'idADB,Name\n'
        '101,A\n'
        '102,B\n'
        '103,C\n'
        '104,D\n'
    )
    input_file.write_text(input_content)

    # Case 1: No existing report, should process all records
    to_process, timeouts, max_idx, valid, processed, total = load_and_filter_input(input_file, report_file, force=False)
    assert len(to_process) == 4
    assert [r['idADB'] for r in to_process] == ['101', '102', '103', '104']
    assert timeouts == set()
    assert valid == 0
    assert processed == 0
    assert total == 4

    # Case 2: Existing report with processed and timed-out records
    report_content = (
        'Index,idADB,Status,Notes\n'
        '1,101,OK,\n'
        '2,103,FAIL,Processing timeout\n'
    )
    report_file.write_text(report_content)
    
    to_process, timeouts, max_idx, valid, processed, total = load_and_filter_input(input_file, report_file, force=False)
    assert len(to_process) == 3 # 102 and 104 are new, 103 timed out
    assert {r['idADB'] for r in to_process} == {'102', '103', '104'}
    assert timeouts == {'103'}
    assert valid == 1
    assert processed == 1
    assert max_idx == 2

    # Case 3: --force flag should ignore the report and process all records
    to_process, _, _, _, _, _ = load_and_filter_input(input_file, report_file, force=True)
    assert len(to_process) == 4


def test_follow_all_redirects_handles_canonical_link(mocker):
    """Tests that the redirect follower correctly handles canonical links."""
    start_url = "http://example.com/pageA"
    canonical_url = "http://example.com/pageB"

    # Soup for the first page with a canonical link
    soup_a_html = f'<html><head><link rel="canonical" href="{canonical_url}" /></head></html>'
    soup_a = BeautifulSoup(soup_a_html, 'html.parser')

    # Soup for the final canonical page
    soup_b_html = '<html><head></head><body>Final Page</body></html>'
    soup_b = BeautifulSoup(soup_b_html, 'html.parser')

    # Mock fetch_page_content to return the two different soups
    mock_fetch = mocker.patch('src.validate_wikipedia_pages.fetch_page_content', side_effect=[soup_a, soup_b])

    final_url, final_soup = follow_all_redirects(start_url)

    assert final_url == canonical_url
    assert "Final Page" in final_soup.get_text()
    assert mock_fetch.call_count == 2


@patch('threading.Thread')
@patch('src.validate_wikipedia_pages.worker_task')
def test_worker_task_with_timeout_handles_hung_worker(mock_worker_task, mock_thread_class, mocker):
    """
    Tests that the timeout wrapper correctly handles a worker task that hangs
    and generates a timeout record.
    """
    mock_thread_instance = MagicMock()
    mock_thread_instance.is_alive.return_value = True  # Simulate a hung thread
    mock_thread_class.return_value = mock_thread_instance

    row = {'idADB': '101', 'ADB_Name': 'Hung Worker'}

    result = worker_task_with_timeout(row, MagicMock(), 1)

    assert result['Status'] == 'FAIL'
    assert result['Notes'] == 'Processing timeout'
    mock_thread_instance.join.assert_called_once_with(timeout=60)


def test_fetch_page_content_handles_meta_refresh(mocker):
    """Tests that fetch_page_content correctly follows meta-refresh redirects."""
    start_url = "http://example.com/redirect"
    final_url = "http://example.com/final"

    # HTML for the redirect page and the final page
    redirect_html = f'<html><head><meta http-equiv="refresh" content="0; url={final_url}"></head></html>'
    final_html = '<html><body>Final Destination</body></html>'

    # Mock the session's get method to return different responses
    mock_response_redirect = MagicMock()
    mock_response_redirect.raise_for_status.return_value = None
    mock_response_redirect.text = redirect_html
    mock_response_redirect.url = start_url

    mock_response_final = MagicMock()
    mock_response_final.raise_for_status.return_value = None
    mock_response_final.text = final_html
    mock_response_final.url = final_url

    mock_session_get = mocker.patch('src.validate_wikipedia_pages.SESSION.get', side_effect=[mock_response_redirect, mock_response_final])

    soup = fetch_page_content(start_url)

    assert "Final Destination" in soup.get_text()
    assert mock_session_get.call_count == 2


class TestMainWorkflow:
    """Tests the main orchestration logic of the script."""

    @pytest.fixture
    def mock_sandbox(self, tmp_path: Path):
        """Creates a comprehensive sandbox for testing the main function."""
        # Create directories
        (tmp_path / "data" / "processed").mkdir(parents=True)
        (tmp_path / "data" / "reports").mkdir(parents=True)

        # Create input file
        input_path = tmp_path / "data/processed/adb_wiki_links.csv"
        input_content = (
            "idADB,ADB_Name,BirthYear,Entry_Type,Wikipedia_URL,Notes\n"
            "101,Doe, John,1990,Person,http://a.com,\n"
            "102,Smith, Jane,1991,Person,http://b.com,\n"
        )
        input_path.write_text(input_content)
        return tmp_path

    @patch('src.validate_wikipedia_pages.generate_summary_report')
    @patch('src.validate_wikipedia_pages.worker_task_with_timeout')
    def test_main_full_run(self, mock_worker, mock_summary, mock_sandbox, capsys):
        """Tests a full, successful run from scratch."""
        mock_worker.return_value = {'Status': 'OK', 'idADB': '101'}

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--force"]
        with patch("sys.argv", test_args):
            validate_wikipedia_pages.main()

        captured = capsys.readouterr()
        assert "SUCCESS:" in captured.out
        assert mock_worker.call_count == 2

    def test_main_report_only(self, mock_sandbox, mocker, capsys):
        """Tests that the --report-only flag works correctly."""
        # Mock sys.exit to raise an exception that pytest can catch.
        def mock_exit(code=0):
            raise SystemExit(code)

        mocker.patch('sys.exit', side_effect=mock_exit)
        mock_generate_summary = mocker.patch('src.validate_wikipedia_pages.generate_summary_report')

        # Create a dummy report file for the function to read
        (mock_sandbox / "data/reports/adb_validation_report.csv").touch()

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--report-only"]
        with patch("sys.argv", test_args):
            # The script should exit gracefully after generating the report
            with pytest.raises(SystemExit) as e:
                validate_wikipedia_pages.main()
            assert e.value.code == 0

        mock_generate_summary.assert_called_once()
        captured = capsys.readouterr()
        assert "Generating Summary Report Only" in captured.out

    @patch('src.validate_wikipedia_pages.finalize_and_report')
    @patch('src.validate_wikipedia_pages.worker_task_with_timeout')
    def test_main_handles_keyboard_interrupt(self, mock_worker, mock_finalize, mock_sandbox):
        """Tests graceful shutdown on KeyboardInterrupt."""
        mock_worker.side_effect = KeyboardInterrupt

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--quiet"]
        with patch("sys.argv", test_args):
            validate_wikipedia_pages.main()

        mock_finalize.assert_called_once()
        # was_interrupted is the 4th positional argument
        assert mock_finalize.call_args[0][3] is True

    def test_main_handles_stale_report(self, mock_sandbox, mocker):
        """Tests that a stale report file triggers an automatic re-run."""
        input_path = mock_sandbox / "data/processed/adb_wiki_links.csv"
        report_path = mock_sandbox / "data/reports/adb_validation_report.csv"
        report_path.touch()

        # Make the input file newer than the report
        os.utime(input_path, (report_path.stat().st_mtime + 1, report_path.stat().st_mtime + 1))

        mock_backup = mocker.patch('src.validate_wikipedia_pages.backup_and_remove')
        mocker.patch('src.validate_wikipedia_pages.worker_task_with_timeout')
        mocker.patch('src.validate_wikipedia_pages.generate_summary_report')

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args):
            validate_wikipedia_pages.main()

        # The backup function is a reliable indicator of a forced re-run
        mock_backup.assert_called_once_with(report_path)

    def test_main_exits_if_input_not_found(self, mock_sandbox, mocker, caplog):
        """Tests that the script exits gracefully if the input file is missing."""
        input_path = mock_sandbox / "data/processed/adb_wiki_links.csv"
        input_path.unlink()  # Ensure the file does not exist

        mocker.patch('sys.exit', side_effect=SystemExit)
        mocker.patch('logging.basicConfig') # Prevent Tqdm handler from overriding caplog

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit):
                validate_wikipedia_pages.main()

        assert "Input file not found" in caplog.text


class TestSummaryReport:
    """Tests the summary report generation logic."""

    @pytest.fixture
    def mock_report_csv(self, tmp_path: Path):
        """Creates a mock validation report CSV with diverse data."""
        report_dir = tmp_path / "data" / "reports"
        report_dir.mkdir(parents=True)
        report_path = report_dir / "adb_validation_report.csv"

        report_content = (
            "Index,idADB,Entry_Type,Status,Notes\n"
            "1,101,Person,OK,\n"
            "2,102,Research,VALID,\n"
            "3,103,Person,FAIL,Processing timeout\n"
            "4,104,Person,FAIL,Non-English URL with no fallback\n"
            "5,105,Person,FAIL,No Wikipedia URL found\n"
            "6,106,Person,FAIL,Failed to fetch Wikipedia page\n"
            "7,107,Person,FAIL,Disambiguation page, no link found\n"
            "8,108,Person,FAIL,Name mismatch (Score: 80)\n"
            "9,109,Person,FAIL,Death date not found\n"
            "10,110,Person,FAIL,Some other error\n"
        )
        report_path.write_text(report_content)
        return report_path

    def test_generate_summary_report_full(self, mock_report_csv, capsys, mocker):
        """Tests that the summary report is generated correctly with varied data."""
        # Mock PROJECT_ROOT from the config_loader module where it's imported
        mocker.patch('src.config_loader.PROJECT_ROOT', mock_report_csv.parents[2])

        generate_summary_report(mock_report_csv)

        summary_path = mock_report_csv.with_name("adb_validation_summary.txt")
        assert summary_path.exists()

        summary_content = summary_path.read_text()

        # Check overall stats
        assert "Total Records in Report:                     10" in summary_content
        assert "Valid Records:                                2" in summary_content
        assert "Failed Records:                               8" in summary_content

        # Check specific failure breakdown lines
        assert "1. No Wikipedia Link Found:                   1" in summary_content
        assert "2. Could Not Fetch Page:                      1" in summary_content
        assert "5. Name Mismatch:                             1" in summary_content
        assert "6. Death Date Not Found:                      1" in summary_content
        assert "7. Processing Timeout:                        1" in summary_content
        assert "8. Other Errors:                              1" in summary_content

        # Check console output as well
        captured = capsys.readouterr()
        assert "Astro-Databank Validation Summary" in captured.out
        assert "Total Records in Report:                     10" in captured.out

# === End of tests/data_preparation/test_validate_wikipedia_pages.py ===

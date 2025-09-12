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
# Filename: tests/data_preparation/test_fetch_adb_data.py

"""
Unit tests for the Astro-Databank fetching script (src/fetch_adb_data.py).

This test suite validates the offline data transformation logic and uses mocks
to verify the session handling and network interaction components of the script.
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from src import fetch_adb_data
from src.fetch_adb_data import (
    convert_hours_to_hhmm,
    fetch_all_data,
    login_to_adb,
    parse_results_from_json,
    parse_tz_code,
    scrape_search_page_data,
)

# --- Mock Data Constants ---
MOCK_HTML_SEARCH_PAGE = """
<html>
    <script>var stat = { "uid": "12345", "token": "abcde" };</script>
    <script src="/adb/categories.min.js?v=1"></script>
</html>
"""

MOCK_JS_CATEGORIES = """
var categories = [
    {"code_id": 100, "title": "Death", "children": [{"code_id": 101, "title": "Accident"}]},
    {"code_id": 200, "title": "Notable", "children": [{"code_id": 201, "title": "Top 5% of Profession"}]}
];
"""

MOCK_API_PAGE_1 = {
    "len": [{"cnt": 2}],
    "data": [{"recno": 2, "lnho": 202, "sbli": "B,,M,1,1,1990", "spli": "B", "srra": "A", "sbio": "B", "ctgs": ""}]
}

MOCK_API_PAGE_2 = {
    "len": [{"cnt": 2}],
    "data": [{"recno": 1, "lnho": 101, "sbli": "A,,M,1,1,1990", "spli": "A", "srra": "A", "sbio": "A", "ctgs": ""}]
}

# --- Tests for Helper Functions ---

@pytest.mark.parametrize("decimal_hours, expected_str", [
    (5.5, "05:30"), (-5.5, "-05:30"), (0.0, "00:00")
])
def test_convert_hours_to_hhmm_valid(decimal_hours, expected_str):
    assert convert_hours_to_hhmm(decimal_hours) == expected_str

@pytest.mark.parametrize("tz_code, expected_abbr, expected_offset", [
    ("h5w30", "...", "05:30"), ("m77w8", "LMT", "05:09")
])
def test_parse_tz_code_valid(tz_code, expected_abbr, expected_offset):
    zone_abbr, zone_time_offset = parse_tz_code(tz_code)
    assert zone_abbr == expected_abbr
    assert zone_time_offset == expected_offset

@pytest.mark.parametrize("invalid_code", ["", "x5w", "h5", "m10q"])
def test_parse_tz_code_invalid(invalid_code):
    with pytest.raises(ValueError):
        parse_tz_code(invalid_code)

def test_parse_results_from_json_valid_data():
    mock_json = {"len": [{"cnt": 1}], "data": [{"recno": 123, "lnho": 456, "sbli": "Smith,John", "spli": "NY,USA", "srra": "A", "sbio": "Bio", "ctgs": "10"}]}
    results, total_hits = parse_results_from_json(mock_json, {"10": "Cat A"})
    assert total_hits == 1
    assert results[0][0] == '123'
    assert "Cat A" in results[0]

def test_parse_results_from_json_empty_and_error_handling():
    results, total_hits = parse_results_from_json({"data": [], "len": [{"cnt": 0}]}, {})
    assert total_hits == 0 and results == []

    mock_json = {"len": [{"cnt": 1}], "data": [{"recno": 1, "lnho": 2, "sbli": "short"}]}
    results, total_hits = parse_results_from_json(mock_json, {})
    assert total_hits == 1 and len(results) == 1 and results[0][2] == 'short'

# --- Tests for Network Interaction Logic ---

def test_login_to_adb_success():
    mock_session = MagicMock()
    mock_response = MagicMock(text="act=disconnect")
    mock_session.get.return_value = mock_response
    assert login_to_adb(mock_session, "user", "pass") is True

def test_login_to_adb_failure():
    mock_session = MagicMock()
    mock_response = MagicMock(text="not logged in")
    mock_session.get.return_value = mock_response
    with pytest.raises(SystemExit):
        login_to_adb(mock_session, "user", "pass")

def test_scrape_search_page_data(tmp_path):
    mock_session = MagicMock()
    
    def mock_get(url, **kwargs):
        if "categories.min.js" in url:
            return SimpleNamespace(text=MOCK_JS_CATEGORIES, raise_for_status=lambda: None)
        return SimpleNamespace(text=MOCK_HTML_SEARCH_PAGE, raise_for_status=lambda: None)
        
    mock_session.get.side_effect = mock_get
    
    with patch.dict(os.environ, {"PROJECT_SANDBOX_PATH": str(tmp_path)}):
        stat_data, category_ids, category_map = scrape_search_page_data(mock_session)

    assert stat_data == {"uid": "12345", "token": "abcde"}
    assert category_ids == [100, 101, 201]
    assert category_map["101"] == "Accident"
    assert (tmp_path / "data/foundational_assets/adb_category_map.csv").exists()

def test_fetch_all_data_paginates_and_saves(tmp_path):
    mock_session = MagicMock()
    mock_session.post.return_value = SimpleNamespace(json=lambda: MOCK_API_PAGE_1, raise_for_status=lambda: None)
    mock_session.get.return_value = SimpleNamespace(json=lambda: MOCK_API_PAGE_2, raise_for_status=lambda: None)
    
    output_path = tmp_path / "output.txt"
    fetch_all_data(mock_session, output_path, {}, [], {}, None, None)

    assert mock_session.post.call_count == 1
    assert mock_session.get.call_count == 1
    
    content = output_path.read_text()
    assert "101" in content and "202" in content
    # Verify sorting: record 1 should appear before record 2
    assert content.find("101") < content.find("202")

def test_fetch_all_data_keyboard_interrupt(tmp_path):
    mock_session = MagicMock()
    mock_session.post.side_effect = KeyboardInterrupt
    
    output_path = tmp_path / "output.txt"
    fetch_all_data(mock_session, output_path, {}, [], {}, None, None)
    assert not output_path.exists() # Should exit before saving

# --- Tests for Main Orchestrator ---

@pytest.fixture
def mock_sandbox_for_main(tmp_path: Path) -> Path:
    (tmp_path / "data" / "sources").mkdir(parents=True)
    with patch.dict(os.environ, {"PROJECT_SANDBOX_PATH": str(tmp_path), "ADB_USERNAME": "user", "ADB_PASSWORD": "pass"}):
        yield tmp_path

@patch('src.fetch_adb_data.login_to_adb')
def test_main_handles_user_cancellation(mock_login, mock_sandbox_for_main, capsys, mocker):
    """
    Tests that the script exits gracefully if the user cancels an overwrite and
    does not proceed to the login stage.
    """
    output_path = mock_sandbox_for_main / "data/sources/adb_raw_export.txt"
    output_path.touch()
    
    # Mock sys.exit to raise an exception that we can catch.
    mocker.patch('sys.exit', side_effect=SystemExit)

    test_args = ["script.py", "--sandbox-path", str(mock_sandbox_for_main)]
    with patch("sys.argv", test_args), patch("builtins.input", return_value="n"):
        with pytest.raises(SystemExit):
            fetch_adb_data.main()

    # Assert that the login function was never called because the script exited early.
    mock_login.assert_not_called()

    captured = capsys.readouterr()
    assert "Operation cancelled by user" in captured.out

def test_main_handles_missing_credentials(mock_sandbox_for_main, monkeypatch):
    monkeypatch.delenv("ADB_USERNAME", raising=False)
    
    # Pre-create the output file to trigger the interactive prompt
    output_path = mock_sandbox_for_main / "data/sources/adb_raw_export.txt"
    output_path.touch()

    test_args = ["script.py", "--sandbox-path", str(mock_sandbox_for_main)]
    # Mock 'y' to get past the overwrite prompt
    with patch("sys.argv", test_args), patch("builtins.input", return_value="y"):
        with pytest.raises(SystemExit) as e:
            fetch_adb_data.main()
        assert e.value.code == 1

# === End of tests/data_preparation/test_fetch_adb_data.py ===

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
# Filename: tests/data_preparation/test_fetch_adb_data.py

"""
Unit tests for the Astro-Databank fetching script (src/fetch_adb_data.py).

This test suite validates the offline data transformation logic and uses mocks
to verify the session handling and network interaction components of the script.
"""

from unittest.mock import MagicMock

import pytest
from src.fetch_adb_data import (
    convert_hours_to_hhmm,
    login_to_adb,
    parse_results_from_json,
    parse_tz_code,
)


# --- Tests for convert_hours_to_hhmm ---

@pytest.mark.parametrize("decimal_hours, expected_str", [
    (5.0, "05:00"),
    (-5.0, "-05:00"),
    (5.5, "05:30"),
    (-5.5, "-05:30"),
    (0.0, "00:00"),
    (8.25, "08:15"),
    (-8.25, "-08:15"),
    (12.99, "12:59"), # 12h 59.4m -> 12:59
    (12.995, "13:00"), # 12h 59.7m -> 13:00 (Test rounding up)
])
def test_convert_hours_to_hhmm_valid(decimal_hours, expected_str):
    """Test conversion of decimal hours to HH:MM format."""
    assert convert_hours_to_hhmm(decimal_hours) == expected_str


# --- Tests for parse_tz_code ---

@pytest.mark.parametrize("tz_code, expected_abbr, expected_offset", [
    # Standard 'h' type cases
    ("h5w", "...", "05:00"),      # Standard west
    ("h5e", "...", "-05:00"),     # Standard east
    ("h5w30", "...", "05:30"),   # With minutes
    ("h10e30", "...", "-10:30"),  # Double digit hours
    ("h0w", "...", "00:00"),      # UTC case, no negative zero
    ("h0e", "...", "00:00"),      # UTC case
    # 'm' type (LMT) cases
    ("m77w8", "LMT", "05:09"),    # West longitude with minutes (5h 8.53m -> 5:09)
    ("m15e", "LMT", "-01:00"),    # East longitude, whole number
    ("m0w", "LMT", "00:00"),      # LMT at Greenwich
    ("m122e26", "LMT", "-08:10"), # Complex conversion (-8h 9.73m -> -8:10)
])
def test_parse_tz_code_valid(tz_code, expected_abbr, expected_offset):
    """Test parsing of valid TZC strings."""
    zone_abbr, zone_time_offset = parse_tz_code(tz_code)
    assert zone_abbr == expected_abbr
    assert zone_time_offset == expected_offset

@pytest.mark.parametrize("invalid_code", [
    "",
    "x5w",
    "h5",
    "h5z30",
    "m10q",
    "invalid",
])
def test_parse_tz_code_invalid(invalid_code):
    """Test that invalid TZC strings raise a ValueError."""
    with pytest.raises(ValueError):
        parse_tz_code(invalid_code)


# --- Tests for parse_results_from_json ---

def test_parse_results_from_json_valid_data():
    """Test parsing a valid JSON response with multiple data entries."""
    mock_json_data = {
        "len": [{"cnt": 2}],
        "data": [
            {
                "recno": 123, "lnho": 456,
                "sbli": "Smith\tLast,John\tFirst,M,15,4,1960,12:30,h5w",
                "spli": "New York\tCity,USA,74W0,40N43",
                "srra": "AA", "sbio": "A sample bio.", "ctgs": "10,20"
            },
            {
                "recno": 789, "lnho": 101,
                "sbli": "Doe,,F,1,1,1990,09:00,m15e", # Note the single-part name 'Doe'
                "spli": "Paris,France,2E20,48N51",
                "srra": "A", "sbio": "Another bio.", "ctgs": "30"
            }
        ]
    }
    mock_category_map = {"10": "Category A", "20": "Category B", "30": "Category C"}
    
    results, total_hits = parse_results_from_json(mock_json_data, mock_category_map)
    
    assert total_hits == 2
    assert len(results) == 2
    
    # Check first record
    assert results[0] == [
        '123', 456, 'Smith Last', 'John First', 'M', '15', '4', '1960', '12:30',
        '...', '05:00', 'New York City', 'USA', '74W0', '40N43', 'AA',
        'A sample bio.', 'Category A, Category B',
        'https://www.astro.com/astro-databank/Smith Last,_John_First'
    ]
    
    # Check second record (single name slug)
    assert results[1] == [
        '789', 101, 'Doe', '', 'F', '1', '1', '1990', '09:00',
        'LMT', '-01:00', 'Paris', 'France', '2E20', '48N51', 'A',
        'Another bio.', 'Category C',
        'https://www.astro.com/astro-databank/Doe'
    ]

def test_parse_results_from_json_empty_and_error_handling():
    """Test parsing with empty data, missing keys, and lenient error handling."""
    mock_category_map = {}

    # Test empty data list
    results, total_hits = parse_results_from_json({"data": [], "len": [{"cnt": 0}]}, mock_category_map)
    assert total_hits == 0
    assert results == []

    # Test missing 'data' key
    results, total_hits = parse_results_from_json({"len": [{"cnt": 0}]}, mock_category_map)
    assert total_hits == 0
    assert results == []

    # Test record with malformed 'sbli' data.
    # The production code is lenient and processes the record with default values
    # rather than skipping it. This test verifies that behavior.
    mock_json_data = {
        "len": [{"cnt": 1}],
        "data": [
            {"recno": 1, "lnho": 2, "sbli": "short", "spli": "", "srra": "C", "sbio": "", "ctgs": ""}
        ]
    }
    results, total_hits = parse_results_from_json(mock_json_data, mock_category_map)
    assert total_hits == 1
    assert len(results) == 1 # The record should be processed, not skipped.
    assert results[0] == [
        '1', 2, 'short', '', 'U', '', '', '', '', '...', '00:00', 
        '', '', '', '', 'C', '', '', 'https://www.astro.com/astro-databank/short'
    ]


# --- Tests for login_to_adb ---

def test_login_to_adb_success():
    """Test a successful login sequence."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "act=disconnect" # The success indicator
    mock_session.get.return_value = mock_response
    mock_session.post.return_value = MagicMock()

    result = login_to_adb(mock_session, "user", "pass")
    assert result is True
    assert mock_session.post.call_count == 1
    assert mock_session.get.call_count == 2 # Initial GET and verification GET

def test_login_to_adb_failure():
    """Test a failed login due to incorrect response text."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "You are not logged in." # The failure indicator
    mock_session.get.return_value = mock_response
    mock_session.post.return_value = MagicMock()

    with pytest.raises(SystemExit):
        login_to_adb(mock_session, "user", "pass")

# === End of tests/data_preparation/test_fetch_adb_data.py ===

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
# Filename: tests/test_neutralize_delineations.py

"""
Unit tests for the delineation neutralization script (src/neutralize_delineations.py).

This test suite validates the script's critical offline logic, focusing on:
1.  Parsing the unique, esoteric format of the raw Solar Fire delineation library.
2.  Correctly grouping the parsed delineations into distinct, logical tasks for
    the LLM worker.
"""

from pathlib import Path
import pytest
from src.neutralize_delineations import parse_llm_response, group_delineations


@pytest.fixture
def mock_delineation_file(tmp_path: Path) -> Path:
    """Creates a temporary delineation library file for testing."""
    delineation_path = tmp_path / "delineations.txt"
    content = """
; This is a comment and should be ignored.
*Title
Sample Delineations

*Sun in Aries
You are a pioneer.
|This is a continuation line.

*Quadrant 1 Strong
You are independent.
"""
    delineation_path.write_text(content)
    return delineation_path


def test_parse_llm_response(mock_delineation_file):
    """
    Tests the parsing of the raw delineation file format, including comments,
    multi-line entries, and line continuations.
    """
    delineations = parse_llm_response(mock_delineation_file)
    
    assert "Title" in delineations
    assert delineations["Title"] == "Sample Delineations"
    
    assert "Sun in Aries" in delineations
    assert delineations["Sun in Aries"] == "You are a pioneer. This is a continuation line."
    
    assert "Quadrant 1 Strong" in delineations
    assert delineations["Quadrant 1 Strong"] == "You are independent."
    
    assert ";" not in str(delineations) # Comments should be fully excluded


def test_group_delineations():
    """
    Tests the logic for grouping parsed delineations into their target output files.
    """
    mock_dels = {
        "Quadrant 1 Strong": "Text Q1S",
        "Quadrant 2 Weak": "Text Q2W",
        "Element Fire Strong": "Text EFS",
        "Mode Fixed Weak": "Text MFW",
        "Aries Strong": "Text AS",
        "Sun in Leo": "Text SL",
        "Moon in Cancer": "Text MC",
        "Some Other Key": "Should be ignored",
    }
    points_to_process = ["Sun", "Moon"]

    groups = group_delineations(mock_dels, points_to_process)

    # Verify correct grouping
    assert groups["balances_quadrants.csv"] == {"Quadrant 1 Strong": "Text Q1S", "Quadrant 2 Weak": "Text Q2W"}
    assert groups["balances_elements.csv"] == {"Element Fire Strong": "Text EFS"}
    assert groups["balances_modes.csv"] == {"Mode Fixed Weak": "Text MFW"}
    assert groups["balances_signs.csv"] == {"Aries Strong": "Text AS"}
    assert groups["points_in_signs.csv"] == {"Sun in Leo": "Text SL", "Moon in Cancer": "Text MC"}
    
    # Verify that an irrelevant key was ignored
    assert "Some Other Key" not in str(groups)

# === End of tests/test_neutralize_delineations.py ===

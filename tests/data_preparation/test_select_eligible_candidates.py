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
# Filename: tests/data_preparation/test_select_eligible_candidates.py

"""
Unit tests for the eligible candidate selection script (src/select_eligible_candidates.py).

This test suite validates the script's core filtering and deduplication logic
by providing mock input files and asserting that the final output contains only
the correctly selected records.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from src import select_eligible_candidates


@pytest.fixture
def mock_sandbox(tmp_path: Path) -> Path:
    """Creates a temporary sandbox directory with mock input files."""
    # Create the necessary directory structure inside the temp path
    (tmp_path / "data" / "sources").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "intermediate").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "backup").mkdir(parents=True, exist_ok=True)

    raw_export_path = tmp_path / "data" / "sources" / "adb_raw_export.txt"
    validation_report_path = tmp_path / "data" / "reports" / "adb_validation_report.csv"

    # Create dummy raw export file (TSV format)
    raw_content = (
        "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tLatitude\tLink\n"
        "1\t101\tSmith\tJohn\tM\t1\t1\t1950\t12:00\t40N43\thttp://a.com\n"   # Valid (Northern)
        "2\t102\tDoe\tJane\tF\t1\t1\t1899\t12:00\t34N03\thttp://b.com\n"     # Invalid (Year too early)
        "3\t103\tLee\tBruce\tM\t27\t11\t1940\t07:12\t37N47\thttp://c.com\n"   # Valid (Northern)
        "4\t104\tKing\tMartin\tM\t15\t1\t1929\t12:00\t33N45\thttp://d.com\n"   # Invalid (Status FAIL)
        "5\t105\tCurie\tMarie\tF\t4\t7\t1934\t1200\t52N14\thttp://e.com\n"    # Invalid (Bad time format)
        "6\t101\tSmith\tJohn\tM\t1\t1\t1950\t12:00\t40N43\thttp://f.com\n"   # Duplicate
        "7\t106\tPele\t\tM\t23\t10\t1940\t03:00\t22S54\thttp://h.com\n"   # Invalid (Southern)
        "8\t201\tResearch: Event\t\t\t1\t1\t1960\t12:00\t48N51\thttp://g.com\n" # Research Entry
    )
    raw_export_path.write_text(raw_content)

    # Create dummy validation report (CSV format)
    validation_content = (
        "idADB,Status,Entry_Type\n"
        "101,OK,Person\n"
        "102,OK,Person\n"
        "103,OK,Person\n"
        "104,FAIL,Person\n"
        "105,OK,Person\n"
        "106,OK,Person\n"
        "201,VALID,Research\n"
    )
    validation_report_path.write_text(validation_content)

    return tmp_path


def test_select_eligible_candidates_main_logic(mock_sandbox):
    """
    Tests the main filtering logic of the select_eligible_candidates script.
    """
    sandbox_path = mock_sandbox
    output_path = sandbox_path / "data" / "intermediate" / "adb_eligible_candidates.txt"

    test_args = [
        "select_eligible_candidates.py",
        "--sandbox-path", str(sandbox_path),
        "--force", # Bypasses the interactive prompt
    ]
    with patch("sys.argv", test_args):
        select_eligible_candidates.main()

    assert output_path.exists()
    with open(output_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Expect header + 2 valid records (John Smith and Bruce Lee)
    assert len(lines) == 3
    
    id_adbs = {line.strip().split('\t')[1] for line in lines[1:]}
    assert id_adbs == {"101", "103"}


def test_select_eligible_candidates_resumes_correctly(mock_sandbox):
    """
    Tests that the script correctly identifies an up-to-date state and exits.
    """
    sandbox_path = mock_sandbox
    output_path = sandbox_path / "data" / "intermediate" / "adb_eligible_candidates.txt"

    # Create a pre-existing, complete output file
    output_content = (
        "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tLink\n"
        "1\t101\tSmith\tJohn\tM\t1\t1\t1950\t12:00\thttp://a.com\n"
        "3\t103\tLee\tBruce\tM\t27\t11\t1940\t07:12\thttp://c.com\n"
    )
    output_path.write_text(output_content)
    
    # Mock the user input to prevent the script from hanging
    with patch("builtins.input", return_value="n"):
        test_args = [
            "select_eligible_candidates.py",
            "--sandbox-path", str(sandbox_path),
        ]
        with patch("sys.argv", test_args):
            # The script should exit gracefully after the prompt
            with pytest.raises(SystemExit) as e:
                select_eligible_candidates.main()
            assert e.value.code == 0
    
    # Verify the output file was not changed
    with open(output_path, 'r', encoding='utf-8') as f:
        final_content = f.read()
    assert final_content == output_content

# === End of tests/data_preparation/test_select_eligible_candidates.py ===

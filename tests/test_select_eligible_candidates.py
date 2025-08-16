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
# Filename: tests/test_select_eligible_candidates.py

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
def mock_input_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Creates temporary input and output files for testing."""
    raw_export_path = tmp_path / "adb_raw_export.txt"
    validation_report_path = tmp_path / "adb_validation_report.csv"
    output_path = tmp_path / "eligible_candidates.txt"

    # Create dummy raw export file (TSV format)
    raw_content = (
        "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tLink\n"
        "1\t101\tSmith\tJohn\tM\t1\t1\t1950\t12:00\thttp://a.com\n"   # Valid
        "2\t102\tDoe\tJane\tF\t1\t1\t1899\t12:00\thttp://b.com\n"     # Invalid (Year too early)
        "3\t103\tLee\tBruce\tM\t27\t11\t1940\t07:12\thttp://c.com\n"   # Valid
        "4\t104\tKing\tMartin\tM\t15\t1\t1929\t12:00\thttp://d.com\n"   # Invalid (Status FAIL)
        "5\t105\tCurie\tMarie\tF\t4\t7\t1934\t1200\thttp://e.com\n"    # Invalid (Bad time format)
        "6\t101\tSmith\tJohn\tM\t1\t1\t1950\t12:00\thttp://f.com\n"   # Duplicate
    )
    raw_export_path.write_text(raw_content)

    # Create dummy validation report (CSV format)
    validation_content = (
        "idADB,Status\n"
        "101,OK\n"
        "102,OK\n"
        "103,VALID\n"
        "104,FAIL\n"
        "105,OK\n"
    )
    validation_report_path.write_text(validation_content)

    return raw_export_path, validation_report_path, output_path


def test_select_eligible_candidates_main_logic(mock_input_files):
    """
    Tests the main filtering logic of the select_eligible_candidates script.
    """
    raw_path, validation_path, output_path = mock_input_files

    test_args = [
        "select_eligible_candidates.py",
        "--input-file", str(raw_path),
        "--validation-report", str(validation_path),
        "--output-file", str(output_path),
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


def test_select_eligible_candidates_resumes_correctly(mock_input_files):
    """
    Tests that the script correctly identifies an up-to-date state and exits.
    """
    raw_path, validation_path, output_path = mock_input_files

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
            "--input-file", str(raw_path),
            "--validation-report", str(validation_path),
            "--output-file", str(output_path),
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

# === End of tests/test_select_eligible_candidates.py ===

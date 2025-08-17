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
# Filename: tests/test_prepare_sf_import.py

"""
Unit tests for the Solar Fire import preparation script (src/prepare_sf_import.py).

This test suite validates the script's core data transformation and formatting
logic by providing a mock input file and asserting that the output adheres to
the specific Comma Quote Delimited (CQD) format required by Solar Fire.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from src import prepare_sf_import


@pytest.fixture
def mock_input_file(tmp_path: Path) -> tuple[Path, Path]:
    """Creates temporary input and output files for testing."""
    input_path = tmp_path / "final_candidates.txt"
    output_path = tmp_path / "sf_import.txt"

    input_content = (
        "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tZoneAbbr\tZoneTimeOffset\tCity\tCountry\tLongitude\tLatitude\tRating\tBio\tCategories\tLink\n"
        "1\t101\tNewton\tIsaac\tM\t4\t1\t1643\t01:00\t...\t-00:01\tLondon\tUnited Kingdom\t0w5\t51n30\tAA\t...\t...\thttp://a.com\n"
        "2\t103\tMonroe\tMarilyn\tF\t1\t6\t1926\t09:30\tPST\t+08:00\tLos Angeles\tUnited States\t118w15\t34n03\tAA\t...\t...\thttp://c.com\n"
    )
    input_path.write_text(input_content)
    return input_path, output_path


def test_prepare_sf_import_logic(mock_input_file):
    """
    Tests the main data formatting and CQD file generation logic.
    """
    input_path, output_path = mock_input_file

    test_args = [
        "prepare_sf_import.py",
        "-i", str(input_path),
        "-o", str(output_path),
        "--force",
    ]

    with patch("sys.argv", test_args):
        prepare_sf_import.main()

    assert output_path.exists()
    with open(output_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    assert len(lines) == 2

    # Verify the first record (Newton)
    # idADB 101 -> Base58 '2k'
    expected_line1 = '"Isaac Newton","4 January 1643","01:00","2k","-00:01","London","United Kingdom","51N30","0W05"\n'
    assert lines[0] == expected_line1

    # Verify the second record (Monroe)
    # idADB 103 -> Base58 '2n'
    expected_line2 = '"Marilyn Monroe","1 June 1926","09:30","2n","+08:00","Los Angeles","United States","34N03","118W15"\n'
    assert lines[1] == expected_line2

# === End of tests/test_prepare_sf_import.py ===

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
# Filename: tests/test_select_final_candidates.py

"""
Unit tests for the final candidate selection script (src/select_final_candidates.py).

This test suite validates the script's core data transformation logic by
providing a set of mock input files and asserting that the final output is
correctly filtered, mapped, sorted, and formatted.
"""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from src import select_final_candidates


@pytest.fixture
def mock_input_files(tmp_path: Path) -> dict:
    """Creates a dictionary of temporary input file paths for testing."""
    paths = {
        "eligible": tmp_path / "eligible.txt",
        "ocean": tmp_path / "ocean.csv",
        "eminence": tmp_path / "eminence.csv",
        "country": tmp_path / "country.csv",
        "output": tmp_path / "final_candidates.txt",
    }

    # Create dummy input files
    paths["eligible"].write_text(
        "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tZoneAbbr\tZoneTimeOffset\tCity\tCountryState\tLongitude\tLatitude\tRating\tBio\tCategories\tLink\n"
        "1\t101\tNewton\tIsaac\tM\t4\t1\t1643\t01:00\t...\t...\t...\tUK\t...\t...\tAA\t...\t...\thttp://a.com\n"
        "2\t102\tPlato\t_\tM\t1\t1\t-427\t12:00\t...\t...\t...\tGR\t...\t...\tAA\t...\t...\thttp://b.com\n"
        "3\t103\tMonroe\tMarilyn\tF\t1\t6\t1926\t09:30\t...\t...\t...\tUSA\t...\t...\tAA\t...\t...\thttp://c.com\n"
        "4\t104\tExtra\tPerson\tF\t1\t1\t1990\t12:00\t...\t...\t...\tFR\t...\t...\tA\t...\t...\thttp://d.com\n"
    )
    paths["ocean"].write_text("idADB\n101\n102\n103")
    paths["eminence"].write_text("idADB,EminenceScore\n103,85.0\n101,99.5\n102,99.5")
    paths["country"].write_text("Abbreviation,Country\nUK,United Kingdom\nGR,Greece\nUSA,United States\nFR,France")

    return paths


def test_select_final_candidates_logic(mock_input_files):
    """
    Tests the main filtering, mapping, and sorting logic of the script.
    """
    paths = mock_input_files
    test_args = [
        "select_final_candidates.py",
        "--eligible-candidates", str(paths["eligible"]),
        "--ocean-scores", str(paths["ocean"]),
        "--eminence-scores", str(paths["eminence"]),
        "--country-codes", str(paths["country"]),
        "--output-file", str(paths["output"]),
        "--force",
    ]

    with patch("sys.argv", test_args):
        select_final_candidates.main()

    assert paths["output"].exists()
    output_df = pd.read_csv(paths["output"], sep="\t")

    # 1. Verify Filtering: "Extra Person" (104) should be removed.
    assert len(output_df) == 3
    assert 104 not in output_df["idADB"].values

    # 2. Verify Country Mapping: Check the 'Country' column content.
    assert output_df[output_df["idADB"] == 101]["Country"].iloc[0] == "United Kingdom"
    assert output_df[output_df["idADB"] == 102]["Country"].iloc[0] == "Greece"
    assert output_df[output_df["idADB"] == 103]["Country"].iloc[0] == "United States"

    # 3. Verify Sorting and Re-indexing: The final list should be sorted by eminence.
    # Monroe (id 103) has the lowest score and must be last.
    # Newton (101) and Plato (102) have the same score, so their order is not guaranteed.
    assert output_df.iloc[2]["idADB"] == 103
    assert set(output_df.head(2)["idADB"]) == {101, 102}
    
    # 4. Verify the final 'Index' is sequential from 1 to 3.
    assert output_df["Index"].tolist() == [1, 2, 3]

# === End of tests/test_select_final_candidates.py ===

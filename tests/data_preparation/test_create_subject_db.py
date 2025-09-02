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
# Filename: tests/data_preparation/test_create_subject_db.py

"""
Unit tests for the subject database creation script (src/create_subject_db.py).

This test suite validates the script's core data integration logic. It provides
mock input files for the final candidates list and the Solar Fire chart export,
and asserts that the script correctly decodes the Base58 ID, merges the files,
and flattens the celestial data into the final, correct database format.
"""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from src import create_subject_db


@pytest.fixture
def mock_input_files(tmp_path: Path) -> dict:
    """
    Creates mock input files in a sandboxed directory structure and returns
    the path to the sandbox and the expected output file.
    """
    # Create directory structure
    intermediate_dir = tmp_path / "data" / "intermediate"
    foundational_dir = tmp_path / "data" / "foundational_assets"
    processed_dir = tmp_path / "data" / "processed"
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    foundational_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    candidates_path = intermediate_dir / "adb_final_candidates.txt"
    chart_export_path = foundational_dir / "sf_chart_export.csv"
    output_path = processed_dir / "subject_db.csv"

    # Create dummy final candidates file
    candidates_path.write_text(
        "Index\tidADB\tLastName\tFirstName\n"
        "1\t101\tNewton\tIsaac\n"
        "2\t103\tMonroe\tMarilyn\n"
    )

    # Create dummy Solar Fire chart export
    # NOTE: The script decodes the ID from the 4th field (ZoneAbbr), not the name.
    chart_export_path.write_text(
        '"Isaac Newton","4 January 1643","1:00","2k","-0:01","London","UK","51n30","0w5"\n'
        '"Body Name","Body Abbr","Longitude"\n'
        '"Sun","Sun","285.65"\n"Moon","Mon","85.21"\n"Mercury","Mer","295.11"\n'
        '"Venus","Ven","325.00"\n"Mars","Mar","15.98"\n"Jupiter","Jup","35.22"\n'
        '"Saturn","Sat","335.88"\n"Uranus","Ura","225.12"\n"Neptune","Nep","235.65"\n'
        '"Pluto","Plu","105.43"\n"Ascendant","Asc","185.33"\n"Midheaven","MC","105.99"\n'
        '"Marilyn Monroe","1 June 1926","9:30","2n","+8:00","LA","USA","34n03","118w15"\n'
        '"Body Name","Body Abbr","Longitude"\n'
        '"Sun","Sun","70.45"\n"Moon","Mon","216.89"\n"Mercury","Mer","85.22"\n'
        '"Venus","Ven","45.12"\n"Mars","Mar","325.76"\n"Jupiter","Jup","320.11"\n'
        '"Saturn","Sat","205.32"\n"Uranus","Ura","358.99"\n"Neptune","Nep","145.43"\n'
        '"Pluto","Plu","105.21"\n"Ascendant","Asc","230.12"\n"Midheaven","MC","145.34"\n'
    )
    return {"sandbox_path": tmp_path, "output_path": output_path}


def test_create_subject_db_logic(mock_input_files):
    """
    Tests the main data integration and database creation logic.
    """
    sandbox_path = mock_input_files["sandbox_path"]
    output_path = mock_input_files["output_path"]

    test_args = [
        "create_subject_db.py",
        "--sandbox-path",
        str(sandbox_path),
        "--force",
    ]

    with patch("sys.argv", test_args):
        create_subject_db.main()

    assert output_path.exists()
    output_df = pd.read_csv(output_path)

    # 1. Verify the number of records is correct
    assert len(output_df) == 2

    # 2. Verify the merge and data flattening for a specific record (Newton)
    newton_record = output_df[output_df["idADB"] == 101].iloc[0]
    assert newton_record["Name"] == "Isaac Newton"
    assert newton_record["Sun"] == 285.65
    assert newton_record["Midheaven"] == 105.99
    assert pd.isna(newton_record["ZoneAbbrev"]) or newton_record["ZoneAbbrev"] == ""

    # 3. Verify the merge and data for the second record (Monroe)
    monroe_record = output_df[output_df["idADB"] == 103].iloc[0]
    assert monroe_record["Name"] == "Marilyn Monroe"
    assert monroe_record["Moon"] == 216.89
    assert monroe_record["Ascendant"] == 230.12

# === End of tests/data_preparation/test_create_subject_db.py ===

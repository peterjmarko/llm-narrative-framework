#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
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
# Filename: tests/data_preparation/test_select_eligible_candidates.py

"""
Unit tests for the eligible candidate selection script (src/select_eligible_candidates.py).

This test suite validates the script's core filtering and deduplication logic
by providing mock input files and asserting that the final output contains only
the correctly selected records.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src import select_eligible_candidates
from src.select_eligible_candidates import main


@pytest.fixture
def mock_sandbox(tmp_path: Path) -> Path:
    """Creates a temporary sandbox directory with mock input files."""
    # Create the necessary directory structure inside the temp path
    (tmp_path / "data" / "sources").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "processed").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "intermediate").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "backup").mkdir(parents=True, exist_ok=True)

    raw_export_path = tmp_path / "data" / "sources" / "adb_raw_export.txt"
    validation_report_path = tmp_path / "data" / "processed" / "adb_validated_subjects.csv"

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

    # Create dummy validation report (CSV format), quoting names that contain commas
    validation_content = (
        "idADB,Subject_Name,Status,Entry_Type\n"
        '101,"Smith, John",OK,Person\n'
        '102,"Doe, Jane",OK,Person\n'
        '103,"Lee, Bruce",OK,Person\n'
        '104,"King, Martin",FAIL,Person\n'
        '105,"Curie, Marie",OK,Person\n'
        '106,Pele,OK,Person\n' # No comma, no quotes needed
        '201,"Research: Event",VALID,Research\n'
    )
    validation_report_path.write_text(validation_content)

    return tmp_path


class TestMainWorkflow:
    """Tests the main orchestration logic of the script."""

    def test_main_logic_full_run(self, mock_sandbox):
        """Tests the main filtering logic on a fresh run."""
        output_path = mock_sandbox / "data/intermediate/adb_eligible_candidates.txt"
        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--force"]
        with patch("sys.argv", test_args):
            main()

        assert output_path.exists()
        df = pd.read_csv(output_path, sep='\t', dtype={'idADB': str})
        assert len(df) == 2
        assert set(df['idADB']) == {"101", "103"}

    def test_main_resumes_and_appends(self, mock_sandbox):
        """Tests that the script correctly appends new candidates to an existing file."""
        output_path = mock_sandbox / "data/intermediate/adb_eligible_candidates.txt"
        # Create an incomplete output file with only one of the two valid candidates
        pre_existing_content = "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tLatitude\tLink\n1\t101\tSmith\tJohn\tM\t1\t1\t1950\t12:00\t40N43\thttp://a.com\n"
        output_path.write_text(pre_existing_content)

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args):
            main()

        # The final file should contain both candidates
        df = pd.read_csv(output_path, sep='\t', dtype={'idADB': str})
        assert len(df) == 2
        assert set(df['idADB']) == {"101", "103"}

    def test_main_handles_stale_files(self, mock_sandbox, mocker):
        """Tests that stale input files trigger an automatic re-run."""
        input_path = mock_sandbox / "data/sources/adb_raw_export.txt"
        output_path = mock_sandbox / "data/intermediate/adb_eligible_candidates.txt"
        output_path.touch()

        # Make the input file newer than the output
        os.utime(input_path, (output_path.stat().st_mtime + 1, output_path.stat().st_mtime + 1))
        
        mock_backup = mocker.patch('src.select_eligible_candidates.backup_and_remove')
        mocker.patch('builtins.input', side_effect=EOFError) # Prevent hanging

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args):
            main()
        
        mock_backup.assert_called_once_with(output_path)

    def test_main_exits_if_input_missing(self, mock_sandbox, mocker, caplog):
        """Tests graceful exit if an input file is missing."""
        validation_path = mock_sandbox / "data/processed/adb_validated_subjects.csv"
        validation_path.unlink() # Delete one of the required inputs

        mocker.patch('sys.exit', side_effect=SystemExit)

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit):
                main()
        
        assert "Input file not found" in caplog.text

    def test_main_handles_user_cancellation(self, mock_sandbox):
        """Tests that the script exits if the user cancels an up-to-date run."""
        output_path = mock_sandbox / "data/intermediate/adb_eligible_candidates.txt"
        # Create a complete output file to trigger the prompt
        output_content = "Index\tidADB\tLastName\n1\t101\tSmith\n3\t103\tLee\n"
        output_path.write_text(output_content)

        with patch("builtins.input", return_value="n"):
            test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
            with patch("sys.argv", test_args):
                with pytest.raises(SystemExit) as e:
                    main()
                assert e.value.code == 0

# === End of tests/data_preparation/test_select_eligible_candidates.py ===

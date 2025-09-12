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
# Filename: tests/data_preparation/test_prepare_sf_import.py

"""
Unit tests for the Solar Fire import preparation script (src/prepare_sf_import.py).

This test suite validates the script's core data transformation and formatting
logic by providing a mock input file and asserting that the output adheres to
the specific Comma Quote Delimited (CQD) format required by Solar Fire.
"""

from pathlib import Path
from unittest.mock import patch
import os
import logging

import pytest
from src.prepare_sf_import import main, format_coordinate, format_for_solar_fire


@pytest.fixture
def mock_input_file(tmp_path: Path) -> dict:
    """
    Creates a mock input file in a sandboxed directory structure and returns
    the path to the sandbox and the expected output file.
    """
    intermediate_dir = tmp_path / "data" / "intermediate"
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    input_path = intermediate_dir / "adb_final_candidates.txt"
    output_path = intermediate_dir / "sf_data_import.txt"

    input_content = (
        "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tZoneAbbr\tZoneTimeOffset\tCity\tCountry\tLongitude\tLatitude\tRating\tBio\tCategories\tLink\n"
        "1\t101\tNewton\tIsaac\tM\t4\t1\t1643\t01:00\t...\t-00:01\tLondon\tUnited Kingdom\t0w5\t51n30\tAA\t...\t...\thttp://a.com\n"
        "2\t103\tMonroe\tMarilyn\tF\t1\t6\t1926\t09:30\tPST\t+08:00\tLos Angeles\tUnited States\t118w15\t34n03\tAA\t...\t...\thttp://c.com\n"
    )
    input_path.write_text(input_content)
    return {"sandbox_path": tmp_path, "output_path": output_path}


@pytest.mark.parametrize("input_coord, expected_output", [
    ("74w0", "74W00"),     # Standard case, needs padding
    ("12e34", "12E34"),    # Already correct
    ("5n5", "5N05"),       # Needs padding
    ("", ""),              # Empty input
    ("invalid", "INVALID"), # Non-matching format
])
def test_format_coordinate(input_coord, expected_output):
    """Tests the coordinate formatting logic."""
    assert format_coordinate(input_coord) == expected_output


class TestMainWorkflow:
    """Tests the main orchestration logic of the script."""

    def test_main_logic_happy_path(self, mock_input_file):
        """Tests the main data formatting and CQD file generation logic."""
        sandbox_path = mock_input_file["sandbox_path"]
        output_path = mock_input_file["output_path"]
        test_args = ["script.py", "--sandbox-path", str(sandbox_path), "--force"]

        with patch("sys.argv", test_args):
            main()

        assert output_path.exists()
        lines = output_path.read_text().splitlines()
        assert len(lines) == 2
        # idADB 101 -> '2k'; idADB 103 -> '2n'
        assert '"Isaac Newton","4 January 1643","01:00","2k",' in lines[0]
        assert '"Marilyn Monroe","1 June 1926","09:30","2n",' in lines[1]

    def test_main_handles_user_cancellation(self, mock_input_file):
        """Tests that the script exits if the user cancels an up-to-date run."""
        output_path = mock_input_file["output_path"]
        output_path.touch() # Create an existing output file

        with patch("builtins.input", return_value="n"):
            test_args = ["script.py", "--sandbox-path", str(mock_input_file["sandbox_path"])]
            with patch("sys.argv", test_args):
                with pytest.raises(SystemExit) as e:
                    main()
                assert e.value.code == 0

    def test_main_handles_stale_file(self, mock_input_file, mocker):
        """Tests that a stale output file triggers an automatic re-run."""
        sandbox_path = mock_input_file["sandbox_path"]
        input_path = sandbox_path / "data/intermediate/adb_final_candidates.txt"
        output_path = mock_input_file["output_path"]
        output_path.touch()

        # Make the input file newer than the output
        os.utime(input_path, (output_path.stat().st_mtime + 1, output_path.stat().st_mtime + 1))
        
        mock_backup = mocker.patch('src.prepare_sf_import.backup_and_remove')

        test_args = ["script.py", "--sandbox-path", str(sandbox_path)]
        with patch("sys.argv", test_args):
            main()
        
        mock_backup.assert_called_once_with(output_path)

    def test_main_exits_if_input_missing(self, mock_input_file, mocker, caplog):
        """Tests graceful exit if the input file is missing."""
        sandbox_path = mock_input_file["sandbox_path"]
        input_path = sandbox_path / "data/intermediate/adb_final_candidates.txt"
        input_path.unlink() # Delete the input file

        mocker.patch('sys.exit', side_effect=SystemExit)

        test_args = ["script.py", "--sandbox-path", str(sandbox_path)]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit):
                main()
        
        assert "Input file not found" in caplog.text

    def test_main_skips_invalid_date(self, mock_input_file, caplog):
        """Tests that records with invalid dates are skipped and logged."""
        sandbox_path = mock_input_file["sandbox_path"]
        input_path = sandbox_path / "data/intermediate/adb_final_candidates.txt"
        output_path = mock_input_file["output_path"]

        # Add a record with an invalid month (13) to the input file
        with open(input_path, "a", encoding="utf-8") as f:
            f.write("3\t201\tInvalid\tDate\tM\t1\t13\t2000\t12:00\t...\t0\tCity\tCountry\t0w0\t0n0\tA\t...\t...\thttp://d.com\n")

        test_args = ["script.py", "--sandbox-path", str(sandbox_path), "--force"]
        
        # Use caplog.at_level to ensure messages are captured, regardless of prior test state
        with caplog.at_level(logging.WARNING):
            with patch("sys.argv", test_args):
                main()

        # The output should still be created with the two valid records
        assert output_path.exists()
        lines = output_path.read_text().splitlines()
        assert len(lines) == 2
        
        # Check that the warning was logged
        assert "Skipping record for Date Invalid due to invalid date" in caplog.text

# === End of tests/data_preparation/test_prepare_sf_import.py ===

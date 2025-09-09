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
# Filename: tests/data_preparation/test_generate_personalities_db.py

"""
Unit tests for the final database generation script (src/generate_personalities_db.py).

This test suite validates the script's core data assembly algorithm. It provides
a complete set of mock input files (subjects, weights, thresholds, and text
snippets) and asserts that the final personality descriptions are correctly
calculated and assembled based on the deterministic rules.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from src.generate_personalities_db import main, calculate_classifications


@pytest.fixture
def mock_input_files(tmp_path: Path) -> dict:
    """
    Creates mock input files in a sandboxed directory structure and returns
    the path to the sandbox and the expected output file.
    """
    # Create the directory structure inside the temp sandbox
    processed_dir = tmp_path / "data" / "processed"
    foundational_dir = tmp_path / "data" / "foundational_assets"
    delineations_dir = foundational_dir / "neutralized_delineations"
    processed_dir.mkdir(parents=True, exist_ok=True)
    delineations_dir.mkdir(parents=True, exist_ok=True)

    # Define paths for mock files
    subject_db_path = processed_dir / "subject_db.csv"
    point_weights_path = foundational_dir / "point_weights.csv"
    thresholds_path = foundational_dir / "balance_thresholds.csv"
    output_path = tmp_path / "data" / "personalities_db.txt"

    subject_db_path.write_text(
        "Index,idADB,Name,Date,Sun,Moon,Ascendant,Midheaven\n"
        "1,101,Pioneer,1950-01-01,10.0,100.0,10.0,100.0\n"  # Sun & Asc in Aries
        "2,102,Stable,1960-01-01,100.0,40.0,100.0,100.0\n"   # Moon in Taurus
    )
    point_weights_path.write_text("Point,Weight\nSun,10\nMoon,10\nAscendant,10\nMidheaven,5")
    thresholds_path.write_text("Category,WeakRatio,StrongRatio\nSigns,0.1,1.01\nElements,0.1,1.01\nModes,0.1,1.01\nQuadrants,0.1,1.01\nHemispheres,0.1,1.01")
    
    # Delineation files
    (delineations_dir / "points_in_signs.csv").write_text('"Sun in Aries","Is a pioneer."\n"Moon in Taurus","Is grounded."')
    (delineations_dir / "balances_elements.csv").write_text('"Element Fire Strong","Has a fiery nature."')
    # Create the other required (but empty for this test) delineation files
    (delineations_dir / "balances_modes.csv").touch()
    (delineations_dir / "balances_hemispheres.csv").touch()
    (delineations_dir / "balances_quadrants.csv").touch()
    (delineations_dir / "balances_signs.csv").touch()

    return {"sandbox_path": tmp_path, "output_path": output_path}


def test_calculate_classifications_weak_scores():
    """Tests that the classification logic correctly identifies 'weak' factors."""
    # Placements: Sun in Aries (Fire), Moon in Taurus (Earth)
    placements = {"Sun": 10.0, "Moon": 40.0}
    point_weights = {"Sun": 10, "Moon": 10}
    # Use a high strong_ratio to prevent any 'strong' classifications
    thresholds = {
        "Elements": {"weak_ratio": 0.1, "strong_ratio": 2.0},
        "Modes": {"weak_ratio": 0.1, "strong_ratio": 2.0},
        "Quadrants": {"weak_ratio": 0.1, "strong_ratio": 2.0},
        "Hemispheres": {"weak_ratio": 0.1, "strong_ratio": 2.0},
        "Signs": {"weak_ratio": 0.1, "strong_ratio": 2.0},
    }
    points_to_process = ["Sun", "Moon"]
    
    classifications = calculate_classifications(placements, point_weights, thresholds, points_to_process)
    
    # Air and Water elements have 0 points, so they should be classified as weak.
    assert "Element Air Weak" in classifications
    assert "Element Water Weak" in classifications
    # Mutable mode has 0 points, so it should be weak.
    assert "Mode Mutable Weak" in classifications


class TestMainWorkflow:
    """Tests the main orchestration logic of the script."""

    def test_main_logic_happy_path(self, mock_input_files):
        """Tests the main database generation algorithm."""
        sandbox_path = mock_input_files["sandbox_path"]
        output_path = mock_input_files["output_path"]

        test_args = ["generate_personalities_db.py", "--sandbox-path", str(sandbox_path), "--force"]
        with patch("sys.argv", test_args):
            main()

        assert output_path.exists()
        output_df = pd.read_csv(output_path, sep="\t")
        assert len(output_df) == 2
        pioneer_desc = output_df[output_df["idADB"] == 101]["DescriptionText"].iloc[0]
        assert "Is a pioneer." in pioneer_desc
        assert "Has a fiery nature." in pioneer_desc

    def test_main_handles_user_cancellation(self, mock_input_files):
        """Tests that the script exits if the user cancels an up-to-date run."""
        output_path = mock_input_files["output_path"]
        output_path.touch()

        with patch("builtins.input", return_value="n"):
            test_args = ["script.py", "--sandbox-path", str(mock_input_files["sandbox_path"])]
            with patch("sys.argv", test_args):
                with pytest.raises(SystemExit) as e:
                    main()
                assert e.value.code == 0

    def test_main_handles_stale_file(self, mock_input_files, mocker):
        """Tests that a stale input file triggers an automatic re-run."""
        sandbox_path = mock_input_files["sandbox_path"]
        subject_db_path = sandbox_path / "data/processed/subject_db.csv"
        output_path = mock_input_files["output_path"]
        output_path.touch()

        os.utime(subject_db_path, (output_path.stat().st_mtime + 1, output_path.stat().st_mtime + 1))
        mock_backup = mocker.patch('src.generate_personalities_db.backup_and_remove')

        test_args = ["script.py", "--sandbox-path", str(sandbox_path)]
        with patch("sys.argv", test_args):
            main()
        
        mock_backup.assert_called_once_with(output_path)

    def test_main_exits_if_input_missing(self, mock_input_files, mocker, caplog):
        """Tests graceful exit if a required input file is missing."""
        sandbox_path = mock_input_files["sandbox_path"]
        (sandbox_path / "data/foundational_assets/point_weights.csv").unlink()

        mocker.patch('sys.exit', side_effect=SystemExit)

        test_args = ["script.py", "--sandbox-path", str(sandbox_path)]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit):
                main()
        
        assert "Point weights file not found" in caplog.text

    def test_main_runs_for_single_record(self, mock_input_files, capsys):
        """Tests that the --test-record-number flag works correctly."""
        sandbox_path = mock_input_files["sandbox_path"]
        output_path = mock_input_files["output_path"]
        
        # Run for the second record in the mock file ("Stable")
        test_args = ["script.py", "--sandbox-path", str(sandbox_path), "--force", "--test-record-number", "2"]
        with patch("sys.argv", test_args):
            main()

        output_df = pd.read_csv(output_path, sep="\t")
        assert len(output_df) == 1
        assert output_df["idADB"].iloc[0] == 102
        
        captured = capsys.readouterr()
        assert "DEBUG: Processing Subject: Stable" in captured.out

# === End of tests/data_preparation/test_generate_personalities_db.py ===

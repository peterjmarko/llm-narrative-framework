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
# Filename: tests/test_generate_personalities_db.py

"""
Unit tests for the final database generation script (src/generate_personalities_db.py).

This test suite validates the script's core data assembly algorithm. It provides
a complete set of mock input files (subjects, weights, thresholds, and text
snippets) and asserts that the final personality descriptions are correctly
calculated and assembled based on the deterministic rules.
"""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from src import generate_personalities_db


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
    output_path = tmp_path / "personalities_db.txt"

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


def test_generate_personalities_db_logic(mock_input_files):
    """
    Tests the main database generation algorithm.
    """
    sandbox_path = mock_input_files["sandbox_path"]
    output_path = mock_input_files["output_path"]

    test_args = [
        "generate_personalities_db.py",
        "--sandbox-path",
        str(sandbox_path),
        "--force",
    ]
    
    with patch("sys.argv", test_args):
        generate_personalities_db.main()

    assert output_path.exists()
    output_df = pd.read_csv(output_path, sep="\t")

    assert len(output_df) == 2
    
    pioneer_desc = output_df[output_df["idADB"] == 101]["DescriptionText"].iloc[0]
    stable_desc = output_df[output_df["idADB"] == 102]["DescriptionText"].iloc[0]

    # Pioneer has Sun & Ascendant in Aries -> high Fire score -> triggers both delineations
    assert "Is a pioneer." in pioneer_desc
    assert "Has a fiery nature." in pioneer_desc
    
    # Stable has Moon in Taurus -> triggers only that delineation
    assert stable_desc == "Is grounded."

# === End of tests/test_generate_personalities_db.py ===

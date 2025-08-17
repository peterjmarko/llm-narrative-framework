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
    """Creates a temporary directory structure with all necessary input files."""
    data_dir = tmp_path / "data"
    delineations_dir = data_dir / "foundational_assets/neutralized_delineations"
    delineations_dir.mkdir(parents=True)

    paths = {
        "subject_db": data_dir / "processed/subject_db.csv",
        "point_weights": data_dir / "foundational_assets/point_weights.csv",
        "thresholds": data_dir / "foundational_assets/balance_thresholds.csv",
        "delineations_dir": str(delineations_dir),
        "output": data_dir / "personalities_db.txt",
    }
    
    paths["subject_db"].parent.mkdir(parents=True)
    paths["subject_db"].write_text(
        "Index,idADB,Name,Date,Sun,Moon,Ascendant,Midheaven\n"
        "1,101,Pioneer,1950-01-01,10.0,100.0,10.0,100.0\n" # Sun & Ascendant in Aries
        "2,102,Stable,1960-01-01,100.0,40.0,100.0,100.0\n" # Moon in Taurus
    )
    paths["point_weights"].write_text("Point,Weight\nSun,10\nMoon,10\nAscendant,10\nMidheaven,5")
    paths["thresholds"].write_text("Category,WeakRatio,StrongRatio\nSigns,0.1,1.01\nElements,0.1,1.01\nModes,0.1,1.01\nQuadrants,0.1,1.01\nHemispheres,0.1,1.01")
    
    # Delineation files
    (delineations_dir / "points.csv").write_text('"Sun In Aries","Is a pioneer."\n"Moon In Taurus","Is grounded."')
    (delineations_dir / "balances.csv").write_text('"Element Fire Strong","Has a fiery nature."')

    return paths


def test_generate_personalities_db_logic(mock_input_files):
    """
    Tests the main database generation algorithm.
    """
    paths = mock_input_files
    test_args = [
        "generate_personalities_db.py",
        "--subject-db", str(paths["subject_db"]),
        "--delineations-dir", str(paths["delineations_dir"]),
        "--point-weights", str(paths["point_weights"]),
        "--thresholds", str(paths["thresholds"]),
        "--output-file", str(paths["output"]),
        "--force",
    ]
    
    with patch("sys.argv", test_args):
        generate_personalities_db.main()

    assert paths["output"].exists()
    output_df = pd.read_csv(paths["output"], sep="\t")

    assert len(output_df) == 2
    
    pioneer_desc = output_df[output_df["idADB"] == 101]["DescriptionText"].iloc[0]
    stable_desc = output_df[output_df["idADB"] == 102]["DescriptionText"].iloc[0]

    # Pioneer has Sun & Ascendant in Aries -> high Fire score -> triggers both delineations
    assert "Is a pioneer." in pioneer_desc
    assert "Has a fiery nature." in pioneer_desc
    
    # Stable has Moon in Taurus -> triggers only that delineation
    assert stable_desc == "Is grounded."

# === End of tests/test_generate_personalities_db.py ===

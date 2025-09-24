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
# Filename: tests/data_preparation/test_select_final_candidates.py

"""
Unit tests for the final candidate selection script (src/select_final_candidates.py).

This test suite validates the script's core data transformation logic by
providing a set of mock input files and asserting that the final output is
correctly filtered, mapped, sorted, and formatted. It also includes specific
tests for the variance-based cohort selection algorithm.
"""

import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from src import select_final_candidates


def test_calculate_average_variance():
    """Tests the average variance calculation."""
    # Case 1: Valid data with known variance
    data = {'Openness': [1, 2, 3], 'Conscientiousness': [2, 3, 4], 'Extraversion': [1,1,1], 'Agreeableness': [1,1,1], 'Neuroticism': [1,1,1]}
    df = pd.DataFrame(data)
    # Variance of [1,2,3] is 1.0. Variance of [2,3,4] is 1.0. Variance of [1,1,1] is 0.0.
    # Average variance = (1.0 + 1.0 + 0 + 0 + 0) / 5 = 0.4
    assert select_final_candidates.calculate_average_variance(df) == pytest.approx(0.4)

    # Case 2: Insufficient data (less than 2 rows)
    df_small = df.head(1)
    assert select_final_candidates.calculate_average_variance(df_small) == 0.0

    # Case 3: Empty DataFrame
    assert select_final_candidates.calculate_average_variance(pd.DataFrame()) == 0.0


@pytest.fixture
def mock_input_files(tmp_path: Path) -> dict:
    """
    Creates mock input files in a sandboxed directory structure and returns
    the path to the sandbox and the expected output file.
    """
    # Create the directory structure inside the temp sandbox
    intermediate_dir = tmp_path / "data" / "intermediate"
    foundational_dir = tmp_path / "data" / "foundational_assets"
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    foundational_dir.mkdir(parents=True, exist_ok=True)

    # Define paths for mock files
    eligible_path = intermediate_dir / "adb_eligible_candidates.txt"
    ocean_path = foundational_dir / "ocean_scores.csv"
    eminence_path = foundational_dir / "eminence_scores.csv"
    country_path = foundational_dir / "country_codes.csv"
    output_path = intermediate_dir / "adb_final_candidates.txt"

    # Create dummy input files
    eligible_path.write_text(
        "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tZoneAbbr\tZoneTimeOffset\tCity\tCountryState\tLongitude\tLatitude\tRating\tBio\tCategories\tLink\n"
        "1\t101\tNewton\tIsaac\tM\t4\t1\t1643\t01:00\t...\t...\t...\tUK\t...\t...\tAA\t...\t...\thttp://a.com\n"
        "2\t102\tPlato\t_\tM\t1\t1\t-427\t12:00\t...\t...\t...\tGR\t...\t...\tAA\t...\t...\thttp://b.com\n"
        "3\t103\tMonroe\tMarilyn\tF\t1\t6\t1926\t09:30\t...\t...\t...\tUSA\t...\t...\tAA\t...\t...\thttp://c.com\n"
        "4\t104\tExtra\tPerson\tF\t1\t1\t1990\t12:00\t...\t...\t...\tFR\t...\t...\tA\t...\t...\thttp://d.com\n"
    )
    ocean_path.write_text("idADB,Openness,Conscientiousness,Extraversion,Agreeableness,Neuroticism\n101,5,5,5,5,5\n102,5,5,5,5,5\n103,5,5,5,5,5")
    eminence_path.write_text("idADB,EminenceScore\n103,85.0\n101,99.5\n102,99.5")
    country_path.write_text("Abbreviation,Country\nUK,United Kingdom\nGR,Greece\nUSA,United States\nFR,France")

    return {"sandbox_path": tmp_path, "output_path": output_path}


@pytest.fixture
def mock_sandbox_with_bypass_config(mock_input_files) -> Path:
    """Creates a mock config.ini with bypass_candidate_selection set to true."""
    sandbox_path = mock_input_files["sandbox_path"]
    config_content = (
        "[DataGeneration]\n"
        "bypass_candidate_selection = true\n"
    )
    (sandbox_path / "config.ini").write_text(config_content)
    return sandbox_path


def test_select_final_candidates_logic(mock_input_files):
    """
    Tests the main filtering, mapping, and sorting logic of the script using a small
    dataset where the variance cutoff logic is not triggered.
    """
    sandbox_path = mock_input_files["sandbox_path"]
    output_path = mock_input_files["output_path"]

    test_args = [
        "select_final_candidates.py",
        "--sandbox-path", str(sandbox_path),
        "--force",
    ]

    with patch("sys.argv", test_args):
        select_final_candidates.main()

    assert output_path.exists()
    output_df = pd.read_csv(output_path, sep="\t")

    # 1. Verify Filtering: "Extra Person" (104) should be removed.
    assert len(output_df) == 3
    assert 104 not in output_df["idADB"].values

    # 2. Verify Country Mapping: Check the 'Country' column content.
    assert output_df[output_df["idADB"] == 101]["Country"].iloc[0] == "United Kingdom"
    assert output_df[output_df["idADB"] == 102]["Country"].iloc[0] == "Greece"
    assert output_df[output_df["idADB"] == 103]["Country"].iloc[0] == "United States"

    # 3. Verify Sorting and Re-indexing: The final list should be sorted by eminence.
    assert output_df.iloc[2]["idADB"] == 103
    assert set(output_df.head(2)["idADB"]) == {101, 102}
    
    # 4. Verify the final 'Index' is sequential from 1 to 3.
    assert output_df["Index"].tolist() == [1, 2, 3]


def test_select_final_candidates_bypass_mode(mock_sandbox_with_bypass_config, mock_input_files):
    """
    Tests that the script correctly bypasses the scoring filter when the
    config flag is set.
    """
    sandbox_path = mock_sandbox_with_bypass_config
    output_path = mock_input_files["output_path"]
    
    # In bypass mode, eminence/ocean scores should NOT exist, but the script should succeed.
    (sandbox_path / "data" / "foundational_assets" / "eminence_scores.csv").unlink()
    (sandbox_path / "data" / "foundational_assets" / "ocean_scores.csv").unlink()

    test_args = [
        "select_final_candidates.py",
        "--sandbox-path", str(sandbox_path),
        "--force",
    ]
    with patch("sys.argv", test_args):
        select_final_candidates.main()

    assert output_path.exists()
    
    output_df = pd.read_csv(output_path, sep='\t')
    assert len(output_df) == 4
    assert (output_df["EminenceScore"] == 0).all()


@pytest.fixture
def mock_sandbox_for_cutoff_test(tmp_path: Path) -> dict:
    """Creates a mock sandbox with a large dataset to test the variance cutoff."""
    intermediate_dir = tmp_path / "data" / "intermediate"
    foundational_dir = tmp_path / "data" / "foundational_assets"
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    foundational_dir.mkdir(parents=True, exist_ok=True)
    
    (tmp_path / "config.ini").write_text(
        "[DataGeneration]\n"
        # Parameters are scaled down from production to match the smaller test dataset size
        "cutoff_search_start_point = 700\n"
        "smoothing_window_size = 160\n"
        "slope_threshold = -0.0001\n"
    )

    num_subjects = 1000
    ids = [1000 + i for i in range(num_subjects)]
    
    eligible_header = "Index\tidADB\tLastName\tFirstName\tGender\tDay\tMonth\tYear\tTime\tZoneAbbr\tZoneTimeOffset\tCity\tCountryState\tLongitude\tLatitude\tRating\tBio\tCategories\tLink\n"
    eligible_rows = [f"{i}\t{ids[i-1]}\tL\tF\tM\t1\t1\t1950\t12:00\t...\t...\t...\tUK\t...\t...\tA\t...\t...\t..." for i in range(1, num_subjects + 1)]
    (intermediate_dir / "adb_eligible_candidates.txt").write_text(eligible_header + "\n".join(eligible_rows))

    eminence_header = "idADB,EminenceScore\n"
    eminence_rows = [f"{id},{100 - (i/10)}" for i, id in enumerate(ids)]
    (foundational_dir / "eminence_scores.csv").write_text(eminence_header + "\n".join(eminence_rows))

    (foundational_dir / "country_codes.csv").write_text("Abbreviation,Country\nUK,United Kingdom")

    ocean_header = "idADB,Openness,Conscientiousness,Extraversion,Agreeableness,Neuroticism\n"
    ocean_rows = []
    np.random.seed(42)
    high_var_scores = np.random.uniform(1.0, 7.0, size=(600, 5))
    for i in range(600):
        scores_str = ",".join([f"{s:.1f}" for s in high_var_scores[i]])
        ocean_rows.append(f"{ids[i]},{scores_str}")
    for i in range(600, 1000):
        ocean_rows.append(f"{ids[i]},5.0,5.0,5.0,5.0,5.0")
    (foundational_dir / "ocean_scores.csv").write_text(ocean_header + "\n".join(ocean_rows))

    return {"sandbox_path": tmp_path, "output_path": intermediate_dir / "adb_final_candidates.txt"}


def test_select_final_candidates_with_variance_cutoff(mock_sandbox_for_cutoff_test):
    """Tests that the variance-based cutoff logic correctly trims the dataset."""
    sandbox_path = mock_sandbox_for_cutoff_test["sandbox_path"]
    output_path = mock_sandbox_for_cutoff_test["output_path"]

    test_args = [
        "select_final_candidates.py", "--sandbox-path", str(sandbox_path), "--force",
    ]

    # Mock plt.show() to prevent plot window from opening during tests
    with patch("sys.argv", test_args), patch("matplotlib.pyplot.show"):
        select_final_candidates.main()

    assert output_path.exists()
    output_df = pd.read_csv(output_path, sep="\t")

    # The search for the plateau starts at subject 700. The algorithm should find
    # the point of diminishing returns somewhere after that but before the end
    # of the dataset. The exact value is sensitive to the smoothing algorithm.
    final_count = len(output_df)
    assert 700 < final_count < 950


def test_plot_flag_triggers_plot_generation(mock_sandbox_for_cutoff_test):
    """Tests that the --plot flag correctly calls the plot generation function."""
    sandbox_path = mock_sandbox_for_cutoff_test["sandbox_path"]
    test_args = [
        "select_final_candidates.py",
        "--sandbox-path", str(sandbox_path),
        "--force",
        "--plot",
    ]

    with patch("sys.argv", test_args), \
         patch("src.select_final_candidates.generate_variance_plot") as mock_generate_plot:
        select_final_candidates.main()
    
    mock_generate_plot.assert_called_once()


def test_interactive_overwrite_prompt_cancel(mock_input_files):
    """Tests that the script exits gracefully if the user cancels an overwrite."""
    sandbox_path = mock_input_files["sandbox_path"]
    output_path = mock_input_files["output_path"]
    
    # Run once to create an up-to-date file
    with patch("sys.argv", ["script.py", "--sandbox-path", str(sandbox_path)]):
        select_final_candidates.main()
    
    mtime_before = output_path.stat().st_mtime

    # Run again without --force, simulating user input 'n' to cancel
    test_args_no_force = ["script.py", "--sandbox-path", str(sandbox_path)]
    with patch("sys.argv", test_args_no_force), \
         patch("builtins.input", return_value="n"):
        
        with pytest.raises(SystemExit) as e:
            select_final_candidates.main()
        assert e.value.code == 0  # Graceful exit

    # Verify the file was not modified
    mtime_after = output_path.stat().st_mtime
    assert mtime_after == mtime_before

# === End of tests/data_preparation/test_select_final_candidates.py ===

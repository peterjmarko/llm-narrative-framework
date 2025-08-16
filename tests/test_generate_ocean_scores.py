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
# Filename: tests/test_generate_ocean_scores.py

"""
Unit tests for the OCEAN score generation script (src/generate_ocean_scores.py).

This test suite validates the critical offline logic of the script. It focuses
on three key areas:
1.  Parsing the structured JSON response from the LLM.
2.  The core statistical calculation for average variance.
3.  The complex "pre-flight check" logic that makes the script robustly
    resumable by re-analyzing existing data to determine if the variance-based
    cutoff condition has already been met.
"""

from collections import deque
from types import SimpleNamespace

import pandas as pd
import pytest
from src.generate_ocean_scores import (
    calculate_average_variance,
    parse_batch_response,
    perform_pre_flight_check,
)


def test_parse_batch_response():
    """Tests the parsing of JSON responses from the LLM."""
    # Case 1: Valid JSON
    response_text = """
    Some introductory text from the model.
    [
      {"idADB": "101", "Name": "A", "Openness": 5.0, "Conscientiousness": 5.0, "Extraversion": 5.0, "Agreeableness": 5.0, "Neuroticism": 5.0},
      {"idADB": "102", "Name": "B", "Openness": 6.0, "Conscientiousness": 6.0, "Extraversion": 6.0, "Agreeableness": 6.0, "Neuroticism": 6.0}
    ]
    Some trailing text.
    """
    result = parse_batch_response(response_text)
    assert len(result) == 2
    assert result[0]['idADB'] == "101"

    # Case 2: Malformed JSON
    assert parse_batch_response("[{'idADB': '101'}]") == [] # Invalid JSON quotes
    # Case 3: No JSON array
    assert parse_batch_response("Just some text.") == []


def test_calculate_average_variance():
    """Tests the average variance calculation."""
    # Case 1: Valid data
    data = {'Openness': [1, 2, 3], 'Conscientiousness': [2, 3, 4], 'Extraversion': [1,1,1], 'Agreeableness': [1,1,1], 'Neuroticism': [1,1,1]}
    df = pd.DataFrame(data)
    # Variance of [1,2,3] is 1.0. Variance of [2,3,4] is 1.0. Variance of [1,1,1] is 0.0.
    # Average variance = (1.0 + 1.0 + 0 + 0 + 0) / 5 = 0.4
    assert calculate_average_variance(df) == pytest.approx(0.4)

    # Case 2: Insufficient data
    df_small = df.head(1)
    assert calculate_average_variance(df_small) == 0.0


def test_perform_pre_flight_check(mocker, tmp_path):
    """Tests the pre-flight check logic for resuming or finalizing a run."""
    mock_args = SimpleNamespace(
        cutoff_start_point=100,
        variance_check_window=3,
        variance_trigger_count=2,
        variance_analysis_window=50,
        variance_cutoff_percentage=0.5,
        output_file=str(tmp_path / "scores.csv"),
        benchmark_population_size=100 # Add dummy values for summary report
    )
    # Mock the functions that would perform file I/O
    mocker.patch('src.generate_ocean_scores.truncate_and_archive_scores')
    mocker.patch('src.generate_ocean_scores.generate_summary_report')

    # Case 1: Not enough data to start checks
    df_too_small = pd.DataFrame({'idADB': range(99)})
    status, _ = perform_pre_flight_check(mock_args, df_too_small, 0.5, deque())
    assert status == "CONTINUE"

    # Case 2: Enough data, but cutoff condition is NOT met
    data_normal = {
        'Openness': [1]*100 + [1,2,3,4,5]*10, # Add variance to the second window
        'Conscientiousness': [1]*150, 'Extraversion': [1]*150,
        'Agreeableness': [1]*150, 'Neuroticism': [1]*150
    }
    df_normal = pd.DataFrame(data_normal)
    # Window 1 (0-100) has var=0 (met). Window 2 (50-150) has var > 0 (not met).
    # Total met_count will be 1, which is less than the trigger count of 2.
    status, checks = perform_pre_flight_check(mock_args, df_normal, 0.5, deque())
    assert status == "CONTINUE"
    assert len(checks) == 2
    assert sum(1 for c in checks if c[2]) == 1 # Only one of the two checks should be met

    # Case 3: Cutoff condition IS met
    # Simulate a history of 3 checks, with 2 of them meeting the threshold
    initial_checks = deque([
        (100, 0.1, True, 20.0), # Met
        (150, 0.8, False, 160.0),# Not Met
        (200, 0.2, True, 40.0), # Met -> This is the 2nd of 3, so trigger stop
    ], maxlen=3)
    df_cutoff = pd.DataFrame({'idADB': range(200)})
    status, _ = perform_pre_flight_check(mock_args, df_cutoff, 0.5, initial_checks)
    assert status == "EXIT"

# === End of tests/test_generate_ocean_scores.py ===

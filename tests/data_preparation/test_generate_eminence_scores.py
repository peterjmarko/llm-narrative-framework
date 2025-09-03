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
# Filename: tests/data_preparation/test_generate_eminence_scores.py

"""
Unit tests for the eminence score generation script (src/generate_eminence_scores.py).

This test suite validates the script's critical offline logic. It includes tests
for parsing the structured LLM response, handling resumability by loading
previously processed IDs (including legacy format detection), and a mocked test
of the main orchestrator loop to ensure the subprocess worker is called correctly.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from src.generate_eminence_scores import main, load_processed_ids, parse_batch_response


@pytest.mark.parametrize("response_text, expected_output", [
    # Case 1: Standard, well-formed response
    (
        '"Albert Einstein (1879), ID 2001: 99.0"\n"Zsa Zsa Gabor (1917), ID 2002: 70.0"',
        [('2001', 'Albert Einstein', '1879', '99.0'), ('2002', 'Zsa Zsa Gabor', '1917', '70.0')]
    ),
    # Case 2: Response with extra whitespace and blank lines
    (
        '  "John F. Kennedy (1917), ID 3001: 95.5"  \n\n"Alan Turing (1912), ID 3002: 90.1"',
        [('3001', 'John F. Kennedy', '1917', '95.5'), ('3002', 'Alan Turing', '1912', '90.1')]
    ),
    # Case 3: Response with a mix of valid and malformed lines
    (
        '"Valid Person (1950), ID 4001: 80.0"\nThis is some commentary.\n"Another Person (1960), ID 4002: 75.0"',
        [('4001', 'Valid Person', '1950', '80.0'), ('4002', 'Another Person', '1960', '75.0')]
    ),
    # Case 4: Name contains a comma
    (
        '"King, Martin Luther (1929), ID 5001: 96.0"',
        [('5001', 'King, Martin Luther', '1929', '96.0')]
    ),
    # Case 5: Empty input
    ("", []),
])
def test_parse_batch_response(response_text, expected_output):
    """
    Tests the parse_batch_response function with various LLM response formats.
    """
    parsed_data = parse_batch_response(response_text)
    assert parsed_data == expected_output


def test_load_processed_ids(tmp_path):
    """Tests the logic for loading already processed subject IDs."""
    scores_file = tmp_path / "scores.csv"

    # Case 1: No file exists
    assert load_processed_ids(scores_file) == set()

    # Case 2: Valid, modern file
    scores_content = (
        "Index,idADB,Name,BirthYear,EminenceScore\n"
        "1,101,Test A,1900,80.0\n"
        "2,102,Test B,1901,85.5\n"
    )
    scores_file.write_text(scores_content)
    assert load_processed_ids(scores_file) == {"101", "102"}

    # Case 3: Incompatible legacy file with 'ARN' column
    legacy_content = "Index,ARN,Name,BirthYear,EminenceScore\n1,101,Test A,1900,80.0\n"
    scores_file.write_text(legacy_content)
    with pytest.raises(SystemExit):
        load_processed_ids(scores_file)
        
    # Case 4: Malformed header with no valid ID column
    malformed_content = "Col1,Col2,Col3\n1,2,3\n"
    scores_file.write_text(malformed_content)
    with pytest.raises(SystemExit):
        load_processed_ids(scores_file)


@pytest.fixture
def mock_sandbox_with_bypass_config(mock_main_sandbox: Path) -> Path:
    """Creates a mock config.ini with bypass_candidate_selection set to true."""
    config_content = (
        "[DataGeneration]\n"
        "bypass_candidate_selection = true\n"
    )
    (mock_main_sandbox / "config.ini").write_text(config_content)
    return mock_main_sandbox


@pytest.fixture
def mock_main_sandbox(tmp_path: Path) -> Path:
    """Creates a temporary sandbox with mock input files for the main orchestrator test."""
    # Define paths relative to the sandbox root
    input_dir = tmp_path / "data" / "intermediate"
    output_dir = tmp_path / "data" / "foundational_assets"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    input_file = input_dir / "adb_eligible_candidates.txt"
    
    input_content = (
        "idADB\tFirstName\tLastName\tYear\n"
        "101\tTest\tA\t1950\n"
        "102\tTest\tB\t1951\n"
    )
    input_file.write_text(input_content)
    
    return tmp_path

def test_main_orchestrator_loop(mocker, mock_main_sandbox):
    """
    Tests the main orchestrator loop by mocking the subprocess call to the LLM worker.
    """
    sandbox_path = mock_main_sandbox
    output_path = sandbox_path / "data" / "foundational_assets" / "eminence_scores.csv"
    
    # Mock the subprocess.run call to simulate the LLM worker
    mock_subprocess = mocker.patch('subprocess.run')
    
    # Mock the functions that generate reports to isolate the main loop logic
    mocker.patch('src.generate_eminence_scores.sort_and_reindex_scores')
    mocker.patch('src.generate_eminence_scores.generate_scores_summary')

    def subprocess_side_effect(*args, **kwargs):
        """Simulates the worker creating a response file."""
        # The worker script gets the output file path from its arguments
        worker_cmd = args[0]
        response_file_arg_index = worker_cmd.index("--output_response_file") + 1
        response_file_path = Path(worker_cmd[response_file_arg_index])
        
        # Write a dummy response that our parser can handle
        response_text = '"Test A (1950), ID 101: 85.0"\n"Test B (1951), ID 102: 88.0"'
        response_file_path.write_text(response_text)
        return MagicMock(returncode=0)

    mock_subprocess.side_effect = subprocess_side_effect

    # Run the main function with mocked args
    test_args = [
        "generate_eminence_scores.py",
        "--sandbox-path", str(sandbox_path),
        "--batch-size", "2",
        "--force" # Use force to simplify the test by ensuring a fresh run
    ]
    with patch("sys.argv", test_args):
        main()

    # Assertions
    assert mock_subprocess.call_count == 1 # One batch of 2 subjects
    assert output_path.exists()
    
    with open(output_path, 'r') as f:
        content = f.read()
        assert "101,Test A,1950,85.0" in content
        assert "102,Test B,1951,88.0" in content


def test_eminence_scores_warns_in_bypass_mode(mock_sandbox_with_bypass_config):
    """
    Tests that the script warns the user and exits if bypass is active
    and the user declines to proceed.
    """
    sandbox_path = mock_sandbox_with_bypass_config
    
    # Mock user input to be 'n' and simulate an interactive terminal
    with patch("builtins.input", return_value="n"), \
         patch("sys.stdout.isatty", return_value=True):
        test_args = [
            "generate_eminence_scores.py",
            "--sandbox-path", str(sandbox_path),
        ]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 0 # Should be a graceful exit

# === End of tests/data_preparation/test_generate_eminence_scores.py ===

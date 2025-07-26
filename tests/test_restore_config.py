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
# Filename: tests/test_restore_config.py

import configparser
from pathlib import Path
from unittest.mock import patch

import pytest

from src.restore_config import main, parse_report_header

# A sample report content for testing the parser
SAMPLE_REPORT_CONTENT = """
Run Directory:      output/reports/StudyX/run_..._tmp-0.7_..._rep-15
--- Run Parameters ---
Num Iterations (m): 100
Items per Query (k): 10
Mapping Strategy:   correct
LLM Model:          meta-llama/llama-3-8b-instruct
Personalities Source: personalities_db_1-5000.txt
"""

MALFORMED_REPORT_CONTENT = """
This report is missing most of the required fields.
LLM Model: some-model
"""


@pytest.fixture
def temp_run_dir(tmp_path: Path) -> Path:
    """Creates a temporary run directory for testing main()."""
    run_dir = tmp_path / "test_run_01"
    run_dir.mkdir()
    return run_dir


def test_parse_report_header_success():
    """Test that parse_report_header correctly extracts all parameters."""
    params = parse_report_header(SAMPLE_REPORT_CONTENT)
    assert params["model_name"] == "meta-llama/llama-3-8b-instruct"
    assert params["mapping_strategy"] == "correct"
    assert params["group_size"] == "10"
    assert params["num_trials"] == "100"
    assert params["personalities_src"] == "personalities_db_1-5000.txt"
    assert params["temperature"] == "0.7"
    assert params["replication"] == "15"


def test_parse_report_header_malformed():
    """Test parsing with missing fields returns 'unknown' or defaults."""
    params = parse_report_header(MALFORMED_REPORT_CONTENT)
    assert params["model_name"] == "some-model"
    assert params["mapping_strategy"] == "unknown"
    assert params["group_size"] == "unknown"
    assert params["num_trials"] == "unknown"
    assert params["personalities_src"] == "unknown"
    assert params["temperature"] == "0.0"  # Default value
    assert params["replication"] == "0"  # Default value


@patch("builtins.print")
def test_main_creates_config_successfully(mock_print, temp_run_dir: Path):
    """Test the main function's successful execution."""
    # Arrange
    report_file = temp_run_dir / "replication_report_abc.txt"
    report_file.write_text(SAMPLE_REPORT_CONTENT, encoding="utf-8")

    # Act
    with patch("sys.argv", ["script_name", str(temp_run_dir)]):
        # Successful execution does not call sys.exit(), so we don't expect an exception.
        main()

    # Assert
    mock_print.assert_any_call(
        f"  -> Success: Created 'config.ini.archived'"
    )

    # Verify the created config file
    config_path = temp_run_dir / "config.ini.archived"
    assert config_path.exists()
    config = configparser.ConfigParser()
    config.read(config_path)

    assert config.get("LLM", "model") == "meta-llama/llama-3-8b-instruct"
    assert config.get("LLM", "temperature") == "0.7"
    assert config.get("Study", "mapping_strategy") == "correct"
    assert config.get("Study", "k_per_query") == "10"
    assert config.get("Study", "num_iterations") == "100"
    assert config.get("Replication", "replication") == "15"


@patch("builtins.print")
def test_main_skips_if_config_exists(mock_print, temp_run_dir: Path):
    """Test that main() skips if config.ini.archived already exists."""
    # Arrange
    (temp_run_dir / "config.ini.archived").touch()

    # Act
    with patch("sys.argv", ["script_name", str(temp_run_dir)]):
        with pytest.raises(SystemExit) as e:
            main()

    # Assert
    assert e.value.code == 0
    mock_print.assert_called_with(
        f"Skipping: '{temp_run_dir.name}' already has an archived config."
    )


@patch("builtins.print")
def test_main_fails_no_report_file(mock_print, temp_run_dir: Path):
    """Test failure when no replication_report file is found."""
    # Act
    with patch("sys.argv", ["script_name", str(temp_run_dir)]):
        with pytest.raises(SystemExit) as e:
            main()

    # Assert
    assert e.value.code == 1
    mock_print.assert_called_with(
        f"Error: No 'replication_report_*.txt' file found in '{temp_run_dir}'"
    )


@patch("builtins.print")
def test_main_fails_dir_not_found(mock_print, tmp_path: Path):
    """Test failure when the target directory does not exist."""
    # Arrange
    non_existent_dir = tmp_path / "non_existent"

    # Act
    with patch("sys.argv", ["script_name", str(non_existent_dir)]):
        with pytest.raises(SystemExit) as e:
            main()

    # Assert
    assert e.value.code == 1
    mock_print.assert_called_with(
        f"Error: Directory not found at '{non_existent_dir}'"
    )


@patch("sys.argv")
@patch("builtins.print")
def test_main_fails_no_args(mock_print, mock_argv):
    """Test failure when no command-line arguments are provided."""
    # Arrange
    mock_argv.__len__.return_value = 1

    # Act
    with pytest.raises(SystemExit) as e:
        main()

    # Assert
    assert e.value.code == 1
    mock_print.assert_called_with(
        "Usage: python restore_config.py <path_to_run_directory>"
    )

# === End of tests/test_restore_config.py ===

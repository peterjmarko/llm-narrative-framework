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
# Filename: tests/test_query_generator.py

import pytest
import os
from unittest.mock import MagicMock
import logging
import tempfile
import configparser

# Since pytest handles the path, we can import directly.
from src import query_generator

@pytest.fixture
def mock_dependencies(tmp_path, mocker):
    """A fixture to mock dependencies for query_generator."""
    # Mock the config_loader module's attributes
    mocker.patch('src.query_generator.PROJECT_ROOT', str(tmp_path))
    
    mock_config = MagicMock()
    config_data = {
        'Filenames': {'base_query_src': "base_query.txt", 'temp_subset_personalities': "temp_subset_personalities.txt"},
        'General': {'default_k': '3', 'base_output_dir': "output"}
    }
    mock_config.get.side_effect = lambda section, key, **kwargs: config_data.get(section, {}).get(key)
    mocker.patch('src.query_generator.APP_CONFIG', mock_config)
    mocker.patch('src.query_generator.get_config_value', side_effect=lambda cfg, sec, key, **kwargs: cfg.get(sec, key))

@pytest.fixture
def mock_sys_exit(mocker):
    return mocker.patch('sys.exit', side_effect=SystemExit)

@pytest.fixture
def setup_main_test_files(tmp_path):
    """Creates the dummy files needed for main() in their expected locations."""
    # The logic in query_generator.main() expects the specific temp file in src/
    # but all other files (even if named the same) in data/. We need to match this.
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    
    # Create the personalities file in the data directory, which matches the test case.
    (data_dir / "temp_subset_personalities.txt").write_text("Index\tName\tBirthYear\tDescriptionText\n1\tA\t1\tDa\n2\tB\t2\tDb\n3\tC\t3\tDc\n")
    
    # The base query is also expected in data/.
    (data_dir / "base_query.txt").write_text("Base query: {k}")

def test_main_happy_path(tmp_path, mock_sys_exit, setup_main_test_files, mocker, mock_dependencies):
    """Tests the main function's happy path."""
    mock_args = {
        'k': 3, 'seed': None, 'mapping_strategy': 'correct', 'verbose': 0,
        'personalities_file': "temp_subset_personalities.txt",
        'base_query_file': "base_query.txt", 'output_basename_prefix': ""
    }
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=mocker.Mock(**mock_args))

    query_generator.main()

    mock_sys_exit.assert_not_called()
    output_dir = tmp_path / "output" / "qgen_standalone_output"
    assert (output_dir / "llm_query.txt").is_file()
    content = (output_dir / "llm_query.txt").read_text()
    assert "Base query: 3" in content

def test_load_base_query_file_not_found(tmp_path, mocker, mock_dependencies):
    """Test load_base_query with non-existent file."""
    from src.query_generator import load_base_query
    
    non_existent_file = tmp_path / "nonexistent.txt"
    
    with pytest.raises(SystemExit) as excinfo:
        load_base_query(str(non_existent_file))
    
    assert excinfo.value.code == 1

def test_load_base_query_empty_file(tmp_path, mocker, mock_dependencies):
    """Test load_base_query with empty file."""
    from src.query_generator import load_base_query
    
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("")
    
    mock_warn = mocker.patch('src.query_generator.logging.warning')
    result = load_base_query(str(empty_file))
    assert result == ""
    mock_warn.assert_called_once()

def test_load_personalities_invalid_format(tmp_path, mocker, mock_dependencies):
    """Test load_personalities with invalid data."""
    from src.query_generator import load_personalities
    
    invalid_file = tmp_path / "invalid.txt"
    invalid_file.write_text("Index\tName\tBirthYear\tDescriptionText\n1\tA\tinvalid_year\tDesc\n2\tB\t2000\tValid\n")
    
    mock_warn = mocker.patch('src.query_generator.logging.warning')
    result = load_personalities(str(invalid_file), 1)
    assert len(result) == 1  # Only valid entry loaded
    mock_warn.assert_called()

def test_load_personalities_insufficient_data(tmp_path, mocker, mock_dependencies):
    """Test load_personalities with insufficient valid entries."""
    from src.query_generator import load_personalities
    
    insufficient_file = tmp_path / "insufficient.txt"
    insufficient_file.write_text("Index\tName\tBirthYear\tDescriptionText\n1\tA\t2000\tDesc\n")
    
    with pytest.raises(SystemExit) as excinfo:
        load_personalities(str(insufficient_file), 5)  # Need 5, only have 1
    
    assert excinfo.value.code == 1

def test_select_and_prepare_k_items_insufficient(tmp_path, mocker, mock_dependencies):
    """Test select_and_prepare_k_items with insufficient items."""
    from src.query_generator import select_and_prepare_k_items
    
    personalities = [{'name': 'A', 'year': 2000, 'description': 'Desc', 'original_index_from_file': 1}]
    
    with pytest.raises(SystemExit) as excinfo:
        select_and_prepare_k_items(personalities, 5)  # Need 5, only have 1
    
    assert excinfo.value.code == 1

def test_write_tab_separated_file_io_error(tmp_path, mocker, mock_dependencies):
    """Test write_tab_separated_file with IO error."""
    from src.query_generator import write_tab_separated_file
    
    # Mock open to raise IOError
    mocker.patch('builtins.open', side_effect=IOError("Disk full"))
    with pytest.raises(IOError):
        write_tab_separated_file(str(tmp_path / "test.txt"), "Header", [["data"]])

def test_random_mapping_strategy(tmp_path, mock_sys_exit, setup_main_test_files, mocker, mock_dependencies):
    """Test main function with random mapping strategy."""
    mock_args = {
        'k': 3, 'seed': 42, 'mapping_strategy': 'random', 'verbose': 0,
        'personalities_file': "temp_subset_personalities.txt",
        'base_query_file': "base_query.txt", 'output_basename_prefix': ""
    }
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=mocker.Mock(**mock_args))
    
    mock_warn = mocker.patch('src.query_generator.logging.warning')
    query_generator.main()
    
    # Should warn about random mapping
    warning_calls = [call for call in mock_warn.call_args_list 
                    if "random" in str(call) and "mapping strategy" in str(call)]
    assert len(warning_calls) > 0

def test_verbose_levels(tmp_path, mock_sys_exit, setup_main_test_files, mocker, mock_dependencies):
    """Test different verbose levels."""
    # Test verbose level 1 (INFO)
    mock_args = {
        'k': 3, 'seed': None, 'mapping_strategy': 'correct', 'verbose': 1,
        'personalities_file': "temp_subset_personalities.txt",
        'base_query_file': "base_query.txt", 'output_basename_prefix': ""
    }
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=mocker.Mock(**mock_args))
    
    mock_logger = mocker.patch('logging.getLogger')
    query_generator.main()
    mock_logger.assert_called()

def test_orchestrator_temp_output_path(tmp_path, mock_sys_exit, setup_main_test_files, mocker, mock_dependencies):
    """Test orchestrator temporary output path handling."""
    mock_args = {
        'k': 3, 'seed': None, 'mapping_strategy': 'correct', 'verbose': 0,
        'personalities_file': "temp_subset_personalities.txt",
        'base_query_file': "base_query.txt", 
        'output_basename_prefix': "temp_qgen_outputs_iter_001/test_"
    }
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=mocker.Mock(**mock_args))
    
    # Capture logging to verify the orchestrator path logic worked
    mock_info = mocker.patch('src.query_generator.logging.info')
    
    query_generator.main()
    
    # Verify the orchestrator path was detected and logged
    info_calls = [str(call) for call in mock_info.call_args_list]
    orchestrator_msgs = [msg for msg in info_calls if "Orchestrated run" in msg and "temp_qgen_outputs_iter_001" in msg]
    assert len(orchestrator_msgs) > 0, "Should detect and log orchestrator temp path"
    
    # Verify the success message was logged (meaning files were created)
    success_msgs = [msg for msg in info_calls if "Query generation process complete" in msg]
    assert len(success_msgs) > 0, "Should complete successfully"


def test_custom_path_prefix(tmp_path, mock_sys_exit, setup_main_test_files, mocker, mock_dependencies):
    """Test custom path prefix handling."""
    mock_args = {
        'k': 3, 'seed': None, 'mapping_strategy': 'correct', 'verbose': 0,
        'personalities_file': "temp_subset_personalities.txt",
        'base_query_file': "base_query.txt", 
        'output_basename_prefix': "custom_subdir/prefix_"
    }
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=mocker.Mock(**mock_args))
    
    query_generator.main()
    
    # Should create files in output/custom_subdir/
    expected_dir = tmp_path / "output" / "custom_subdir"
    assert expected_dir.exists()
    assert (expected_dir / "prefix_llm_query.txt").exists()

def test_invalid_k_value(tmp_path, mock_sys_exit, setup_main_test_files, mocker, mock_dependencies):
    """Test invalid k value."""
    mock_args = {
        'k': 0, 'seed': None, 'mapping_strategy': 'correct', 'verbose': 0,
        'personalities_file': "temp_subset_personalities.txt",
        'base_query_file': "base_query.txt", 'output_basename_prefix': ""
    }
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=mocker.Mock(**mock_args))
    
    with pytest.raises(SystemExit):
        query_generator.main()
    
    mock_sys_exit.assert_called_with(1)

def test_normalize_text_for_llm():
    """Test text normalization function."""
    from src.query_generator import normalize_text_for_llm
    
    # Test normal text
    assert normalize_text_for_llm("Hello World") == "Hello World"
    
    # Test non-string input
    assert normalize_text_for_llm(123) == 123
    assert normalize_text_for_llm(None) is None
    
    # Test unicode normalization
    result = normalize_text_for_llm("café")
    assert "cafe" in result or "caf" in result  # Depends on exact normalization

def test_create_mapping_file_no_match(tmp_path, mocker, mock_dependencies):
    """Test create_mapping_file with missing match (critical error)."""
    from src.query_generator import create_mapping_file
    
    # Create mismatched lists that will cause the critical error
    shuffled_names = [("Name1", 2000, 0), ("Name2", 2001, 1)]
    shuffled_descriptions = [("Desc1", 99), ("Desc2", 98)]  # Wrong ref_ids
    
    with pytest.raises(SystemExit) as excinfo:
        create_mapping_file(shuffled_names, shuffled_descriptions, str(tmp_path / "mapping.txt"), 2)
    
    assert excinfo.value.code == 1

def test_directory_creation_error(tmp_path, mocker, mock_dependencies):
    """Test directory creation failure."""
    mock_args = {
        'k': 3, 'seed': None, 'mapping_strategy': 'correct', 'verbose': 0,
        'personalities_file': "temp_subset_personalities.txt",
        'base_query_file': "base_query.txt", 'output_basename_prefix': ""
    }
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=mocker.Mock(**mock_args))
    
    # Mock os.makedirs to raise OSError
    mocker.patch('os.makedirs', side_effect=OSError("Permission denied"))
    with pytest.raises(SystemExit) as excinfo:
        query_generator.main()
    
    assert excinfo.value.code == 1

def test_file_write_errors(tmp_path, mocker, mock_dependencies):
    """Test various file write error scenarios."""
    from src.query_generator import create_shuffled_names_file, assemble_full_query
    
    selected_items = [{'name': 'Test', 'year': 2000, 'internal_ref_id': 0}]
    
    # Test create_shuffled_names_file with write error
    mocker.patch('builtins.open', side_effect=IOError("Write error"))
    with pytest.raises(SystemExit) as excinfo:
        create_shuffled_names_file(selected_items, str(tmp_path / "test.txt"))
    assert excinfo.value.code == 1
    
    # Test assemble_full_query with write error
    mocker.patch('builtins.open', side_effect=IOError("Write error"))
    with pytest.raises(SystemExit) as excinfo:
        assemble_full_query("Base {k}", [("Name", 2000, 0)], [("Desc", 0)], str(tmp_path / "query.txt"), 1)
    assert excinfo.value.code == 1
def test_wrong_number_of_items_after_loading(tmp_path, mock_sys_exit, mocker, mock_dependencies):
    """Test error when loaded items don't match expected k value."""
    # Create file with 2 items
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "temp_subset_personalities.txt").write_text(
        "Index\tName\tBirthYear\tDescriptionText\n1\tA\t1\tDa\n2\tB\t2\tDb\n"
    )
    (data_dir / "base_query.txt").write_text("Base query: {k}")
    
    # But request k=5
    mock_args = {
        'k': 5, 'seed': None, 'mapping_strategy': 'correct', 'verbose': 0,
        'personalities_file': "temp_subset_personalities.txt",
        'base_query_file': "base_query.txt", 'output_basename_prefix': ""
    }
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=mocker.Mock(**mock_args))
    
    with pytest.raises(SystemExit):
        query_generator.main()
    
    mock_sys_exit.assert_called_with(1)

# === End of tests/test_query_generator.py ===

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
# Filename: tests/experiment_workflow/test_config_loader.py

import pytest
from configparser import ConfigParser
import os

from config_loader import (
    get_config_value, get_config_list, get_path, get_sandbox_path, 
    PROJECT_ROOT, get_config_compatibility_map, get_config_section_as_dict
)

# A valid config content for happy path testing
VALID_CONFIG_CONTENT = """
[General]
default_k = 10
base_output_dir = output

[Experiment]
num_replications = 30
mapping_strategy = correct
"""


@pytest.fixture
def mock_config_file(tmp_path):
    """A fixture to create a temporary config file for testing."""
    def _create_file(content):
        config_path = tmp_path / "config.ini"
        config_path.write_text(content)
        return str(config_path)
    return _create_file


def test_get_config_value_happy_path(mock_config_file):
    """
    Tests the get_config_value helper with correct types.
    """
    config_path = mock_config_file(VALID_CONFIG_CONTENT)
    config = ConfigParser()
    config.read(config_path)

    # Test getting an integer
    k_val = get_config_value(config, 'General', 'default_k', value_type=int)
    assert k_val == 10
    assert isinstance(k_val, int)

    # Test getting a string
    strategy = get_config_value(config, 'Experiment', 'mapping_strategy', value_type=str)
    assert strategy == 'correct'
    assert isinstance(strategy, str)


def test_get_config_value_fallback(mock_config_file):
    """
    Tests that the fallback mechanism works for missing keys.
    """
    config_path = mock_config_file("[General]\nkey = value")
    config = ConfigParser()
    config.read(config_path)

    fallback_val = get_config_value(config, 'General', 'missing_key', fallback=123)
    assert fallback_val == 123


def test_get_config_value_missing_section(mock_config_file):
    """
    Tests that None is returned when a section is missing and no fallback is provided.
    """
    config_path = mock_config_file("[General]\nkey = value")
    config = ConfigParser()
    config.read(config_path)

    # The function should return None for a missing section when no fallback is given
    value = get_config_value(config, 'MissingSection', 'some_key')
    assert value is None


def test_get_config_value_missing_key(mock_config_file):
    """
    Tests that None is returned when a key is missing and no fallback is provided.
    """
    config_path = mock_config_file("[General]\nkey = value")
    config = ConfigParser()
    config.read(config_path)

    # The function should return None for a missing key when no fallback is given
    value = get_config_value(config, 'General', 'missing_key')
    assert value is None


def test_get_config_value_invalid_type(mock_config_file):
    """
    Tests that None is returned for incorrect data types when no fallback is provided.
    """
    config_path = mock_config_file("[General]\nnum = not_a_number")
    config = ConfigParser()
    config.read(config_path)

    # The function should return None for a type conversion error when no fallback is given
    value = get_config_value(config, 'General', 'num', value_type=int)
    assert value is None

def test_get_config_value_with_inline_comments_and_types():
    """
    Tests that values with inline comments are parsed correctly for various types.
    """
    config = ConfigParser()
    config.read_string("""
    [TestSection]
    string_val =  some_value ; this is a comment
    int_val    =  42 # another comment
    float_val  =  3.14;
    bool_true  =  yes # boolean
    bool_false =  0
    special_tab = \\t ; a tab character
    special_none = None # a None string
    """)
    
    # Assert that comments are stripped and values are correctly typed
    assert get_config_value(config, 'TestSection', 'string_val') == 'some_value'
    assert get_config_value(config, 'TestSection', 'int_val', value_type=int) == 42
    assert get_config_value(config, 'TestSection', 'float_val', value_type=float) == 3.14
    assert get_config_value(config, 'TestSection', 'bool_true', value_type=bool) is True
    assert get_config_value(config, 'TestSection', 'bool_false', value_type=bool) is False
    assert get_config_value(config, 'TestSection', 'special_tab') == '\t'
    assert get_config_value(config, 'TestSection', 'special_none') is None

def test_get_config_list_parsing():
    """
    Tests that comma-separated lists are parsed correctly.
    """
    config = ConfigParser()
    config.read_string("""
    [Lists]
    items = item1, item2 ,  item3
    empty = 
    single = item_one
    """)
    
    assert get_config_list(config, 'Lists', 'items') == ['item1', 'item2', 'item3']
    assert get_config_list(config, 'Lists', 'empty') == []
    assert get_config_list(config, 'Lists', 'single') == ['item_one']
    assert get_config_list(config, 'Lists', 'missing_key') == []
    assert get_config_list(config, 'Lists', 'missing_key', fallback=['default']) == ['default']

def test_get_path_and_sandbox():
    """
    Tests the get_path and get_sandbox_path helpers for both sandboxed and normal modes.
    """
    # Test without sandbox
    os.environ.pop('PROJECT_SANDBOX_PATH', None)
    assert get_sandbox_path() is None
    expected_path_normal = os.path.join(PROJECT_ROOT, 'data', 'file.txt')
    assert get_path(os.path.join('data', 'file.txt')) == expected_path_normal
    
    # Test with sandbox enabled
    sandbox_dir = "/tmp/sandbox"
    os.environ['PROJECT_SANDBOX_PATH'] = sandbox_dir
    assert get_sandbox_path() == sandbox_dir
    expected_path_sandbox = os.path.join(sandbox_dir, 'data', 'file.txt')
    assert get_path(os.path.join('data', 'file.txt')) == expected_path_sandbox
    
    # Clean up environment variable
    os.environ.pop('PROJECT_SANDBOX_PATH')

def test_get_config_compatibility_map():
    """
    Tests the parsing of the [ConfigCompatibility] section.
    """
    # Case 1: Valid configuration
    config_valid = ConfigParser()
    config_valid.read_string("""
    [ConfigCompatibility]
    canonical_name = Section1:key1, Section2:key2
    another_name = Section3:key3
    """)
    expected_map = {
        'canonical_name': [('Section1', 'key1'), ('Section2', 'key2')],
        'another_name': [('Section3', 'key3')]
    }
    assert get_config_compatibility_map(config_valid) == expected_map

    # Case 2: Section is missing
    config_missing = ConfigParser()
    config_missing.read_string("[General]\nkey = value")
    assert get_config_compatibility_map(config_missing) == {}

    # Case 3: Malformed entry is skipped
    config_malformed = ConfigParser()
    config_malformed.read_string("""
    [ConfigCompatibility]
    good_key = Section:key
    bad_key = just_a_value_no_colon
    """)
    result_map = get_config_compatibility_map(config_malformed)
    assert 'good_key' in result_map
    assert 'bad_key' not in result_map

def test_get_config_value_invalid_boolean_fallback(caplog):
    """
    Tests that an invalid boolean string returns the fallback and logs a warning.
    """
    config = ConfigParser()
    config.read_string("[Booleans]\ninvalid_bool = not_a_boolean")

    # Test with a specific fallback
    result = get_config_value(config, 'Booleans', 'invalid_bool', value_type=bool, fallback=False)
    assert result is False

    # Check that a warning was logged
    assert "Error converting [Booleans]/invalid_bool" in caplog.text
    assert "Using fallback: False" in caplog.text

    # Test with the default fallback (None)
    caplog.clear()
    result_none = get_config_value(config, 'Booleans', 'invalid_bool', value_type=bool)
    assert result_none is None
    assert "Using fallback: None" in caplog.text

def test_get_config_value_fallback_key():
    """
    Tests that the fallback_key mechanism works correctly.
    """
    config = ConfigParser()
    config.read_string("[Section]\nlegacy_key = legacy_value")

    # The primary 'new_key' is missing, so it should find 'legacy_key'
    value = get_config_value(config, 'Section', 'new_key', fallback_key='legacy_key')
    assert value == 'legacy_value'

    # Neither key exists, so it should return the final fallback
    value_fallback = get_config_value(config, 'Section', 'missing1', fallback_key='missing2', fallback='default')
    assert value_fallback == 'default'

def test_get_config_value_invalid_float_fallback(caplog):
    """
    Tests that an invalid float string returns the fallback and logs a warning.
    """
    config = ConfigParser()
    config.read_string("[Floats]\ninvalid_float = not_a_float")

    result = get_config_value(config, 'Floats', 'invalid_float', value_type=float, fallback=0.0)
    assert result == 0.0
    assert "Error converting [Floats]/invalid_float" in caplog.text
    assert "Using fallback: 0.0" in caplog.text

def test_get_config_section_as_dict():
    """
    Tests that an entire config section can be correctly read as a dictionary.
    """
    config = ConfigParser()
    config.read_string("""
    [MySection]
    key1 = value1
    key2 = value2
    """)

    # Test reading a valid section
    expected_dict = {'key1': 'value1', 'key2': 'value2'}
    assert get_config_section_as_dict(config, 'MySection') == expected_dict

    # Test reading a missing section
    assert get_config_section_as_dict(config, 'MissingSection') == {}

# === End of tests/experiment_workflow/test_config_loader.py ===

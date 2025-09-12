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
# Filename: tests/test_config_loader.py

import pytest
from configparser import ConfigParser

from config_loader import get_config_value

# A valid config content for happy path testing
VALID_CONFIG_CONTENT = """
[General]
default_k = 10
base_output_dir = output

[Study]
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
    strategy = get_config_value(config, 'Study', 'mapping_strategy', value_type=str)
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

# === End of tests/test_config_loader.py ===

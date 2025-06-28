#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: tests/test_config_loader.py

"""
Unit Tests for the Configuration Loader (config_loader.py)

Purpose:
This script tests the core functionality of the `config_loader.py` module, which is
responsible for finding the project's root directory, loading the `config.ini` file,
and providing a typed-access interface to its values.

Given that `config_loader` is a foundational module imported by nearly every other
script in the pipeline, ensuring its reliability is critical. These tests validate
its logic in an isolated environment.

Key Test Areas:
-   **`get_config_value` Function**:
    -   **Happy Path**: Verifies that the function correctly retrieves and casts
      configuration values to their expected types (string, integer, float, boolean).
      It also tests the handling of inline comments.
    -   **Fallback Logic**: Ensures the function returns the specified `fallback`
      value gracefully under various failure conditions:
        - When the requested section is missing from the config.
        - When the requested key is missing from a section.
        - When a value cannot be cast to the requested type (e.g., parsing "abc"
          as an integer).

-   **`load_app_config` Function**:
    -   Tests the file discovery mechanism. It uses mocks to simulate the presence
      of `config.ini` and asserts that the loader correctly attempts to read it from
      the expected location (e.g., the current working directory).

-   **`PROJECT_ROOT` Constant**:
    -   Performs a basic sanity check to confirm that the auto-detected `PROJECT_ROOT`
      is a valid, existing directory and appears to be the correct project folder by
      checking for the presence of a key file (`src/config_loader.py`).

Test Strategy & Mocks:
-   **Direct Import**: Unlike other tests that mock `config_loader`, this script
    imports the module directly to test its actual functions.
-   **Temporary Directory**: Each test runs in a temporary working directory created
    by `tempfile.TemporaryDirectory` to isolate file system operations.
-   **In-Memory Config**: The tests for `get_config_value` use an in-memory
    `configparser.ConfigParser` object, allowing for precise control over the test
    data without needing to write physical `.ini` files.
-   **File System Mocking**: The test for `load_app_config` uses `unittest.mock.patch`
    to mock `os.path.exists` and `configparser.ConfigParser.read`, isolating the
    test from the actual file system and focusing purely on the path-finding logic.
"""

# === Start of tests/test_config_loader.py ===

import unittest
from unittest.mock import patch, mock_open
import os
import tempfile
import configparser

# Since we are testing config_loader itself, we import it directly.
# This requires the test runner (e.g., pytest) to handle the path.
from config_loader import get_config_value, load_app_config, PROJECT_ROOT

class TestConfigLoader(unittest.TestCase):

    def setUp(self):
        self.test_dir_obj = tempfile.TemporaryDirectory(prefix="test_config_loader_")
        self.test_dir = self.test_dir_obj.name
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.test_dir_obj.cleanup()

    def test_get_config_value_happy_paths(self):
        """Test retrieving values of different types correctly."""
        config = configparser.ConfigParser()
        config['TestSection'] = {
            'string_key': 'hello world',
            'int_key': '123',
            'float_key': '45.6',
            'true_key': 'yes',
            'false_key': 'off',
            'comment_key': 'value ; this is a comment'
        }
        
        self.assertEqual(get_config_value(config, 'TestSection', 'string_key'), 'hello world')
        self.assertEqual(get_config_value(config, 'TestSection', 'int_key', value_type=int), 123)
        self.assertEqual(get_config_value(config, 'TestSection', 'float_key', value_type=float), 45.6)
        self.assertTrue(get_config_value(config, 'TestSection', 'true_key', value_type=bool))
        self.assertFalse(get_config_value(config, 'TestSection', 'false_key', value_type=bool))
        self.assertEqual(get_config_value(config, 'TestSection', 'comment_key'), 'value')

    def test_get_config_value_fallbacks(self):
        """Test fallback behavior for missing sections, keys, or bad values."""
        config = configparser.ConfigParser()
        config['TestSection'] = {'int_key': 'not-an-int'}

        # Missing section
        self.assertEqual(get_config_value(config, 'MissingSection', 'key', fallback='default'), 'default')
        # Missing key
        self.assertEqual(get_config_value(config, 'TestSection', 'missing_key', fallback=99), 99)
        # Type conversion error
        self.assertEqual(get_config_value(config, 'TestSection', 'int_key', fallback=-1, value_type=int), -1)

    @patch('os.path.exists')
    @patch('configparser.ConfigParser.read')
    def test_load_app_config_finds_config_in_cwd(self, mock_read, mock_exists):
        """Test that config is loaded from CWD if present."""
        # Simulate that config.ini exists only in the current working directory
        def exists_side_effect(path):
            return os.path.basename(path) == 'config.ini' and self.test_dir in path
        mock_exists.side_effect = exists_side_effect
        
        load_app_config()
        
        mock_read.assert_called_once_with(os.path.join(self.test_dir, 'config.ini'))

    def test_project_root_detection(self):
        """Test if PROJECT_ROOT is a valid, existing directory."""
        # This is a simple sanity check
        self.assertTrue(os.path.isdir(PROJECT_ROOT))
        self.assertTrue(os.path.exists(os.path.join(PROJECT_ROOT, 'src', 'config_loader.py')))

# === End of tests/test_config_loader.py ===
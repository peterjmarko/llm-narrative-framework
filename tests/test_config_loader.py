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
# Filename: tests/test_config_loader.py

"""
Unit Tests for the Configuration Loader (config_loader.py)
"""

# === Start of tests/test_config_loader.py ===

import unittest
from unittest.mock import patch
import os
import tempfile
import configparser

# Import all necessary components from the module under test
from src.config_loader import (
    get_config_value, load_app_config, PROJECT_ROOT, get_project_root,
    load_env_vars, get_config_compatibility_map, get_config_list,
    get_config_section_as_dict
)

class TestConfigLoader(unittest.TestCase):
    """
    A single, unified test class for all config_loader functionality.
    Each test method is self-contained to prevent test pollution.
    """

    def setUp(self):
        """Set up a temporary directory for file system isolation."""
        self.test_dir_obj = tempfile.TemporaryDirectory(prefix="test_config_loader_")
        self.test_dir = self.test_dir_obj.name
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up the temporary directory."""
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

        self.assertEqual(get_config_value(config, 'MissingSection', 'key', fallback='default'), 'default')
        self.assertEqual(get_config_value(config, 'TestSection', 'missing_key', fallback=99), 99)
        self.assertEqual(get_config_value(config, 'TestSection', 'int_key', fallback=-1, value_type=int), -1)

    def test_get_config_value_edge_cases(self):
        """Test edge cases for get_config_value like fallback keys and special strings."""
        config = configparser.ConfigParser()
        config['TestSection'] = {
            'fallback_key': 'fallback_value',
            'true_key_fallback': 'true',
            'tab_key': r'\t',
            'none_key': 'None',
            'bad_float': 'not-a-float',
            'bad_bool': 'not-a-bool'
        }

        self.assertEqual(get_config_value(config, 'TestSection', 'missing_primary', fallback_key='fallback_key'), 'fallback_value')
        self.assertTrue(get_config_value(config, 'TestSection', 'missing_bool', value_type=bool, fallback_key='true_key_fallback'), 'Should use fallback key')
        self.assertEqual(get_config_value(config, 'TestSection', 'tab_key'), '\t')
        self.assertIsNone(get_config_value(config, 'TestSection', 'none_key'))

        with self.assertLogs('src.config_loader', level='WARNING') as cm:
            self.assertEqual(get_config_value(config, 'TestSection', 'bad_float', value_type=float, fallback=0.0), 0.0)
            self.assertTrue(len(cm.output) > 0, "Expected log output but got none")

        with self.assertLogs('src.config_loader', level='WARNING') as cm:
            self.assertEqual(get_config_value(config, 'TestSection', 'bad_bool', value_type=bool, fallback=True), True)
            self.assertTrue(len(cm.output) > 0, "Expected log output but got none")

        with self.assertLogs('src.config_loader', level='ERROR') as cm:
            self.assertEqual(get_config_value(config, 'TestSection', 'fallback_key', value_type=list, fallback=[]), [])
            self.assertTrue(len(cm.output) > 0, "Expected log output but got none")

    @patch('os.path.exists')
    @patch('configparser.ConfigParser.read')
    def test_load_app_config_finds_config_in_cwd(self, mock_read, mock_exists):
        """Test that config is loaded from CWD if present."""
        def exists_side_effect(path):
            return os.path.basename(path) == 'config.ini' and self.test_dir in path
        mock_exists.side_effect = exists_side_effect
        
        load_app_config()
        
        mock_read.assert_called_once_with(os.path.abspath(os.path.join(self.test_dir, 'config.ini')))

    @patch('os.path.exists')
    @patch('configparser.ConfigParser.read')
    def test_load_app_config_finds_config_in_project_root(self, mock_read, mock_exists):
        """Test that config is loaded from project root if not in CWD."""
        def exists_side_effect(path):
            if self.test_dir in path: return False
            return os.path.basename(path) == 'config.ini'
        mock_exists.side_effect = exists_side_effect
        
        load_app_config()
        expected_path = os.path.abspath(os.path.join(get_project_root(), 'config.ini'))
        mock_read.assert_called_once_with(expected_path)

    @patch('os.path.exists', return_value=False)
    def test_load_app_config_not_found(self, mock_exists):
        """Test that a warning is logged if config.ini is not found."""
        with self.assertLogs('src.config_loader', level='WARNING') as cm:
            load_app_config()
            self.assertTrue(len(cm.output) > 0, "Expected log output but got none")

    @patch('os.path.exists', return_value=True)
    @patch('configparser.ConfigParser.read', side_effect=configparser.Error("Mock parsing error"))
    def test_load_app_config_parsing_error(self, mock_read, mock_exists):
        """Test that an error is logged if config.ini is malformed."""
        with self.assertLogs('src.config_loader', level='ERROR') as cm:
            load_app_config()
            self.assertTrue(len(cm.output) > 0, "Expected log output but got none")

    @patch('src.config_loader.os.path.exists')
    @patch('src.config_loader.load_dotenv')
    def test_load_env_vars(self, mock_load_dotenv, mock_exists):
        """Test the three main branches of .env loading logic."""
        mock_exists.return_value = True
        mock_load_dotenv.return_value = True
        self.assertTrue(load_env_vars())

        mock_load_dotenv.return_value = False
        with self.assertLogs('src.config_loader', level='WARNING'):
            result = load_env_vars(); self.assertFalse(result, f"Expected False but got {result}")

        mock_exists.return_value = False
        with self.assertLogs('src.config_loader', level='INFO'):
            result = load_env_vars(); self.assertFalse(result, f"Expected False but got {result}")

    def test_project_root_detection(self):
        """Test if PROJECT_ROOT is a valid, existing directory."""
        self.assertTrue(os.path.isdir(PROJECT_ROOT))
        self.assertTrue(os.path.exists(os.path.join(PROJECT_ROOT, 'src', 'config_loader.py')))

    def test_get_config_list(self):
        """Test retrieving a comma-separated list."""
        config = configparser.ConfigParser()
        config.add_section('TestSection')
        config.set('TestSection', 'list_key', 'item1, item2, item3')
        config.set('TestSection', 'list_key_empty', '')

        expected = ['item1', 'item2', 'item3']
        self.assertEqual(get_config_list(config, 'TestSection', 'list_key'), expected)
        self.assertEqual(get_config_list(config, 'TestSection', 'missing_key', fallback=['default']), ['default'])
        self.assertEqual(get_config_list(config, 'TestSection', 'missing_key'), [])
        self.assertEqual(get_config_list(config, 'TestSection', 'list_key_empty'), [])

    def test_get_config_section_as_dict(self):
        """Test retrieving a section as a dictionary."""
        config = configparser.ConfigParser()
        config.add_section('TestSection')
        config.set('TestSection', 'key1', 'val1')
        config.set('TestSection', 'key2', 'val2')

        expected = {'key1': 'val1', 'key2': 'val2'}
        self.assertEqual(get_config_section_as_dict(config, 'TestSection'), expected)
        self.assertEqual(get_config_section_as_dict(config, 'MissingSection'), {})

    def test_get_config_compatibility_map(self):
        """Test parsing the compatibility map."""
        config = configparser.ConfigParser()
        config.add_section('ConfigCompatibility')
        config.set('ConfigCompatibility', 'canonical_name', 'GoodSection:good_key, BadSection:bad_key')
        config.set('ConfigCompatibility', 'bad_entry', 'this-is-malformed')

        expected_map = {
            'canonical_name': [('GoodSection', 'good_key'), ('BadSection', 'bad_key')]
        }
        with patch('builtins.print'):
            compat_map = get_config_compatibility_map(config)
        self.assertEqual(compat_map['canonical_name'], expected_map['canonical_name'])
        self.assertNotIn('bad_entry', compat_map)
        
        empty_config = configparser.ConfigParser()
        self.assertEqual(get_config_compatibility_map(empty_config), {})

# === End of tests/test_config_loader.py ===

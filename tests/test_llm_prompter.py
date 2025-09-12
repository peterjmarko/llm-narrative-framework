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
# Filename: tests/test_llm_prompter.py

"""
Unit Tests for the LLM Prompter Worker (llm_prompter.py).

This script validates the logic of the `llm_prompter.py` worker in isolation,
focusing on its handling of API calls and file I/O based on simulated outcomes.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile
import configparser
import types
import json
import requests
from pathlib import Path
import importlib

# Import the module to test
from src import llm_prompter

class TestLLMPrompter(unittest.TestCase):
    """Test suite for llm_prompter.py."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="llm_prompter_test_")
        self.project_root = self.test_dir.name
        
        self.query_file = Path(self.project_root) / "query.txt"
        self.response_file = Path(self.project_root) / "response.txt"
        self.error_file = Path(self.project_root) / "error.txt"
        self.json_file = Path(self.project_root) / "response_full.json"
        
        self.query_file.write_text("Test query")

        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'LLM': {
                'model_name': 'test-model', 'api_endpoint': 'http://fake-api.com/v1',
                'api_timeout_seconds': '10', 'referer_header': 'http://test.com',
                'max_tokens': '100', 'temperature': '0.1'
            }
        })
        
        fake_mod = types.ModuleType("config_loader")
        fake_mod.PROJECT_ROOT = self.project_root
        fake_mod.APP_CONFIG = self.mock_config
        def dummy_get_config_value(config, section, key, fallback=None, value_type=str, **kwargs):
            val = config.get(section, key, fallback=fallback)
            if val is None: return fallback
            return value_type(val)
        fake_mod.get_config_value = dummy_get_config_value
        
        self.config_patcher = patch.dict('sys.modules', {'config_loader': fake_mod})
        self.config_patcher.start()
        importlib.reload(llm_prompter)

        self.getenv_patcher = patch('src.llm_prompter.os.getenv', return_value='fake-api-key')
        self.mock_getenv = self.getenv_patcher.start()
        
        self.requests_patcher = patch('src.llm_prompter.requests.post')
        self.mock_requests_post = self.requests_patcher.start()
        
        self.sys_exit_patcher = patch('src.llm_prompter.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()
        self.mock_sys_exit.side_effect = SystemExit # Make it raise an exception

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.config_patcher.stop()
        self.getenv_patcher.stop()
        self.requests_patcher.stop()
        self.sys_exit_patcher.stop()

    def _get_base_argv(self):
        """Returns the base set of command-line arguments for a test run."""
        return [
            'llm_prompter.py',
            '001', # query_identifier
            '--input_query_file', str(self.query_file),
            '--output_response_file', str(self.response_file),
            '--output_error_file', str(self.error_file),
            '--output_json_file', str(self.json_file),
            '--quiet' # Suppress spinner for cleaner test logs
        ]

    def test_happy_path_success(self):
        """Verify correct file creation on a successful API call."""
        # --- Arrange ---
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "API success content"}}]
        }
        mock_response.raise_for_status.return_value = None
        self.mock_requests_post.return_value = mock_response
        
        test_argv = self._get_base_argv()

        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        # Assert correct files were created
        self.assertTrue(self.response_file.is_file())
        self.assertTrue(self.json_file.is_file())
        self.assertFalse(self.error_file.exists())
        
        # Assert file contents
        self.assertEqual(self.response_file.read_text(), "API success content")
        self.assertEqual(json.loads(self.json_file.read_text())['choices'][0]['message']['content'], "API success content")
        
        # Assert successful exit
        self.mock_sys_exit.assert_called_with(0)

    def test_api_http_error(self):
        """Verify error file creation on an HTTP error."""
        # --- Arrange ---
        self.mock_requests_post.side_effect = requests.exceptions.HTTPError("Simulated 500 Error")
        test_argv = self._get_base_argv()

        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        self.assertTrue(self.error_file.is_file())
        self.assertFalse(self.response_file.exists())
        self.assertIn("Simulated 500 Error", self.error_file.read_text())
        self.mock_sys_exit.assert_called_with(1)

    def test_api_timeout(self):
        """Verify error file creation on a connection timeout."""
        # --- Arrange ---
        self.mock_requests_post.side_effect = requests.exceptions.Timeout("Simulated Timeout")
        test_argv = self._get_base_argv()

        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        self.assertTrue(self.error_file.is_file())
        self.assertFalse(self.response_file.exists())
        self.assertIn("timed out", self.error_file.read_text())
        self.mock_sys_exit.assert_called_with(1)

    def test_input_file_not_found(self):
        """Verify graceful exit when the input query file is missing."""
        # --- Arrange ---
        self.query_file.unlink() # Delete the input file
        test_argv = self._get_base_argv()
        
        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        self.assertTrue(self.error_file.is_file())
        self.assertFalse(self.response_file.exists())
        self.assertIn("Input query file not found", self.error_file.read_text())
        self.mock_sys_exit.assert_called_with(1)

if __name__ == '__main__':
    unittest.main()

# === End of tests/test_llm_prompter.py ===

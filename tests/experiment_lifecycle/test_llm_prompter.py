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
# Filename: tests/experiment_lifecycle/test_llm_prompter.py

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

    def test_api_returns_malformed_json(self):
        """Verify error handling when the API returns a non-JSON response."""
        # --- Arrange ---
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        # Simulate a JSONDecodeError when .json() is called
        mock_response.json.side_effect = requests.exceptions.JSONDecodeError("Syntax error", "", 0)
        mock_response.text = "<html><body>502 Bad Gateway</body></html>"
        self.mock_requests_post.return_value = mock_response
        
        test_argv = self._get_base_argv()

        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        self.assertTrue(self.error_file.is_file())
        self.assertIn("Failed to decode JSON", self.error_file.read_text())
        self.assertIn("502 Bad Gateway", self.error_file.read_text())
        self.mock_sys_exit.assert_called_with(1)

    def test_api_returns_json_with_missing_content(self):
        """Verify graceful handling of valid JSON with an unexpected structure."""
        # --- Arrange ---
        mock_response = MagicMock()
        # Return a valid JSON structure but without the 'content' key
        mock_response.json.return_value = {"choices": [{"message": {"role": "assistant"}}]}
        mock_response.raise_for_status.return_value = None
        self.mock_requests_post.return_value = mock_response
        
        test_argv = self._get_base_argv()
        
        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        self.assertTrue(self.response_file.is_file())
        self.assertEqual(self.response_file.read_text(), "") # Response file should be created but empty
        self.assertTrue(self.json_file.is_file()) # Full JSON should still be saved
        self.mock_sys_exit.assert_called_with(0)

    def test_config_path_argument_is_used(self):
        """Verify that parameters from a --config_path file override the default."""
        # --- Arrange ---
        # Create a run-specific config file with a different model name
        specific_config = configparser.ConfigParser()
        specific_config.read_dict({'LLM': {'model_name': 'override-model'}})
        config_path = Path(self.project_root) / "specific_config.ini"
        with open(config_path, 'w') as f:
            specific_config.write(f)

        # Mock the API call to succeed
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Success"}}]}
        mock_response.raise_for_status.return_value = None
        self.mock_requests_post.return_value = mock_response
        
        test_argv = self._get_base_argv() + ['--config_path', str(config_path)]

        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        # Verify that requests.post was called with the overridden model name
        self.mock_requests_post.assert_called_once()
        _, kwargs = self.mock_requests_post.call_args
        self.assertEqual(kwargs['json']['model'], 'override-model')
        self.mock_sys_exit.assert_called_with(0)

    @patch('src.llm_prompter.call_openrouter_api', side_effect=KeyboardInterrupt)
    def test_keyboard_interrupt_handling(self, mock_api_call):
        """Verify the main try/except block catches KeyboardInterrupt."""
        # --- Arrange ---
        test_argv = self._get_base_argv()

        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        self.assertTrue(self.error_file.is_file())
        self.assertIn("Processing interrupted by user (Ctrl+C).", self.error_file.read_text())
        self.mock_sys_exit.assert_called_with(1)

    def test_mock_api_generic_exception(self):
        """Verify the --test_mock_api_outcome hook for a generic exception."""
        # --- Arrange ---
        # This test uses the script's internal mocking hooks, so we don't mock requests.post
        test_argv = self._get_base_argv() + [
            '--test_mock_api_outcome', 'generic_exception_in_api'
        ]

        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        self.assertTrue(self.error_file.is_file())
        self.assertIn("Unhandled error", self.error_file.read_text())
        self.assertIn("Simulated generic error", self.error_file.read_text())
        self.mock_sys_exit.assert_called_with(1)

    def test_mock_api_returns_none(self):
        """Verify the --test_mock_api_outcome hook for a None response."""
        # --- Arrange ---
        test_argv = self._get_base_argv() + [
            '--test_mock_api_outcome', 'api_returns_none'
        ]

        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        self.assertTrue(self.error_file.is_file())
        self.assertIn("LLM API call returned None", self.error_file.read_text())
        self.mock_sys_exit.assert_called_with(1)

    def test_mock_api_http_error_hook(self):
        """Verify the --test_mock_api_outcome hook for an HTTP 401 error."""
        # --- Arrange ---
        test_argv = self._get_base_argv() + [
            '--test_mock_api_outcome', 'api_http_401'
        ]

        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        self.assertTrue(self.error_file.is_file())
        self.assertIn("API call failed with HTTP error", self.error_file.read_text())
        self.assertIn("Simulated 401 Unauthorized", self.error_file.read_text())
        self.mock_sys_exit.assert_called_with(1)


class TestLLMPrompterInteractive(unittest.TestCase):
    """Test suite for llm_prompter.py's standalone interactive mode."""

    def setUp(self):
        """Set up a temporary directory and basic mocks."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="llm_prompter_interactive_")
        self.project_root = self.test_dir.name
        
        # We need to change the CWD to our temp dir to simulate running the script from there
        self.original_cwd = os.getcwd()
        os.chdir(self.project_root)

        # Patch abspath to make the script believe it's running from the temp directory.
        # This forces interactive mode files to be created in the test sandbox.
        self.abspath_patcher = patch('src.llm_prompter.os.path.abspath', return_value=os.path.join(self.project_root, 'llm_prompter.py'))
        self.mock_abspath = self.abspath_patcher.start()
        
        # Mock sys.exit to prevent test runner from exiting
        self.sys_exit_patcher = patch('src.llm_prompter.sys.exit', side_effect=SystemExit)
        self.mock_sys_exit = self.sys_exit_patcher.start()

    def tearDown(self):
        """Clean up and restore CWD."""
        os.chdir(self.original_cwd)
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()
        self.abspath_patcher.stop()

    @patch('src.llm_prompter.os.getenv', return_value=None)
    def test_interactive_mode_fails_without_api_key(self, mock_getenv):
        """Verify interactive mode exits if OPENROUTER_API_KEY is not set."""
        # --- Arrange ---
        # No arguments are passed to trigger interactive mode
        test_argv = ['llm_prompter.py']
        
        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()
        
        # Verify it writes to the default error file and exits
        error_file = Path(self.project_root) / "interactive_test_error.txt"
        self.assertTrue(error_file.is_file())
        self.assertIn("OPENROUTER_API_KEY not set", error_file.read_text())
        self.mock_sys_exit.assert_called_with(1)

    @patch('src.llm_prompter.os.getenv', return_value='fake-key')
    @patch('src.llm_prompter.requests.post')
    def test_interactive_mode_creates_sample_query_and_runs(self, mock_requests_post, mock_getenv):
        """Verify interactive mode creates a sample query file and makes an API call."""
        # --- Arrange ---
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Success"}}]}
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        test_argv = ['llm_prompter.py', '--interactive_test_mode']
        query_file = Path(self.project_root) / "interactive_test_query.txt"
        
        # Ensure the query file does NOT exist before the run
        self.assertFalse(query_file.exists())

        # --- Act & Assert ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                llm_prompter.main()

        # Verify the sample query file was created
        self.assertTrue(query_file.is_file())
        self.assertIn("capital of the Moon", query_file.read_text())
        
        # Verify the API call was made and the script exited successfully
        mock_requests_post.assert_called_once()
        self.mock_sys_exit.assert_called_with(0)


def tearDownModule():
    """Cleans up any interactive test artifacts that may have been created in the src/ directory."""
    print("\n--- Cleaning up llm_prompter test artifacts ---")
    # This logic correctly finds the src directory relative to this test file's location
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
    artifacts_to_remove = [
        "interactive_test_query.txt",
        "interactive_test_response.txt",
        "interactive_test_error.txt"
    ]
    for filename in artifacts_to_remove:
        file_path = os.path.join(src_dir, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Removed artifact: {file_path}")
            except OSError as e:
                print(f"Error removing artifact {file_path}: {e}")


if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_llm_prompter.py ===

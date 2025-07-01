# tests/test_inject_metadata.py

import unittest
import os
import tempfile
import subprocess
import sys
import pathlib
from unittest.mock import patch, mock_open
from io import StringIO

# Ensure the src directory is in the Python path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.inject_metadata import inject_metadata_into_report

# Define a standard report template for consistency
REPORT_TEMPLATE = """
---
Replication Report
---
Date: 2024-01-01
Personalities Source: standard_file.csv
---
"""

class TestInjectMetadata(unittest.TestCase):
    """
    Test suite for the inject_metadata.py script.
    """

    def setUp(self):
        """Set up a temporary directory with a nested structure for testing."""
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = self.temp_dir_obj.name

        # --- Create a realistic folder structure ---
        # Depth 0
        self.run_01_path = os.path.join(self.temp_dir, "run_01")
        os.makedirs(self.run_01_path)
        self.report_01_path = os.path.join(self.run_01_path, "replication_report_abc.txt")
        with open(self.report_01_path, 'w') as f:
            f.write(REPORT_TEMPLATE)

        # Depth 1
        level1_path = os.path.join(self.temp_dir, "level1")
        self.run_02_path = os.path.join(level1_path, "run_02")
        os.makedirs(self.run_02_path)
        self.report_02_path = os.path.join(self.run_02_path, "replication_report_def.txt")
        with open(self.report_02_path, 'w') as f:
            f.write(REPORT_TEMPLATE)

        # Depth 2
        level2_path = os.path.join(level1_path, "level2")
        self.run_03_path = os.path.join(level2_path, "run_03")
        os.makedirs(self.run_03_path)
        self.report_03_path = os.path.join(self.run_03_path, "replication_report_ghi.txt")
        with open(self.report_03_path, 'w') as f:
            f.write(REPORT_TEMPLATE)
            
        # A run directory with no report file to test skipping
        os.makedirs(os.path.join(self.temp_dir, "run_no_report"))

    def tearDown(self):
        """Clean up the temporary directory."""
        self.temp_dir_obj.cleanup()

    def _run_script(self, *args):
        """Helper function to run the script via subprocess."""
        script_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'inject_metadata.py')
        command = [sys.executable, script_path] + list(args)
        # The logging module writes to stderr by default.
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def _assert_injected(self, report_path, key, value):
        """Assert that the key-value pair was successfully injected."""
        with open(report_path, 'r') as f:
            content = f.read()
        self.assertIn(f"{key}: {value}", content)

    def _assert_not_injected(self, report_path, key):
        """Assert that the key-value pair was NOT injected."""
        with open(report_path, 'r') as f:
            content = f.read()
        self.assertNotIn(f"{key}:", content)

    # --- Integration Tests ---

    def test_depth_0_only_modifies_root(self):
        """Verify --depth 0 only processes the target directory."""
        result = self._run_script(self.temp_dir, "--key", "TestKey", "--value", "TestValue", "--depth", "0")
        # FIX: Check stderr for logging output
        self.assertIn("Successfully updated 1 of 1 reports", result.stderr)
        self._assert_injected(self.report_01_path, "TestKey", "TestValue")
        self._assert_not_injected(self.report_02_path, "TestKey")
        self._assert_not_injected(self.report_03_path, "TestKey")

    def test_depth_1_modifies_root_and_level1(self):
        """Verify --depth 1 processes the target and one level of subdirectories."""
        result = self._run_script(self.temp_dir, "--key", "TestKey", "--value", "TestValue", "--depth", "1")
        # FIX: Check stderr for logging output
        self.assertIn("Successfully updated 2 of 2 reports", result.stderr)
        self._assert_injected(self.report_01_path, "TestKey", "TestValue")
        self._assert_injected(self.report_02_path, "TestKey", "TestValue")
        self._assert_not_injected(self.report_03_path, "TestKey")

    def test_depth_minus_1_is_fully_recursive(self):
        """Verify --depth -1 processes all subdirectories."""
        result = self._run_script(self.temp_dir, "--key", "TestKey", "--value", "TestValue", "--depth", "-1")
        # FIX: Check stderr for logging output
        self.assertIn("Successfully updated 3 of 3 reports", result.stderr)
        self._assert_injected(self.report_01_path, "TestKey", "TestValue")
        self._assert_injected(self.report_02_path, "TestKey", "TestValue")
        self._assert_injected(self.report_03_path, "TestKey", "TestValue")

    def test_target_directory_not_found(self):
        """Verify the script exits gracefully if the target directory does not exist."""
        non_existent_dir = os.path.join(self.temp_dir, "non_existent")
        result = self._run_script(non_existent_dir, "--key", "K", "--value", "V")
        # FIX: Check stderr for logging output
        self.assertIn("FATAL: The specified target directory does not exist", result.stderr)

    def test_no_run_dirs_found(self):
        """Verify correct message when no 'run_*' directories are found."""
        empty_dir = os.path.join(self.temp_dir, "empty")
        os.makedirs(empty_dir)
        result = self._run_script(empty_dir, "--key", "K", "--value", "V")
        # FIX: Check stderr for logging output
        self.assertIn("No 'run_*' directories found to process", result.stderr)

    # --- Unit Tests for inject_metadata_into_report ---

    def test_skips_if_key_already_exists(self):
        """Verify that a file is skipped if the metadata key is already present."""
        key = "ExistingKey"
        report_with_key = os.path.join(self.temp_dir, "report_with_key.txt")
        with open(report_with_key, 'w') as f:
            f.write(f"{key}: old_value\n" + REPORT_TEMPLATE)
        
        # FIX: Use assertLogs to capture logging output correctly
        with self.assertLogs('root', level='INFO') as cm:
            success = inject_metadata_into_report(report_with_key, key, "new_value")

        self.assertFalse(success)
        self.assertIn(f"Skipping: Metadata key '{key}' already exists", "".join(cm.output))

    def test_fails_if_anchor_is_missing(self):
        """Verify failure when the 'Personalities Source:' anchor is not in the file."""
        report_no_anchor = os.path.join(self.temp_dir, "report_no_anchor.txt")
        with open(report_no_anchor, 'w') as f:
            f.write("Some\nRandom\nContent\n")

        # FIX: Use assertLogs to capture logging output correctly
        with self.assertLogs('root', level='INFO') as cm:
            success = inject_metadata_into_report(report_no_anchor, "key", "value")

        self.assertFalse(success)
        self.assertIn("Could not find injection anchor", "".join(cm.output))

    def test_handles_read_io_error(self):
        """Verify graceful handling of an IOError during file reading."""
        m = mock_open()
        m.side_effect = IOError("Permission denied")
        # FIX: Use assertLogs to capture logging output correctly
        with patch('builtins.open', m), \
             self.assertLogs('root', level='INFO') as cm:
            success = inject_metadata_into_report("any/fake/path.txt", "key", "value")

        self.assertFalse(success)
        log_output = "".join(cm.output)
        self.assertIn("Could not read file", log_output)
        self.assertIn("Permission denied", log_output)
        
    def test_handles_write_io_error(self):
        """Verify graceful handling of an IOError during file writing."""
        read_handle = StringIO(REPORT_TEMPLATE)
        m = mock_open()
        m.side_effect = [read_handle, IOError("Disk full")]

        # FIX: Use assertLogs to capture logging output correctly
        with patch('builtins.open', m), \
             self.assertLogs('root', level='INFO') as cm:
            success = inject_metadata_into_report("any/fake/path.txt", "key", "value")

        self.assertFalse(success)
        log_output = "".join(cm.output)
        self.assertIn("Could not write to file", log_output)
        self.assertIn("Disk full", log_output)

if __name__ == '__main__':
    unittest.main()
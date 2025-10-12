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
# Filename: tests/maintenance/test_operation_runner.py

"""Tests for operation_runner.py module."""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "maintenance"))
import operation_runner


class TestOperationRunner(unittest.TestCase):
    """Test suite for operation_runner functionality."""
    
    def setUp(self):
        """Create temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp()
        self.test_results_dir = Path(self.test_dir) / "tests" / "results"
        self.test_results_dir.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)
    
    @patch('operation_runner.Path')
    def test_log_operation_summary_creates_file(self, mock_path):
        """Test that log_operation_summary creates the correct file structure."""
        mock_path.return_value.resolve.return_value.parent.parent.parent = Path(self.test_dir)
        
        log_file = self.test_results_dir / "test_summary.jsonl"
        
        operation_runner.log_operation_summary(
            "test-data-prep",
            0,
            12.34,
            "test_summary.jsonl",
            ["pytest", "tests/data_preparation/"]
        )
        
        self.assertTrue(log_file.exists())
        
        with open(log_file, 'r') as f:
            entry = json.loads(f.read())
        
        self.assertEqual(entry['operation'], 'test-data-prep')
        self.assertEqual(entry['status'], 'PASS')
        self.assertEqual(entry['exit_code'], 0)
        self.assertEqual(entry['duration_seconds'], 12.34)
        self.assertIn('timestamp', entry)
        self.assertEqual(entry['command'], 'pytest tests/data_preparation/')
    
    @patch('operation_runner.Path')
    def test_log_operation_summary_appends(self, mock_path):
        """Test that multiple calls append to the same file."""
        mock_path.return_value.resolve.return_value.parent.parent.parent = Path(self.test_dir)
        
        log_file = self.test_results_dir / "workflow_summary.jsonl"
        
        # Log two operations
        operation_runner.log_operation_summary("new-exp", 0, 10.0, "workflow_summary.jsonl", ["pwsh", "-File", "new_experiment.ps1"])
        operation_runner.log_operation_summary("aud-exp", 1, 5.5, "workflow_summary.jsonl", ["pwsh", "-File", "audit_experiment.ps1"])
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 2)
        
        entry1 = json.loads(lines[0])
        entry2 = json.loads(lines[1])
        
        self.assertEqual(entry1['operation'], 'new-exp')
        self.assertEqual(entry1['status'], 'PASS')
        self.assertIn('command', entry1)
        
        self.assertEqual(entry2['operation'], 'aud-exp')
        self.assertEqual(entry2['status'], 'FAIL')
        self.assertIn('command', entry2)
    
    def test_get_operation_category_detects_test_section(self):
        """Test that get_operation_category correctly identifies test operations."""
        # This would need a mock pyproject.toml, but demonstrates the test structure
        # In practice, you'd use a fixture file or mock the file reading
        pass
    
    def test_lock_prevents_concurrent_operations(self):
        """Test that the lock mechanism prevents concurrent operations."""
        # This would test the acquire_lock/release_lock functionality
        pass


if __name__ == '__main__':
    unittest.main()

# === End of tests/maintenance/test_operation_runner.py ===

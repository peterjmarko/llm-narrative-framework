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
# Filename: tests/scripts/test_clean_project.py

import unittest
from unittest.mock import patch
import pathlib
import sys
import os
import tempfile
import shutil
import zipfile
import io
from contextlib import redirect_stdout

# Add scripts directory to path to allow import
scripts_dir = str(pathlib.Path(__file__).resolve().parent.parent.parent / "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from clean_project import main as clean_main, ARCHIVE_DIR_NAME, STATE_FILE_NAME

class TestCleanProject(unittest.TestCase):

    def setUp(self):
        """Create a temporary directory to act as the project root for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.project_root = pathlib.Path(self.test_dir)

    def tearDown(self):
        """Remove the temporary directory after each test."""
        shutil.rmtree(self.test_dir)

    def _create_mock_file_structure(self):
        """Helper to create a standard set of files and folders for testing."""
        # Create items that SHOULD be cleaned
        (self.project_root / "src" / "__pycache__").mkdir(parents=True)
        (self.project_root / "src" / "__pycache__" / "module.pyc").touch()
        (self.project_root / "htmlcov").mkdir()
        (self.project_root / "htmlcov" / "index.html").touch()
        (self.project_root / ".coverage").touch()
        (self.project_root / "temp_sandbox").mkdir()
        (self.project_root / "temp_sandbox" / "test_file.txt").touch()
        # Create items that should NOT be cleaned
        (self.project_root / ".venv" / "lib").mkdir(parents=True)
        (self.project_root / "src" / "my_source.py").touch()

    def test_dry_run_identifies_correct_targets(self):
        """Test that a dry run correctly identifies items to be cleaned."""
        self._create_mock_file_structure()
        
        # Capture stdout to check the report content
        captured_output = io.StringIO()
        with redirect_stdout(captured_output), \
             patch('sys.argv', ['clean_project.py', '--quiet']):
            
            # Pass the temporary directory as the root path for the test
            clean_main(root_path=self.project_root)
        
        output = captured_output.getvalue()
        
        self.assertIn("src/__pycache__", output)
        self.assertIn("htmlcov", output)
        self.assertIn(".coverage", output)
        self.assertIn("temp_sandbox", output)
        self.assertNotIn(".venv", output)

    @patch('builtins.input', return_value='y')
    def test_execute_archives_and_prunes_correctly(self, mock_input):
        """Test that --execute creates an archive and correctly prunes the single previous one."""
        self._create_mock_file_structure()
        
        archive_dir = self.project_root / ARCHIVE_DIR_NAME
        archive_dir.mkdir()
        
        # Create a valid "old" zip archive to test pruning (use proper timestamp format)
        old_archive_path = archive_dir / "cleanup_archive_20240101_120000.zip"
        with zipfile.ZipFile(old_archive_path, 'w') as zf:
            zf.writestr("dummy.txt", "data")

        # Set this as the last good archive to prevent self-healing
        state_file = archive_dir / STATE_FILE_NAME
        state_file.write_text("cleanup_archive_20240101_120000.zip")
        
        with patch('sys.argv', ['clean_project.py', '--execute', '--quiet']):
            clean_main(root_path=self.project_root)

        self.assertFalse((self.project_root / "src" / "__pycache__").exists())
        
        archives = list(archive_dir.glob("*.zip"))
        self.assertEqual(len(archives), 1, "Should only be one new archive left.")
        self.assertFalse(old_archive_path.exists(), "Old archive should have been pruned.")
        
        state_file = archive_dir / STATE_FILE_NAME
        self.assertTrue(state_file.exists())
        self.assertEqual(state_file.read_text().strip(), archives[0].name)

    @patch('builtins.input', return_value='y')
    @patch('clean_project.main')
    def test_self_healing_restores_from_corrupted_archive(self, mock_main_relaunch, mock_input):
        """Test the self-healing mechanism for an interrupted run."""
        archive_dir = self.project_root / ARCHIVE_DIR_NAME
        archive_dir.mkdir()
        
        state_file = archive_dir / STATE_FILE_NAME
        state_file.write_text("cleanup_archive_GOOD.zip")
        (archive_dir / "cleanup_archive_GOOD.zip").touch() # This is a valid, but empty, previous archive.
        
        corrupted_archive_path = archive_dir / "cleanup_archive_CORRUPTED.zip"
        with zipfile.ZipFile(corrupted_archive_path, 'w') as zf:
            zf.writestr("src/should_be_restored.txt", "data")
        
        with patch('sys.argv', ['clean_project.py', '--execute', '--quiet']):
            with self.assertRaises(SystemExit) as cm:
                clean_main(root_path=self.project_root)
            self.assertEqual(cm.exception.code, 0)
            
        self.assertTrue((self.project_root / "src" / "should_be_restored.txt").exists())
        self.assertFalse(corrupted_archive_path.exists())
        mock_main_relaunch.assert_called_once()

if __name__ == '__main__':
    unittest.main()

# === End of tests/scripts/test_clean_project.py ===

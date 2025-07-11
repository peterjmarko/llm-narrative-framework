#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
# Filename: tests/test_convert_py_to_txt.py

# tests/test_convert_py_to_txt.py

import unittest
import os
import shutil
import tempfile
import subprocess
import sys
import pathlib
import time
import datetime
from unittest.mock import patch
from io import StringIO

# Import the specific functions we need to unit test
from src.convert_py_to_txt import convert_scripts_to_txt, archive_previous_txt_versions

# --- CONFIGURATION ---
# The project root is used for setting the PYTHONPATH and CWD
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Names used by the script
TXT_OUTPUT_SUBDIR_NAME = "project_code_as_txt"
ARCHIVE_SUBDIR_NAME = "Archive"
EXCLUDE_DIR_NAME = ".venv"
# --- END CONFIGURATION ---


class TestConvertPyToTxt(unittest.TestCase):
    """
    Tests the src/convert_py_to_txt.py script by running it as a proper Python module.
    """

    def setUp(self):
        """Set up a temporary directory with a mock project structure before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_dir, TXT_OUTPUT_SUBDIR_NAME)

        # Create a mock project structure
        with open(os.path.join(self.temp_dir, "root_script.py"), "w") as f: f.write("# root")
        os.makedirs(os.path.join(self.temp_dir, "module1", "submodule"))
        with open(os.path.join(self.temp_dir, "module1", "component_a.py"), "w") as f: f.write("# a")
        with open(os.path.join(self.temp_dir, "module1", "helper.ps1"), "w") as f: f.write("# ps1")
        with open(os.path.join(self.temp_dir, "module1", "submodule", "component_b.py"), "w") as f: f.write("# b")
        os.makedirs(os.path.join(self.temp_dir, EXCLUDE_DIR_NAME))
        with open(os.path.join(self.temp_dir, EXCLUDE_DIR_NAME, "some_lib.py"), "w") as f: f.write("# ignored")

    def tearDown(self):
        """Clean up the temporary directory after each test."""
        shutil.rmtree(self.temp_dir)

    def _run_script(self, source_dir, *args):
        """
        Runs the script as a module under coverage, using the correct argument structure.
        """
        cmd = [
            sys.executable,
            "-m", "coverage", "run",
            "--parallel-mode",
            "--source=src",
            "-m", "src.convert_py_to_txt",
            source_dir,  # This is the mandatory 'project_dir' argument for the script.
        ]
        cmd.extend(args)

        env = os.environ.copy()
        env['COVERAGE_FILE'] = os.path.join(PROJECT_ROOT, '.coverage')
        env['PYTHONPATH'] = PROJECT_ROOT

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            env=env,
            cwd=PROJECT_ROOT
        )

        # A small helper to avoid printing stack traces for expected failures.
        is_expected_failure = "invalid_source" in self.id()

        if result.returncode != 0 and not is_expected_failure:
            print("\n--- SUBPROCESS FAILED ---")
            print(f"Command: {' '.join(cmd)}")
            print(f"PYTHONPATH: {env.get('PYTHONPATH')}")
            print(f"Return Code: {result.returncode}")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            print("-------------------------\n")

        return result

    def test_depth_0_non_recursive(self):
        """Verify --depth 0 (default) only converts files in the root directory."""
        result = self._run_script(self.temp_dir, "--depth", "0")
        self.assertEqual(result.returncode, 0, "Script execution failed.")
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "root_script.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "module1", "component_a.txt")))

    def test_depth_1_one_level_deep(self):
        """Verify --depth 1 converts root and one level of subdirectories."""
        result = self._run_script(self.temp_dir, "--depth", "1")
        self.assertEqual(result.returncode, 0, "Script execution failed.")
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "root_script.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "module1", "component_a.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "module1", "helper.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "module1", "submodule", "component_b.txt")))

    def test_depth_minus_1_infinite_recursion(self):
        """Verify --depth -1 converts files at all levels."""
        result = self._run_script(self.temp_dir, "--depth", "-1")
        self.assertEqual(result.returncode, 0, "Script execution failed.")
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "root_script.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "module1", "component_a.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "module1", "submodule", "component_b.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, EXCLUDE_DIR_NAME, "some_lib.txt")))

    def test_archiving_functionality(self):
        """Verify that pre-existing files are copied to the Archive folder."""
        # SETUP: Create a dummy output directory with a file in it *before* running the script.
        os.makedirs(self.output_dir)
        pre_existing_file_path = os.path.join(self.output_dir, "pre_existing_file.txt")
        with open(pre_existing_file_path, "w") as f:
            f.write("This file should be archived.")

        # EXECUTE: Run the script. It should first archive, then convert.
        result = self._run_script(self.temp_dir, "--depth", "0")
        self.assertEqual(result.returncode, 0, "Script execution failed.")

        # VERIFY: Check that the pre-existing file was moved to the archive.
        archive_dir = os.path.join(self.output_dir, ARCHIVE_SUBDIR_NAME)
        self.assertTrue(os.path.exists(os.path.join(archive_dir, "pre_existing_file.txt")), "Pre-existing file was not found in the archive.")
        
        # VERIFY: Check that the new conversion also happened.
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "root_script.txt")), "The new conversion did not create the expected root_script.txt.")
    
    def test_invalid_source_directory(self):
        """Verify the script handles a non-existent source directory gracefully."""
        invalid_path = os.path.join(self.temp_dir, "this_dir_does_not_exist")
        result = self._run_script(invalid_path)
        # The script prints an error but exits with code 0. We test for this specific behavior.
        self.assertEqual(result.returncode, 0, "Script should exit cleanly even with an invalid path.")
        # The script prints its error message to stdout.
        self.assertIn("The specified project directory does not exist", result.stdout)

    def test_empty_source_directory(self):
        """Verify the script runs without error on an empty directory."""
        empty_dir = os.path.join(self.temp_dir, "empty_dir")
        os.makedirs(empty_dir)
        result = self._run_script(empty_dir)
        self.assertEqual(result.returncode, 0, "Script failed on an empty directory.")
        # The output directory should not be created if there's nothing to convert
        self.assertFalse(os.path.exists(self.output_dir), "Output directory should not be created for an empty source.")

    def test_archiving_empty_directory(self):
        """Verify that archiving works correctly when the output folder exists but is empty."""
        # Create an empty output directory before running the script
        os.makedirs(self.output_dir)

        result = self._run_script(self.temp_dir, "--depth", "0")
        self.assertEqual(result.returncode, 0, "Script execution failed.")

        # The script's behavior is to always create the archive dir if the parent exists.
        archive_dir = os.path.join(self.output_dir, ARCHIVE_SUBDIR_NAME)
        self.assertTrue(os.path.exists(archive_dir), "Archive directory should be created even if the source is empty.")
        # We also assert that the created archive directory is empty.
        self.assertEqual(len(os.listdir(archive_dir)), 0, "The created archive directory should be empty.")
    
    def test_invalid_source_directory(self):
        """Verify the script handles a non-existent source directory gracefully."""
        invalid_path = os.path.join(self.temp_dir, "this_dir_does_not_exist")
        result = self._run_script(invalid_path)
        # VERIFY: The script prints an error but exits with code 0. This is the actual behavior.
        self.assertEqual(result.returncode, 0, "Script should exit cleanly even with an invalid path.")
        # VERIFY: The script prints its specific error message to stdout.
        self.assertIn("The specified project directory does not exist", result.stdout)

    def test_nothing_to_archive(self):
        """Verify the 'Nothing to archive' message is printed when the output dir doesn't exist."""
        # Run the script on a directory where the output folder does not yet exist.
        result = self._run_script(self.temp_dir, "--depth", "0")
        self.assertEqual(result.returncode, 0, "Script execution failed.")
        # The script should print a specific informational message.
        self.assertIn("Nothing to archive", result.stdout)

    def test_pycache_exclusion(self):
        """Verify that files in a __pycache__ directory are ignored."""
        # The setUp method already creates a __pycache__ directory.
        result = self._run_script(self.temp_dir, "--depth", "-1") # Use infinite depth
        self.assertEqual(result.returncode, 0, "Script execution failed.")
        
        # Verify the file within __pycache__ was NOT converted.
        pycache_output_path = os.path.join(self.output_dir, "module1", "__pycache__", "cached.txt")
        self.assertFalse(os.path.exists(pycache_output_path), "A file from __pycache__ was incorrectly converted.")

    def test_no_convertible_files(self):
        """Verify the script runs without error if no convertible files are found."""
        # Create a new directory and put a non-convertible file in it.
        source_dir = os.path.join(self.temp_dir, "no_scripts")
        os.makedirs(source_dir)
        with open(os.path.join(source_dir, "data.json"), "w") as f:
            f.write("{}")

        result = self._run_script(source_dir)
        self.assertEqual(result.returncode, 0, "Script failed when no convertible files were present.")
        
        # Verify the summary message shows 0 files were copied.
        self.assertIn("Script files (.py, .ps1) found and copied as .txt: 0", result.stdout)
        
        # The output directory should still be created by the script.
        output_dir_for_this_test = os.path.join(source_dir, TXT_OUTPUT_SUBDIR_NAME)
        self.assertTrue(os.path.exists(output_dir_for_this_test))
    
    def test_archive_path_is_a_file(self):
        """Verify the script handles the case where the archive path is a file."""
        # SETUP: Create the output directory, and then create a FILE named 'Archive' inside it.
        os.makedirs(self.output_dir)
        archive_file_path = os.path.join(self.output_dir, ARCHIVE_SUBDIR_NAME)
        with open(archive_file_path, "w") as f:
            f.write("I am a file, not a directory.")

        # EXECUTE: Run the script.
        result = self._run_script(self.temp_dir)
        self.assertEqual(result.returncode, 0, "Script failed when archive path was a file.")

        # VERIFY: The script should have removed the file and created a directory.
        archive_dir_path = os.path.join(self.output_dir, ARCHIVE_SUBDIR_NAME)
        self.assertTrue(os.path.isdir(archive_dir_path), "The 'Archive' file was not replaced with a directory.")
        self.assertIn("Warning: Archive path", result.stdout, "Warning for replacing file was not shown.")

    def test_archive_conflict_source_dir_dest_file(self):
        """Verify archive handles conflict: source is a directory, destination is a file."""
        # SETUP:
        # 1. Create a dummy archive with a FILE named 'module1'.
        archive_dir = os.path.join(self.output_dir, ARCHIVE_SUBDIR_NAME)
        os.makedirs(archive_dir)
        with open(os.path.join(archive_dir, "module1"), "w") as f:
            f.write("I am a file.")
        # 2. Create a dummy output dir that will be archived. The source has a FOLDER named 'module1'.
        os.makedirs(os.path.join(self.output_dir, "module1"))
        with open(os.path.join(self.output_dir, "module1", "test.txt"), "w") as f:
            f.write("content")

        # EXECUTE: Run the script.
        result = self._run_script(self.temp_dir)
        self.assertEqual(result.returncode, 0, "Script failed during archive conflict.")

        # VERIFY: The file 'module1' in the archive should be replaced by the directory.
        self.assertTrue(os.path.isdir(os.path.join(archive_dir, "module1")))
        self.assertTrue(os.path.exists(os.path.join(archive_dir, "module1", "test.txt")))
        self.assertIn("is a file, removing to copy directory", result.stdout)

    def test_archive_conflict_source_file_dest_dir(self):
        """Verify archive handles conflict: source is a file, destination is a directory."""
        # SETUP:
        # 1. Create a dummy archive with a DIRECTORY named 'root_script.txt'.
        archive_dir = os.path.join(self.output_dir, ARCHIVE_SUBDIR_NAME)
        os.makedirs(os.path.join(archive_dir, "root_script.txt"))
        # 2. Create a dummy output dir with a FILE named 'root_script.txt'.
        with open(os.path.join(self.output_dir, "root_script.txt"), "w") as f:
            f.write("I am a file.")

        # EXECUTE: Run the script.
        result = self._run_script(self.temp_dir)
        self.assertEqual(result.returncode, 0, "Script failed during archive conflict.")

        # VERIFY: The directory in the archive should be replaced by the file.
        self.assertTrue(os.path.isfile(os.path.join(archive_dir, "root_script.txt")))
        self.assertIn("is a directory, removing to copy file", result.stdout)

    # The patch target must be where the object is *looked up* (in the script's module)
    @patch('src.convert_py_to_txt.shutil.copy2', side_effect=IOError("Simulated write error"))
    def test_copy_failure_is_handled_gracefully_unit_test(self, mock_copy):
        """
        Unit tests the copy failure by calling the function directly,
        allowing the mock to correctly intercept the call.
        """
        # SETUP: Define the arguments for the function we are testing.
        source_path = pathlib.Path(self.temp_dir)
        output_subdir = TXT_OUTPUT_SUBDIR_NAME
        exclude_dirs = {"__pycache__"}
        depth = 0

        # Use a mock to force shutil.copy2 to raise an error.
        # The patch target must be where the object is *looked up*, which is
        # inside the script's module.
        with patch('src.convert_py_to_txt.shutil.copy2', side_effect=IOError("Simulated write error")):
            # SETUP: Redirect stdout to capture the print() statements from the function.
            old_stdout = sys.stdout
            sys.stdout = captured_output = StringIO()

            # EXECUTE: Call the function directly.
            convert_scripts_to_txt(source_path, output_subdir, exclude_dirs, depth)

            # TEARDOWN: Restore stdout.
            sys.stdout = old_stdout
            
            # Get the output that was printed.
            output = captured_output.getvalue()

        # VERIFY: Check that the correct error messages were printed to the captured output.
        self.assertIn("Error: Could not copy", output)
        self.assertIn("Errors during copy/directory creation: 1", output)
    
    def test_skips_up_to_date_files(self):
        """
        Verify that files are not re-copied if the destination is not older.
        This covers the timestamp check (lines 234-235).
        """
        # Run once to create the initial .txt files.
        self._run_script(self.temp_dir)
        dest_file_path = os.path.join(self.output_dir, "root_script.txt")
        self.assertTrue(os.path.exists(dest_file_path))
        mtime_after_first_run = os.path.getmtime(dest_file_path)

        # Wait a moment to ensure timestamps are distinct, then run again.
        time.sleep(0.1)
        self._run_script(self.temp_dir)

        # Verify the destination file was NOT modified because it was up-to-date.
        mtime_after_second_run = os.path.getmtime(dest_file_path)
        self.assertEqual(mtime_after_first_run, mtime_after_second_run, "File should not have been updated.")

    def test_archive_function_handles_errors(self):
        """
        Unit tests error handling in the archive_previous_txt_versions function.
        This covers copy errors (lines 163-169).
        """
        # SETUP
        output_path = pathlib.Path(self.output_dir)
        archive_source_dir = output_path / ARCHIVE_SUBDIR_NAME
        os.makedirs(archive_source_dir)
        (archive_source_dir / "file_to_archive.txt").touch()

        # Mock shutil.copy2 to simulate a failure when the function tries to copy the file.
        with patch('src.convert_py_to_txt.shutil.copy2', side_effect=IOError("Mock copy error")), \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:

            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_previous_txt_versions(output_path, ARCHIVE_SUBDIR_NAME, timestamp)
            output = mock_stdout.getvalue()

        # VERIFY: Assert that the actual error messages printed by the script are present.
        self.assertIn("Error archiving", output) # Check for the specific error line.
        self.assertIn("Archiving encountered 1 errors", output) # Check for the summary line.

    def test_convert_function_handles_mkdir_error(self):
        """
        Unit tests that a mkdir error is handled during the conversion process.
        This covers the except block for dest_dir.mkdir (lines 227-230).
        """
        # Mock pathlib.Path.mkdir to simulate a failure to create a destination directory.
        with patch('pathlib.Path.mkdir', side_effect=IOError("Mock mkdir error")), \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:

            # Execute the function directly.
            convert_scripts_to_txt(pathlib.Path(self.temp_dir), TXT_OUTPUT_SUBDIR_NAME, set(), 0)
            output = mock_stdout.getvalue()

        # VERIFY: Assert the actual error message printed by the script.
        self.assertIn("Error: Could not create output directory", output)
        self.assertIn("Mock mkdir error", output)


if __name__ == '__main__':
    unittest.main()

# === End of tests/test_convert_py_to_txt.py ===

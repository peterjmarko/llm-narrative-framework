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
# Filename: tests/test_list_project_files.py

import unittest
import os
import tempfile
import subprocess
import sys
import pathlib
from unittest.mock import patch, MagicMock, mock_open, PropertyMock, DEFAULT

# Ensure the src directory is in the Python path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import functions and the module itself to patch its constants
import src.list_project_files as list_project_files_module
from src.list_project_files import (
    main as list_files_main,
    generate_file_listing,
    count_lines_in_file,
    should_exclude_path,
    get_project_root
)

class TestListProjectFiles(unittest.TestCase):
    """
    Comprehensive test suite for list_project_files.py, combining
    integration tests for happy paths and unit tests for edge cases and errors.
    """

    def setUp(self):
        """Set up a temporary directory to simulate a project structure for each test."""
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.project_root = pathlib.Path(self.temp_dir_obj.name)
        
        # Store original constants to restore them after tests
        self.original_exclude_dirs_set = list_project_files_module.EXCLUDE_DIRS_SET.copy()
        self.original_exclude_files_set = list_project_files_module.EXCLUDE_FILES_SET.copy()
        self.original_exclude_extensions_set = list_project_files_module.EXCLUDE_EXTENSIONS_SET.copy()
        self.original_custom_depth_map = list_project_files_module.CUSTOM_DEPTH_MAP.copy()
        self.original_file_count_warning_threshold = list_project_files_module.FILE_COUNT_WARNING_THRESHOLD

        # Modify constants for predictable testing
        list_project_files_module.EXCLUDE_DIRS_SET = {"test_exclude_dir", "archive", "node_modules", ".venv", "__pycache__"}
        list_project_files_module.EXCLUDE_FILES_SET = {".DS_Store", "Thumbs.db", "*.pyc", "*.pyo", "*.pyd", "~$*.*", "temp.log", "hidden_file.temp"}
        list_project_files_module.EXCLUDE_EXTENSIONS_SET = {".pyc", ".pyo", ".pyd", ".log", ".tmp", ".swp"}
        list_project_files_module.FILE_COUNT_WARNING_THRESHOLD = 5 # Set low for easy testing of warning prompt

        # Create a standard mock project structure
        self.output_dir = self.project_root / "output"
        self.output_dir.mkdir()
        
        self.src_dir = self.project_root / "src"
        self.src_dir.mkdir()
        (self.src_dir / "module1.py").write_text("line1\nline2\n", "utf-8")
        (self.src_dir / "module2.txt").write_text("content", "utf-8")

        self.tests_dir = self.project_root / "tests"
        self.tests_dir.mkdir()
        (self.tests_dir / "test_something.py").write_text("test_line1", "utf-8")

        self.docs_dir = self.project_root / "docs"
        self.docs_dir.mkdir()
        (self.docs_dir / "index.md").touch()
        (self.docs_dir / "dev").mkdir()
        (self.docs_dir / "dev" / "api.rst").touch()

        self.htmlcov_dir = self.project_root / "htmlcov"
        self.htmlcov_dir.mkdir()
        (self.htmlcov_dir / "index.html").touch()

        self.analysis_inputs_dir = self.output_dir / "analysis_inputs"
        self.analysis_inputs_dir.mkdir()
        (self.analysis_inputs_dir / "data.csv").touch()
        
        self.results_dir = self.output_dir / "results"
        self.results_dir.mkdir()
        (self.results_dir / "run1").mkdir()
        (self.results_dir / "run1" / "summary.txt").touch()

        (self.project_root / "README.md").touch() # A key file
        (self.project_root / "config.py").touch() # For get_project_root heuristic
        (self.project_root / "main.py").write_text("pass", "utf-8")
        (self.project_root / "keys.py").touch() # Another key file
        (self.project_root / ".env").touch() # Another key file
        (self.project_root / "requirements.txt").touch() # Another key file
        (self.project_root / "noon_price_predictor.py").touch() # Another key file

        # Excluded items via initial setup or EXCLUDE_DIRS_SET
        (self.project_root / ".venv").mkdir()
        (self.project_root / "test.log").touch()
        (self.project_root / "temp.tmp").touch()
        (self.project_root / "test_exclude_dir").mkdir()
        (self.project_root / "archive").mkdir()
        (self.project_root / "node_modules").mkdir()
        (self.project_root / "__pycache__").mkdir()
        (self.project_root / "__pycache__" / "cached_file.pyc").touch() # Nested excluded file

        # For should_exclude_path_top_level_hidden_dir test:
        (self.project_root / ".some_hidden_dir").mkdir()
        (self.project_root / ".some_hidden_dir" / "hidden_file.temp").touch()

        # Set up custom depth map for testing. This is used by generate_file_listing.
        list_project_files_module.CUSTOM_DEPTH_MAP = {
            "docs": 2,
            "htmlcov": 0,
            "output/analysis_inputs": 0,
            "output": 3,
            "src": 1,
            "tests": 1,
        }

    def tearDown(self):
        """Clean up the temporary directory and restore original constants."""
        self.temp_dir_obj.cleanup()
        list_project_files_module.EXCLUDE_DIRS_SET = self.original_exclude_dirs_set
        list_project_files_module.EXCLUDE_FILES_SET = self.original_exclude_files_set
        list_project_files_module.EXCLUDE_EXTENSIONS_SET = self.original_exclude_extensions_set
        list_project_files_module.CUSTOM_DEPTH_MAP = self.original_custom_depth_map
        list_project_files_module.FILE_COUNT_WARNING_THRESHOLD = self.original_file_count_warning_threshold

    def _run_script_as_subprocess(self, *args):
        """Helper to run the script as a subprocess for integration testing."""
        script_path = pathlib.Path(__file__).parent.parent / "src" / "list_project_files.py"
        command = [sys.executable, str(script_path)] + list(args)
        # Run from the project_root so relative paths work naturally for the script itself
        return subprocess.run(command, cwd=self.project_root, capture_output=True, text=True, check=False)

    # --- Integration Tests ---

    def test_integration_happy_path_depth_all(self):
        """High-level test to ensure the script runs and produces expected output with depth -1."""
        result = self._run_script_as_subprocess("--depth", "-1", str(self.project_root)) # Pass target_directory explicitly
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}\n{result.stdout}")

        report_path = self.project_root / "output" / list_project_files_module.REPORT_SUBDIR / "project_structure_report_depth_all.txt"
        self.assertTrue(report_path.exists(), f"Report file not created at {report_path}")

        report_content = report_path.read_text(encoding='utf-8')
        self.assertIn("Report generation complete", report_content)
        self.assertIn(os.path.join("src", "module1.py"), report_content)
        self.assertIn(os.path.join("tests", "test_something.py"), report_content)

        # Test custom depth for docs (docs:2) and output (output:3)
        # Corrected indentation for assertion to match src/list_project_files.py's actual output (2 spaces per level)
        self.assertIn("docs/\n  📁 dev/\n    📄 api.rst\n", report_content)
        self.assertIn("📁 output/\n", report_content)
        self.assertIn("  📁 results/\n", report_content)
        self.assertIn("    📁 run1/\n", report_content)
        self.assertIn("      📄 summary.txt\n", report_content)
        
        # Assert excluded items are NOT in report due to various rules
        self.assertNotIn("📁 .venv/", report_content)
        self.assertNotIn("test.log", report_content) # Excluded by extension
        self.assertNotIn("temp.tmp", report_content) # Excluded by extension
        self.assertIn("📁 htmlcov/\n", report_content) # Custom depth 0 means dir is listed
        self.assertNotIn("index.html", report_content) # But its contents are hidden
        self.assertNotIn("data.csv", report_content) # Excluded by custom depth 0 for output/analysis_inputs
        self.assertNotIn("📁 __pycache__/", report_content) # Excluded by name
        self.assertNotIn("📁 .some_hidden_dir/", report_content) # Excluded by the new fix

    def test_integration_happy_path_depth_0(self):
        """Test with depth 0, where CUSTOM_DEPTH_MAP overrides take precedence."""
        # Note: The patch for CUSTOM_DEPTH_MAP is removed as it doesn't affect the subprocess.
        # This test now verifies the script's actual behavior.
        result = self._run_script_as_subprocess("--depth", "0", str(self.project_root)) # Pass target_directory explicitly
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}\n{result.stdout}")

        report_path = self.project_root / "output" / list_project_files_module.REPORT_SUBDIR / "project_structure_report_depth_0.txt"
        self.assertTrue(report_path.exists(), f"Report file not created at {report_path}")

        report_content = report_path.read_text(encoding='utf-8')
        self.assertIn("Report generation complete", report_content)

        # Check top-level items
        self.assertIn("src/", report_content)
        self.assertIn("tests/", report_content)
        self.assertIn("output/", report_content)
        self.assertIn("docs/", report_content)
        self.assertIn("main.py", report_content)
        self.assertIn("README.md", report_content)

        # With depth=0, the hierarchical listing respects CUSTOM_DEPTH_MAP,
        # but the file summary collection logic does not. The test verifies this actual behavior.
        
        # 1. Check that the tree view correctly expands folders with custom depth > 0.
        self.assertIn("  📄 module1.py\n", report_content)      # from src (custom depth 1)
        self.assertIn("  📄 test_something.py\n", report_content) # from tests (custom depth 1)

        # 2. Check that the file summary, which strictly follows --depth=0, does NOT include nested files.
        # We replace separators to make the check work on both Windows and Linux.
        report_content_for_summary_check = report_content.replace('/', '\\')
        self.assertNotIn(os.path.join(".", "src", "module1.py"), report_content_for_summary_check)
        self.assertNotIn(os.path.join(".", "tests", "test_something.py"), report_content_for_summary_check)

        # 3. Check that the tree view correctly hides contents for custom depth == 0.
        self.assertIn("📁 htmlcov/\n", report_content)
        self.assertNotIn("index.html", report_content)

    def test_integration_depth_1(self):
        """Test with depth 1 - top-level + immediate children, respecting custom depths."""
        result = self._run_script_as_subprocess("--depth", "1", str(self.project_root))
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}\n{result.stdout}")
        
        report_path = self.project_root / "output" / list_project_files_module.REPORT_SUBDIR / "project_structure_report_depth_1.txt"
        self.assertTrue(report_path.exists(), f"Report file not created at {report_path}")
        
        report_content = report_path.read_text(encoding='utf-8')
        self.assertIn("Report generation complete", report_content)
        
        # Check depth 1 items and custom depths
        # Corrected indentation for assertion to match src/list_project_files.py's actual output (2 spaces per level)
        self.assertIn("src/\n  📄 module1.py\n  📄 module2.txt\n", report_content) # src:1
        # Corrected indentation for assertion to match src/list_project_files.py's actual output (2 spaces per level)
        self.assertIn("tests/\n  📄 test_something.py\n", report_content) # tests:1
        
        # docs custom depth is 2, so it should show docs/dev/ and docs/index.md, AND docs/dev/api.rst
        # Corrected indentation for assertion to match src/list_project_files.py's actual output (2 spaces per level)
        self.assertIn("docs/\n  📁 dev/\n    📄 api.rst\n  📄 index.md\n", report_content)
        
        # output/analysis_inputs custom depth is 0, so its contents should be hidden
        self.assertIn("📁 output/\n", report_content)
        self.assertIn("  📁 analysis_inputs/\n", report_content)
        self.assertIn("  📁 results/\n", report_content)
        self.assertNotIn("output/analysis_inputs/data.csv", report_content) # Should be hidden

        # results dir

    def test_no_py_files_found(self):
        """Verify correct message when no .py files are found."""
        # Unlink all .py files created in setUp
        for py_file in self.project_root.rglob("*.py"):
            py_file.unlink()

        result = self._run_script_as_subprocess("--depth", "-1", str(self.project_root)) # Pass target_directory explicitly
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}\n{result.stdout}")
        report_path = self.project_root / "output" / list_project_files_module.REPORT_SUBDIR / "project_structure_report_depth_all.txt"
        self.assertTrue(report_path.exists(), f"Report file not created at {report_path}") # Added check here
        report_content = report_path.read_text(encoding='utf-8')
        self.assertIn("(No .py files found meeting criteria)", report_content)

    def test_no_key_files_found(self):
        """Verify correct message when no key files are found."""
        # Unlink all key files created in setUp
        (self.project_root / "README.md").unlink()
        (self.project_root / "config.py").unlink()
        (self.project_root / "keys.py").unlink()
        (self.project_root / ".env").unlink()
        (self.project_root / "requirements.txt").unlink()
        (self.project_root / "noon_price_predictor.py").unlink()
        
        result = self._run_script_as_subprocess("--depth", "0", str(self.project_root)) # Pass target_directory explicitly
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}\n{result.stdout}")
        report_path = self.project_root / "output" / list_project_files_module.REPORT_SUBDIR / "project_structure_report_depth_0.txt"
        self.assertTrue(report_path.exists(), f"Report file not created at {report_path}") # Added check here
        report_content = report_path.read_text(encoding='utf-8')
        self.assertIn("(No predefined key files found at project root)", report_content)

    # --- Unit Tests for should_exclude_path ---
    def test_should_exclude_path_dir_by_name(self):
        """Test exclusion of a directory by its name."""
        excluded_dir = self.project_root / "test_exclude_dir"
        self.assertTrue(should_exclude_path(excluded_dir, self.project_root))

    def test_should_exclude_path_file_by_name(self):
        """Test exclusion of a file by its name."""
        excluded_file = self.project_root / "temp.log"
        self.assertTrue(should_exclude_path(excluded_file, self.project_root))

    def test_should_exclude_path_file_by_extension(self):
        """Test exclusion of a file by its extension."""
        excluded_file = self.project_root / "some_file.tmp"
        self.assertTrue(should_exclude_path(excluded_file, self.project_root))

    def test_should_exclude_path_nested_excluded_dir(self):
        """Test exclusion of a file within a nested excluded directory."""
        # File within 'archive' (in EXCLUDE_DIRS_SET)
        nested_excluded_file = self.project_root / "archive" / "nested_document.pdf"
        nested_excluded_file.touch()
        self.assertTrue(should_exclude_path(nested_excluded_file, self.project_root))
        
        # File within 'node_modules/my_lib'
        nested_in_node_modules = self.project_root / "node_modules" / "my_lib" / "index.js"
        (self.project_root / "node_modules" / "my_lib").mkdir(parents=True, exist_ok=True)
        nested_in_node_modules.touch()
        self.assertTrue(should_exclude_path(nested_in_node_modules, self.project_root))

        # File within '__pycache__'
        nested_in_pycache = self.project_root / "__pycache__" / "another_cached.pyc"
        nested_in_pycache.touch()
        self.assertTrue(should_exclude_path(nested_in_pycache, self.project_root))

    def test_should_exclude_path_top_level_hidden_dir(self):
        """Test exclusion of a top-level hidden directory not explicitly in EXCLUDE_DIRS_SET (e.g., .some_hidden_dir)."""
        hidden_dir_item = self.project_root / ".some_hidden_dir"
        self.assertFalse(hidden_dir_item.name in list_project_files_module.EXCLUDE_DIRS_SET)
        self.assertTrue(should_exclude_path(hidden_dir_item, self.project_root), 
                        f"Expected {hidden_dir_item} to be excluded by top-level hidden dir rule.")
        
        # Test a file inside such a directory
        hidden_file_item = self.project_root / ".some_hidden_dir" / "hidden_file.temp"
        self.assertTrue(should_exclude_path(hidden_file_item, self.project_root),
                        f"Expected {hidden_file_item} to be excluded as it's inside a top-level hidden dir.")

    # --- Unit Tests for generate_file_listing ---
    @patch('pathlib.Path.iterdir', autospec=True) # Added autospec=True
    def test_generate_listing_handles_permission_error_for_root(self, mock_iterdir):
        # Configure mock_iterdir to raise PermissionError for any call
        mock_iterdir.side_effect = PermissionError("Access Denied")
        """Verify that generate_file_listing gracefully handles a PermissionError."""
        mock_outfile = MagicMock()
        mock_outfile.write = MagicMock()
        
        # The mock_iterdir needs to be a method for the Path object, so it will receive `self` as the first arg.
        # The patch above patches the class method, so the mock_iterdir will get the Path instance.
        generate_file_listing(mock_outfile, self.project_root, self.project_root, scan_depth=1)
        
        self.assertTrue(any(" (Cannot Access)\n" in call.args[0] for call in mock_outfile.write.call_args_list))

    def test_generate_listing_custom_depths_applied(self):
        """Test that custom depths are correctly applied in generate_file_listing."""
        mock_outfile = MagicMock()
        mock_outfile.write = MagicMock()
        
        generate_file_listing(mock_outfile, self.project_root, self.project_root, indent_level=0, scan_depth=-1)

        content_written = "".join([call.args[0] for call in mock_outfile.write.call_args_list])

        # Test docs:2 (should show docs/dev/api.rst)
        # Corrected indentation for assertion to match src/list_project_files.py's actual output (2 spaces per level)
        self.assertIn("docs/\n  📁 dev/\n    📄 api.rst\n", content_written)
        
        # Test htmlcov:0 (should show htmlcov/ but not its contents)
        self.assertIn("htmlcov/\n", content_written)
        self.assertNotIn("htmlcov/index.html", content_written)

        # Test output/analysis_inputs:0 (should show output/analysis_inputs/ but not its contents)
        # Corrected indentation and added emoji for assertion to match src/list_project_files.py's actual output
        self.assertIn("📁 output/\n  📁 analysis_inputs/\n", content_written)
        self.assertNotIn("output/analysis_inputs/data.csv", content_written)
        
        # Test src:1 (should show module1.py and module2.txt)
        # Corrected indentation for assertion to match src/list_project_files.py's actual output (2 spaces per level)
        self.assertIn("src/\n  📄 module1.py\n  📄 module2.txt\n", content_written)

    def test_generate_listing_nested_dir_permission_error(self):
        """Verify generate_file_listing handles PermissionError for a nested directory."""
        mock_outfile = MagicMock()
        mock_outfile.write = MagicMock()

        mock_problem_dir = self.project_root / "output" / "problem_dir"
        mock_problem_dir.mkdir()
        
        original_iterdir = pathlib.Path.iterdir # Store original unbound method

        def custom_iterdir(mock_self, *args, **kwargs): # mock_self is the Path instance the mocked iterdir was called on
            # The 'self' argument from the original method call is passed as mock_self when autospec=True
            current_path_instance = mock_self 
            if current_path_instance == mock_problem_dir:
                raise PermissionError("Mock Permission Denied to nested dir")
            # Call the original unbound method, passing the instance explicitly
            return original_iterdir(current_path_instance)

        with patch('pathlib.Path.iterdir', autospec=True, side_effect=custom_iterdir):
            generate_file_listing(mock_outfile, self.project_root, self.project_root, indent_level=0, scan_depth=-1)
        
        content_written = "".join([call.args[0] for call in mock_outfile.write.call_args_list])
        
        expected_line = f"{'  ' * 2}📁 problem_dir/  (Cannot Access)\n"
        self.assertIn(expected_line, content_written)

    # --- Unit Tests for main() ---

    @patch('src.list_project_files.get_project_root')
    @patch('pathlib.Path.mkdir', side_effect=OSError("Permission denied"))
    def test_main_handles_mkdir_error(self, mock_mkdir, mock_get_root):
        """Verify main() exits if the output directory cannot be created."""
        mock_get_root.return_value = self.project_root
        with patch('sys.argv', ['script_name', str(self.project_root)]):
            with self.assertRaises(SystemExit) as cm:
                list_files_main()
        self.assertEqual(cm.exception.code, 1)

    @patch('builtins.input', return_value='y') # Added to handle input prompt
    @patch('builtins.open', side_effect=IOError("Disk full"))
    def test_main_handles_io_error_during_write(self, mock_open_builtin, mock_input):
        """Unit test for the main IOError handler during file writing."""
        with patch('sys.argv', ['script_name', str(self.project_root)]):
            with self.assertRaises(SystemExit) as cm:
                list_files_main()
            self.assertEqual(cm.exception.code, 1)

    @patch('builtins.input', return_value='y') # Added to handle input prompt
    @patch('src.list_project_files.datetime')
    def test_main_handles_unexpected_exception(self, mock_datetime, mock_input):
        """Unit test for the final catch-all exception handler."""
        mock_datetime.now.side_effect = TypeError("Unexpected error")
        with patch('sys.argv', ['script_name', str(self.project_root)]):
            with self.assertRaises(SystemExit) as cm:
                list_files_main()
            self.assertEqual(cm.exception.code, 1)

    @patch('builtins.input', return_value='y') # Added to handle input prompt
    @patch('src.list_project_files.get_project_root')
    def test_main_auto_detect_project_root(self, mock_get_root, mock_input):
        """Test main when target_directory is not provided, so get_project_root is called."""
        mock_get_root.return_value = self.project_root
        
        with patch('sys.argv', ['script_name', '--depth', '0']):
            with patch('builtins.open', mock_open()) as mock_file_open:
                list_files_main()
                mock_get_root.assert_called_once()
                report_path = self.project_root / "output" / list_project_files_module.REPORT_SUBDIR / "project_structure_report_depth_0.txt"
                mock_file_open.assert_called_with(report_path, 'w', encoding='utf-8')

    def test_main_invalid_target_directory(self):
        """Test main exits with error if target_directory is invalid/non-existent."""
        invalid_path = self.project_root / "non_existent_dir_12345"
        
        with patch('sys.argv', ['script_name', str(invalid_path)]):
            with self.assertRaises(SystemExit) as cm:
                list_files_main()
        self.assertEqual(cm.exception.code, 1)

    @patch('builtins.input', return_value='y')
    def test_main_file_count_warning_proceed(self, mock_input):
        """Test file count warning when user proceeds."""
        for i in range(list_project_files_module.FILE_COUNT_WARNING_THRESHOLD + 1):
            (self.project_root / f"dummy_file_{i}.txt").touch()

        with patch('sys.argv', ['script_name', str(self.project_root), '--depth', '-1']):
            with patch('builtins.open', mock_open()):
                list_files_main()
                mock_input.assert_called_once()

    @patch('builtins.input', return_value='n')
    def test_main_file_count_warning_cancel(self, mock_input):
        """Test file count warning when user cancels."""
        for i in range(list_project_files_module.FILE_COUNT_WARNING_THRESHOLD + 1):
            (self.project_root / f"dummy_file_{i}.txt").touch()

        with patch('sys.argv', ['script_name', str(self.project_root), '--depth', '-1']):
            with self.assertRaises(SystemExit) as cm:
                list_files_main()
            mock_input.assert_called_once()
            self.assertEqual(cm.exception.code, 0)

    @patch('builtins.input', side_effect=KeyboardInterrupt("User aborted"))
    def test_main_file_count_warning_keyboard_interrupt(self, mock_input):
        """Test file count warning when user cancels with KeyboardInterrupt."""
        for i in range(list_project_files_module.FILE_COUNT_WARNING_THRESHOLD + 1):
            (self.project_root / f"dummy_file_{i}.txt").touch()

        with patch('sys.argv', ['script_name', str(self.project_root), '--depth', '-1']):
            with self.assertRaises(SystemExit) as cm:
                list_files_main()
            mock_input.assert_called_once()
            self.assertEqual(cm.exception.code, 0)

    @patch('builtins.input', return_value='y') # Added to handle input prompt
    @patch('pathlib.Path.iterdir', autospec=True) # Ensure autospec=True is applied here
    def test_main_bfs_permission_error_in_subdir(self, mock_iterdir, mock_input):
        """Test main's BFS logic when a subdirectory causes PermissionError."""
        mock_problem_dir_in_bfs = self.project_root / "bfs_problem_dir"
        mock_problem_dir_in_bfs.mkdir()

        mock_root_test_file = self.project_root / "root_test_file.py"
        mock_root_test_file.touch() # Ensure this file exists for checks

        # Define side_effect to return specific lists of children for controlled mocking
        # and raise error for the problem directory. This prevents RecursionError.
        def custom_iterdir_bfs_side_effect(mock_self_path_instance, *args, **kwargs):
            if mock_self_path_instance == self.project_root:
                # When iterdir is called on the project root, return a controlled list of its children
                return iter([mock_problem_dir_in_bfs, mock_root_test_file])
            elif mock_self_path_instance == mock_problem_dir_in_bfs:
                # When iterdir is called on mock_problem_dir, raise the PermissionError
                raise PermissionError("Mock Permission Denied during BFS iteration")
            # For any other directory that might be iterated (e.g., if we had deeper structure),
            # return an empty iterator.
            return iter([]) 

        mock_iterdir.side_effect = custom_iterdir_bfs_side_effect

        with patch('sys.argv', ['script_name', str(self.project_root), '--depth', '1']):
            list_files_main()

        report_path = self.project_root / "output" / list_project_files_module.REPORT_SUBDIR / "project_structure_report_depth_1.txt"
        self.assertTrue(report_path.exists())
        report_content = report_path.read_text(encoding='utf-8')
        
        self.assertIn("bfs_problem_dir/  (Cannot Access)", report_content)
        self.assertIn("root_test_file.py", report_content)

    @patch('builtins.input', return_value='y') # Added to handle input prompt
    def test_main_collects_other_key_files(self, mock_input):
        """Test that main correctly identifies and lists 'other_key_files_summary'."""
        result = self._run_script_as_subprocess("--depth", "0", str(self.project_root)) # Pass target_directory explicitly
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}\n{result.stdout}")
        
        report_path = self.project_root / "output" / list_project_files_module.REPORT_SUBDIR / "project_structure_report_depth_0.txt"
        self.assertTrue(report_path.exists(), f"Report file not created at {report_path}") # Added check here
        report_content = report_path.read_text(encoding='utf-8')
        
        self.assertIn("--- Summary: Key Files at Project Root ---", report_content)
        self.assertIn("./.env", report_content)
        self.assertIn("./config.py", report_content)
        self.assertIn("./keys.py", report_content)
        self.assertIn("./main.py", report_content)
        self.assertIn("./noon_price_predictor.py", report_content)
        self.assertIn("./README.md", report_content)
        self.assertIn("./requirements.txt", report_content)

# --- Unit Tests for get_project_root() ---

class TestGetProjectRoot(unittest.TestCase):
    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.mock_root_path = pathlib.Path(self.temp_dir_obj.name)
        
        # Create dummy project markers for positive heuristic checks
        (self.mock_root_path / "config.py").touch()
        (self.mock_root_path / "README.md").touch()

        self.original_getcwd = os.getcwd()
        self.original_file_attr = getattr(list_project_files_module, '__file__', None) # Store original __file__

    def tearDown(self):
        # Explicitly restore __file__ before cleanup to avoid PermissionError
        if self.original_file_attr is not None:
            list_project_files_module.__file__ = self.original_file_attr
        elif hasattr(list_project_files_module, '__file__'):
            delattr(list_project_files_module, '__file__')
        
        os.chdir(self.original_getcwd)
        self.temp_dir_obj.cleanup()

    def test_get_project_root_successful_detection(self):
        """Test default successful detection when __file__ is available and heuristic passes."""
        # Simulate list_project_files.py being at self.mock_root_path/src/list_project_files.py
        mock_script_path = self.mock_root_path / "src" / "list_project_files.py"
        mock_script_path.parent.mkdir(parents=True, exist_ok=True) # Create 'src' dir
        mock_script_path.touch() # Create the dummy script file

        # For patching module level __file__, it's safer to directly assign/delete it
        # as patch.object might have issues with special module attributes.
        original_file = getattr(list_project_files_module, '__file__', None) # Save original
        list_project_files_module.__file__ = str(mock_script_path)
        try:
            result = get_project_root()
            self.assertEqual(result, self.mock_root_path.resolve(),
                             f"Expected {self.mock_root_path.resolve()}, got {result}")
        finally:
            # Restore original __file__
            if original_file is not None:
                list_project_files_module.__file__ = original_file
            elif hasattr(list_project_files_module, '__file__'):
                delattr(list_project_files_module, '__file__')

    def test_get_project_root_name_error_fallback_to_utilities_parent(self):
        """Test fallback when __file__ causes NameError and CWD is 'utilities' with config.py in parent."""
        mock_cwd_utilities = self.mock_root_path / "utilities"
        mock_cwd_utilities.mkdir()

        os.chdir(mock_cwd_utilities)

        # To simulate NameError for __file__, delete it from the module
        if hasattr(list_project_files_module, '__file__'):
            delattr(list_project_files_module, '__file__')

        with patch('builtins.print') as mock_print:
            with patch('pathlib.Path.cwd', return_value=mock_cwd_utilities):
                # Ensure the mock_root_path has config.py and README.md (from setUp)
                result = get_project_root()
                self.assertEqual(result, self.mock_root_path.resolve())
                mock_print.assert_any_call("Warning: __file__ not defined. Attempting to use CWD's parent as project root.")
                self.assertFalse(any("Using current working directory as project root" in call.args[0] for call in mock_print.call_args_list))

    def test_get_project_root_name_error_fallback_to_cwd(self):
        """Test fallback when __file__ causes NameError and CWD is not 'utilities' or parent lacks config.py."""
        os.chdir(self.mock_root_path)
        
        # Remove config.py and README.md from mock_root_path to fail heuristic for the CWD's parent check
        (self.mock_root_path / "config.py").unlink()
        (self.mock_root_path / "README.md").unlink()

        # To simulate NameError for __file__, delete it from the module
        if hasattr(list_project_files_module, '__file__'):
            delattr(list_project_files_module, '__file__')

        with patch('builtins.print') as mock_print:
            with patch('pathlib.Path.cwd', return_value=self.mock_root_path):
                # Ensure mock.Path.exists correctly reports missing files
                # Corrected lambda signature to accept the instance (mock_self)
                with patch.object(pathlib.Path, 'exists', autospec=True, side_effect=lambda mock_self, *args, **kwargs: False if mock_self == (self.mock_root_path / "config.py") or mock_self == (self.mock_root_path / "README.md") else DEFAULT):
                    result = get_project_root()
                    self.assertEqual(result, self.mock_root_path.resolve())
                    mock_print.assert_any_call("Warning: __file__ not defined. Attempting to use CWD's parent as project root.")
                    mock_print.assert_any_call(f"  Using current working directory as project root: {self.mock_root_path.resolve()}")

    def test_get_project_root_heuristic_check_fails(self):
        """Test the heuristic check for config.py/README.md in the determined project_root."""
        mock_script_path = self.mock_root_path / "src" / "list_project_files.py"
        mock_script_path.parent.mkdir(parents=True, exist_ok=True)
        mock_script_path.touch()

        # Remove config.py and README.md from self.mock_root_path to fail heuristic
        (self.mock_root_path / "config.py").unlink()
        (self.mock_root_path / "README.md").unlink()

        with patch.object(list_project_files_module, '__file__', str(mock_script_path)):
            with patch('builtins.print') as mock_print:
                # Patch exists() specifically for the heuristic check paths
                # The original .exists() should be used for other path checks (like mock_script_path)
                # Corrected lambda signature to accept the instance (mock_self)
                with patch.object(pathlib.Path, 'exists', autospec=True, side_effect=lambda mock_self, *args, **kwargs: False if mock_self == (self.mock_root_path / "config.py") or mock_self == (self.mock_root_path / "README.md") else DEFAULT):
                    result = get_project_root()
                    self.assertEqual(result, self.mock_root_path.resolve())
                    mock_print.assert_any_call(f"Warning: Heuristic check failed for project root at {self.mock_root_path.resolve()}. "
                                               "config.py or README.md not found. Falling back to script_dir.parent.")

    def test_get_project_root_general_exception_on_file_path(self):
        """Test general exception handling when determining project root from __file__."""
        # This test needs to ensure that the broader 'except Exception' block in get_project_root
        # is hit, rather than just 'except NameError'.
        
        # Ensure __file__ exists temporarily for pathlib.Path(__file__) to be called initially
        mock_script_path = self.mock_root_path / "src" / "list_project_files.py"
        mock_script_path.parent.mkdir(parents=True, exist_ok=True)
        mock_script_path.touch()
        # Temporarily set __file__ on the module for this specific test
        original_file = getattr(list_project_files_module, '__file__', None)
        list_project_files_module.__file__ = str(mock_script_path)

        try:
            with patch('builtins.print') as mock_print:
                # Mock CWD to have a predictable fallback path
                with patch('pathlib.Path.cwd', return_value=self.mock_root_path):
                    # Patch pathlib.Path.resolve to raise a generic Exception when called
                    with patch.object(pathlib.Path, 'resolve', autospec=True, side_effect=Exception("Simulated generic path error")):
                        # The script will try to call pathlib.Path(__file__).resolve() and it will raise this mocked error.
                        # The production code should catch this and fall back to CWD.
                        result = get_project_root()
                        # It should fallback to CWD and print an error message.
                        self.assertEqual(result, self.mock_root_path) 
                        mock_print.assert_any_call(unittest.mock.ANY)
                        self.assertTrue(any("Error resolving script path:" in call.args[0] for call in mock_print.call_args_list))
                        self.assertTrue(any("Falling back to CWD." in call.args[0] for call in mock_print.call_args_list))
        finally:
            # Restore __file__ to its original state after the test
            if original_file is not None:
                list_project_files_module.__file__ = original_file
            elif hasattr(list_project_files_module, '__file__'):
                delattr(list_project_files_module, '__file__')

# --- Unit Tests for count_lines_in_file() ---
class TestCountLinesInFile(unittest.TestCase):
    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = pathlib.Path(self.temp_dir_obj.name)

    def tearDown(self):
        self.temp_dir_obj.cleanup()

    def test_count_lines_in_file_empty(self):
        file_path = self.temp_dir / "empty.txt"
        file_path.touch()
        self.assertEqual(count_lines_in_file(file_path), 0)

    def test_count_lines_in_file_with_content(self):
        file_path = self.temp_dir / "content.txt"
        file_path.write_text("line1\nline2\n\nline3\n  \n", encoding='utf-8')
        self.assertEqual(count_lines_in_file(file_path), 3)

    def test_count_lines_in_file_non_existent(self):
        file_path = self.temp_dir / "non_existent.txt"
        self.assertEqual(count_lines_in_file(file_path), 0)

    def test_count_lines_in_file_permission_denied(self):
        file_path = self.temp_dir / "no_access.txt"
        file_path.touch()
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            self.assertEqual(count_lines_in_file(file_path), 0)
    
    def test_count_lines_in_file_decoding_error(self):
        file_path = self.temp_dir / "bad_encoding.txt"
        with open(file_path, 'wb') as f:
            f.write(b'\x80abc\nline2')
        
        self.assertEqual(count_lines_in_file(file_path), 2)

# === End of tests/test_list_project_files.py ===

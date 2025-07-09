# tests/test_list_project_files.py

import unittest
import os
import tempfile
import subprocess
import sys
import pathlib
from unittest.mock import patch, MagicMock
import configparser

# Ensure the src directory is in the Python path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import functions to be tested directly
from src.list_project_files import (
    main as list_files_main,
    generate_file_listing,
    count_lines_in_file
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
        
        # Create a standard mock project structure
        self.output_dir = self.project_root / "output"
        self.output_dir.mkdir()
        
        self.src_dir = self.project_root / "src"
        self.src_dir.mkdir()
        
        (self.project_root / "README.md").touch() # A key file
        (self.project_root / "main.py").write_text("pass", "utf-8")
        (self.project_root / "src" / "module1.py").write_text("pass", "utf-8")
        
        # Excluded items
        (self.project_root / ".venv").mkdir()
        (self.project_root / "test.log").touch()
        
        self.report_path = self.output_dir / "project_reports" / "project_structure_report_depth_-1.txt"

        # FIX: Create a mock config.ini in the temp project root so the script can find it
        # and know where to write the output report.
        mock_config = configparser.ConfigParser()
        mock_config['General'] = {'base_output_dir': 'output'}
        mock_config['Filenames'] = {'project_structure_report': 'project_structure_report.txt'}
        
        with open(self.project_root / "config.ini", "w") as f:
            mock_config.write(f)

    def tearDown(self):
        """Clean up the temporary directory."""
        self.temp_dir_obj.cleanup()

    def _run_script_as_subprocess(self, *args):
        """Helper to run the script as a subprocess for integration testing."""
        script_path = pathlib.Path(__file__).parent.parent / "src" / "list_project_files.py"
        command = [sys.executable, str(script_path), str(self.project_root)] + list(args)
        return subprocess.run(command, capture_output=True, text=True, check=False)

    # --- Integration Tests ---

    def test_integration_happy_path(self):
        """High-level test to ensure the script runs and produces expected output."""
        result = self._run_script_as_subprocess("--depth", "-1")
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
        report_path = self.output_dir / "project_reports" / "project_structure_report_depth_all.txt"
        self.assertTrue(report_path.exists(), "The report file was not created at the expected path.")
        
        # Corrected to use the local 'report_path' variable
        report_content = report_path.read_text(encoding='utf-8')
        self.assertIn("Report generation complete", report_content)
        self.assertIn(os.path.join("src", "module1.py"), report_content)
        self.assertNotIn("test.log", report_content)

    def test_no_py_files_found(self):
        """Verify correct message when no .py files are found."""
        (self.project_root / "main.py").unlink()
        (self.project_root / "src" / "module1.py").unlink()
        
        result = self._run_script_as_subprocess("--depth", "-1")
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
        report_path = self.output_dir / "project_reports" / "project_structure_report_depth_all.txt"
        report_content = report_path.read_text(encoding='utf-8')
        self.assertIn("(No .py files found meeting criteria)", report_content)

    def test_no_key_files_found(self):
        """Verify correct message when no key files are found."""
        (self.project_root / "README.md").unlink()
        
        result = self._run_script_as_subprocess("--depth", "0")
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
        report_path = self.output_dir / "project_reports" / "project_structure_report_depth_0.txt"
        report_content = report_path.read_text(encoding='utf-8')
        self.assertIn("(No predefined key files found at project root)", report_content)

    # --- Unit Tests for Coverage ---

    @patch('pathlib.Path.iterdir', side_effect=PermissionError("Access Denied"))
    def test_generate_listing_handles_permission_error(self, mock_iterdir):
        """Verify that generate_file_listing gracefully handles a PermissionError."""
        mock_outfile = MagicMock()
        mock_outfile.write = MagicMock()
        
        generate_file_listing(mock_outfile, self.project_root, self.project_root, scan_depth=1)
        
        # FIX: The error message in the code is "(Cannot Access)".
        self.assertTrue(any("(Cannot Access)" in call.args[0] for call in mock_outfile.write.call_args_list))

    @patch('src.list_project_files.get_project_root')
    @patch('pathlib.Path.mkdir', side_effect=OSError("Permission denied"))
    def test_main_handles_mkdir_error(self, mock_mkdir, mock_get_root):
        """Verify main() exits if the output directory cannot be created."""
        mock_get_root.return_value = self.project_root
        
        with patch('sys.argv', ['script_name', '--depth', '0']):
            with self.assertRaises(SystemExit) as cm:
                list_files_main()
        self.assertEqual(cm.exception.code, 1)

    @patch('builtins.open', side_effect=IOError("Disk full"))
    def test_main_handles_io_error(self, mock_open):
        """Unit test for the main IOError handler during file writing."""
        with patch('sys.argv', ['script_name', str(self.project_root)]):
            with self.assertRaises(SystemExit) as cm:
                list_files_main()
            self.assertEqual(cm.exception.code, 1)

    @patch('src.list_project_files.datetime')
    def test_main_handles_unexpected_exception(self, mock_datetime):
        """Unit test for the final catch-all exception handler."""
        mock_datetime.now.side_effect = TypeError("Unexpected error")
        with patch('sys.argv', ['script_name', str(self.project_root)]):
            with self.assertRaises(SystemExit) as cm:
                list_files_main()
            self.assertEqual(cm.exception.code, 1)

    def test_count_lines_in_file(self):
        """Unit test for the line counting utility function."""
        test_file = self.project_root / "line_test.txt"
        test_file.write_text("line 1\nline 2\n\n", encoding='utf-8')
        self.assertEqual(count_lines_in_file(test_file), 2)
        
        self.assertEqual(count_lines_in_file(pathlib.Path("non_existent_file.txt")), 0)

if __name__ == '__main__':
    unittest.main()
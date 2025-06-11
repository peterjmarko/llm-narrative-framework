import unittest
from unittest.mock import patch, mock_open
import os
import sys
import shutil
import tempfile
import subprocess

# This script is designed to be run from the project root.
# It tests the reprocess_runs.py coordinator script.

# Define path to the real 'src' directory to copy the script under test
REAL_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestReprocessRuns(unittest.TestCase):

    def setUp(self):
        """Set up a temporary project environment for the reprocessor test."""
        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="test_reprocess_")
        self.test_project_root = self.test_project_root_obj.name

        self.src_dir = os.path.join(self.test_project_root, 'src')
        self.output_dir = os.path.join(self.test_project_root, 'output')
        os.makedirs(self.src_dir)
        os.makedirs(self.output_dir)

        self.original_sys_path = list(sys.path)
        sys.path.insert(0, self.src_dir)

        self.mock_run_dir = os.path.join(self.output_dir, "run_20240101_120000_rep-01_mock")
        os.makedirs(self.mock_run_dir)

        self.stale_report_path = os.path.join(self.mock_run_dir, "replication_report_stale.txt")
        with open(self.stale_report_path, "w") as f:
            f.write("This is old report content.")

        # --- Copy the REAL reprocessor script into the test src directory ---
        real_reprocess_script_path = os.path.join(REAL_SRC_DIR, "reprocess_runs.py")
        shutil.copy2(real_reprocess_script_path, os.path.join(self.src_dir, "reprocess_runs.py"))

        # --- Create MOCK versions of the scripts IT CALLS ---
        worker_scripts_to_mock = ["process_llm_responses.py", "analyze_performance.py", "compile_results.py"]
        for script_name in worker_scripts_to_mock:
            path = os.path.join(self.src_dir, script_name)
            with open(path, "w") as f:
                # The mock workers don't need to do anything.
                f.write(f"import sys;")

    def tearDown(self):
        """Clean up the temporary directory."""
        # Restore the original sys.path
        sys.path[:] = self.original_sys_path
        self.test_project_root_obj.cleanup()

    @patch('subprocess.run')
    def test_reprocessor_calls_all_stages_and_overwrites_report(self, mock_subprocess_run):
        """
        Tests that reprocess_runs.py calls the processor, analyzer, and compiler
        in the correct order and overwrites the existing report file.
        """
        # Dynamically import the main function from the REAL script
        # which is now runnable since sys.path is correct.
        from reprocess_runs import main as reprocess_main

        # Arrange
        fresh_analysis_output = "This is the new, fresh analysis output."
        def mock_run_side_effect(command, **kwargs):
            script_path = command[1]
            if "analyze_performance.py" in script_path:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout=fresh_analysis_output, stderr="")
            else:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout=f"Mock success for {os.path.basename(script_path)}", stderr="")

        mock_subprocess_run.side_effect = mock_run_side_effect

        # Act
        # Call the imported main function directly, with mocked sys.argv
        cli_args = ['reprocess_runs.py', '--target_dir', self.output_dir]
        with patch.object(sys, 'argv', cli_args):
            reprocess_main()

        # Assert
        self.assertEqual(mock_subprocess_run.call_count, 3, "Expected calls to processor, analyzer, and compiler.")
        
        call_args_list = [call.args[0] for call in mock_subprocess_run.call_args_list]
        
        process_cmd = call_args_list[0]
        self.assertIn("process_llm_responses.py", process_cmd[1])
        self.assertIn(self.mock_run_dir, process_cmd)

        analyze_cmd = call_args_list[1]
        self.assertIn("analyze_performance.py", analyze_cmd[1])
        self.assertIn(self.mock_run_dir, analyze_cmd)

        compile_cmd = call_args_list[2]
        self.assertIn("compile_results.py", compile_cmd[1])
        self.assertIn(self.output_dir, compile_cmd)

        self.assertTrue(os.path.exists(self.stale_report_path))
        with open(self.stale_report_path, 'r') as f:
            report_content = f.read()
        # The new report should contain the generated header AND the new analysis output.
        self.assertIn("REPLICATION RUN REPORT (Re-processed on", report_content)
        self.assertIn(fresh_analysis_output, report_content)

if __name__ == '__main__':
    unittest.main()
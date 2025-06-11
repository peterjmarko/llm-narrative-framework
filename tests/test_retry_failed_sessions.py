import unittest
from unittest.mock import patch
import os
import sys
import shutil
import tempfile
import subprocess

# This script is designed to be run from the project root.
# It tests the retry_failed_sessions.py coordinator script.

# Define path to the real 'src' directory to copy the script under test
REAL_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))

class TestRetryFailedSessions(unittest.TestCase):

    def setUp(self):
        """Set up a temporary project environment for the retry script test."""
        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="test_retry_")
        self.test_project_root = self.test_project_root_obj.name

        # Create mock directories and scripts
        self.src_dir = os.path.join(self.test_project_root, 'src')
        self.output_dir = os.path.join(self.test_project_root, 'output')
        os.makedirs(self.src_dir)
        os.makedirs(self.output_dir)

        worker_scripts_to_mock = ["run_llm_sessions.py", "process_llm_responses.py", "analyze_performance.py", "compile_results.py"]
        for script_name in worker_scripts_to_mock:
            path = os.path.join(self.src_dir, script_name)
            with open(path, "w") as f:
                f.write(f"import sys; print('Mock {script_name} ran'); sys.exit(0)")
        
        # Add the temporary src directory to the path so modules can be imported
        self.original_sys_path = list(sys.path)
        sys.path.insert(0, self.src_dir)

        # --- Copy the REAL retry script into the test environment ---
        real_retry_script_path = os.path.join(REAL_SRC_DIR, "retry_failed_sessions.py")
        self.test_retry_script_path = os.path.join(self.src_dir, "retry_failed_sessions.py")
        shutil.copy2(real_retry_script_path, self.test_retry_script_path)

        # --- Create a mock directory structure with failures ---
        # Run A: Has one success and one failure
        self.run_a_dir = os.path.join(self.output_dir, "run_A_with_failure")
        run_a_queries = os.path.join(self.run_a_dir, "session_queries")
        run_a_responses = os.path.join(self.run_a_dir, "session_responses")
        os.makedirs(run_a_queries); os.makedirs(run_a_responses)
        with open(os.path.join(run_a_queries, "llm_query_001.txt"), "w") as f: f.write("q1")
        with open(os.path.join(run_a_queries, "llm_query_002.txt"), "w") as f: f.write("q2")
        with open(os.path.join(run_a_responses, "llm_response_001.txt"), "w") as f: f.write("r1")
        # Note: No response file for query 002, simulating a failure.

        # Run B: Is completely successful
        self.run_b_dir = os.path.join(self.output_dir, "run_B_all_success")
        run_b_queries = os.path.join(self.run_b_dir, "session_queries")
        run_b_responses = os.path.join(self.run_b_dir, "session_responses")
        os.makedirs(run_b_queries); os.makedirs(run_b_responses)
        with open(os.path.join(run_b_queries, "llm_query_001.txt"), "w") as f: f.write("q1")
        with open(os.path.join(run_b_responses, "llm_response_001.txt"), "w") as f: f.write("r1")

    def tearDown(self):
        """Clean up the temporary directory."""
        # Restore the original sys.path
        sys.path[:] = self.original_sys_path
        self.test_project_root_obj.cleanup()

    @patch('subprocess.run')
    def test_retry_script_finds_and_fixes_failures(self, mock_subprocess_run):
        """
        Tests that the retry script correctly identifies specific failures,
        calls the session runner to fix them, and then re-runs the analysis
        only on the affected directories.
        """
        # Dynamically import the main function from the REAL script
        from retry_failed_sessions import main as retry_main

        # Arrange
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="Mock success", stderr="")

        # Act
        cli_args = ['retry_failed_sessions.py', '--parent_dir', self.output_dir]
        with patch.object(sys, 'argv', cli_args):
            retry_main()

        # Assert
        # 1. Verify the total number of subprocess calls
        # 1 for retry, 1 for process, 1 for analyze, 1 for compile = 4 total
        self.assertEqual(mock_subprocess_run.call_count, 4)

        # 2. Get the list of all commands that were run
        call_args_list = [call.args[0] for call in mock_subprocess_run.call_args_list]

        # 3. Assert the retry call is correct
        retry_call_cmd = call_args_list[0]
        self.assertIn("run_llm_sessions.py", retry_call_cmd[1])
        self.assertIn("--run_output_dir", retry_call_cmd)
        self.assertIn(self.run_a_dir, retry_call_cmd) # Must target the failed run dir
        self.assertIn("--start_index", retry_call_cmd)
        self.assertIn("2", retry_call_cmd) # Must target the failed index 2
        self.assertIn("--end_index", retry_call_cmd)
        self.assertIn("--force-rerun", retry_call_cmd)

        # 4. Assert the analysis calls target the corrected directory
        process_call_cmd = call_args_list[1]
        self.assertIn("process_llm_responses.py", process_call_cmd[1])
        self.assertIn("--run_output_dir", process_call_cmd)
        self.assertIn(self.run_a_dir, process_call_cmd) # Must only re-analyze run_A

        analyze_call_cmd = call_args_list[2]
        self.assertIn("analyze_performance.py", analyze_call_cmd[1])
        self.assertIn("--run_output_dir", analyze_call_cmd)
        self.assertIn(self.run_a_dir, analyze_call_cmd) # Must only re-analyze run_A

        # 5. Assert the final compile call is correct
        compile_call_cmd = call_args_list[3]
        self.assertIn("compile_results.py", compile_call_cmd[1])
        self.assertIn(self.output_dir, compile_call_cmd) # Compiler runs on the parent dir

if __name__ == '__main__':
    unittest.main()
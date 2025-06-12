import unittest
import os
import sys
import shutil
import tempfile
import subprocess

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

        # --- Copy the REAL retry script AND create MOCK versions of its dependencies ---
        shutil.copy2(os.path.join(REAL_SRC_DIR, "retry_failed_sessions.py"), self.src_dir)
        
        # Create minimal, working mocks for all scripts called by the retry script
        scripts_to_mock = [
            "run_llm_sessions.py", "reprocess_runs.py", "compile_results.py",
            "process_llm_responses.py", "analyze_performance.py"
        ]
        for script_name in scripts_to_mock:
            mock_path = os.path.join(self.src_dir, script_name)
            with open(mock_path, "w") as f:
                # The mock just needs to print something and exit successfully.
                f.write(f"#!/usr/bin/env python3\nimport sys\nprint('Mock {script_name} ran with args: {{sys.argv[1:]}}')\nsys.exit(0)")

        # --- Create a mock directory structure with failures ---
        self.run_a_dir = os.path.join(self.output_dir, "run_A_with_failure")
        run_a_queries = os.path.join(self.run_a_dir, "session_queries")
        run_a_responses = os.path.join(self.run_a_dir, "session_responses")
        os.makedirs(run_a_queries); os.makedirs(run_a_responses)
        with open(os.path.join(run_a_queries, "llm_query_001.txt"), "w") as f: f.write("q1")
        with open(os.path.join(run_a_queries, "llm_query_002.txt"), "w") as f: f.write("q2")
        with open(os.path.join(run_a_responses, "llm_response_001.txt"), "w") as f: f.write("r1")

        self.run_b_dir = os.path.join(self.output_dir, "run_B_all_success")
        run_b_queries = os.path.join(self.run_b_dir, "session_queries")
        run_b_responses = os.path.join(self.run_b_dir, "session_responses")
        os.makedirs(run_b_queries); os.makedirs(run_b_responses)
        with open(os.path.join(run_b_queries, "llm_query_001.txt"), "w") as f: f.write("q1")
        with open(os.path.join(run_b_responses, "llm_response_001.txt"), "w") as f: f.write("r1")

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_project_root_obj.cleanup()

    def test_retry_script_finds_and_fixes_failures(self):
        """
        Tests that the retry script correctly identifies specific failures,
        and calls the appropriate worker scripts.
        """
        # Arrange
        cli_args = [
            sys.executable,
            os.path.join(self.src_dir, "retry_failed_sessions.py"),
            self.output_dir
        ]
        
        # Act
        result = subprocess.run(cli_args, capture_output=True, text=True, cwd=self.test_project_root)

        # Assert
        self.assertEqual(result.returncode, 1, f"Script should exit 1 after repairs. Stderr:\n{result.stderr}")
        
        output = result.stdout
        self.assertIn("Found 1 failed session(s) at indices [2]", output)
        self.assertIn("Submitting 1 tasks for: run_A_with_failure", output)
        self.assertIn("Retry Phase Complete: 1 successful, 0 failed.", output)
        self.assertIn("Re-analyzing 'run_A_with_failure'", output)
        # Check that the mock scripts were called.
        self.assertIn("Mock run_llm_sessions.py ran", output)
        self.assertIn("Mock process_llm_responses.py ran", output)
        self.assertIn("Mock compile_results.py ran", output)

    def test_manual_retry_rejects_invalid_args(self):
        """
        Tests that the script exits when --indices is used incorrectly.
        """
        # Arrange: try to use --indices with a parent directory, which is not allowed.
        cli_args = [
            sys.executable,
            os.path.join(self.src_dir, "retry_failed_sessions.py"),
            self.output_dir,
            '--indices', '1', '2'
        ]

        # Act
        result = subprocess.run(cli_args, capture_output=True, text=True, cwd=self.test_project_root)

        # Assert
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: --indices can only be used when specifying a single run directory", result.stderr)

if __name__ == '__main__':
    unittest.main()
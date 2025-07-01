import unittest
import os
import sys
import shutil
import tempfile
import subprocess

# Path to the real 'src' directory where the script and its dependencies live
REAL_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
# The project root, where the final .coverage file should live
PROJECT_ROOT = os.path.abspath(os.path.join(REAL_SRC_DIR, '..'))

class TestRetryFailedSessions(unittest.TestCase):

    def setUp(self):
        """
        Set up a temporary environment and mock the script's dependencies in-place.
        """
        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="test_retry_")
        self.test_project_root = self.test_project_root_obj.name
        self.output_dir = os.path.join(self.test_project_root, 'output')
        os.makedirs(self.output_dir)

        # --- In-Place Mocking Strategy ---
        self.scripts_to_restore = []
        scripts_to_mock = [
            "run_llm_sessions.py", "compile_results.py",
            "process_llm_responses.py", "analyze_performance.py"
        ]
        
        for script_name in scripts_to_mock:
            real_path = os.path.join(REAL_SRC_DIR, script_name)
            backup_path = real_path + ".bak"
            
            if os.path.exists(real_path):
                os.rename(real_path, backup_path)
                self.scripts_to_restore.append((backup_path, real_path))

            with open(real_path, "w") as f:
                f.write(f"#!/usr/bin/env python3\nimport sys\nprint('Mock {script_name} ran successfully.')\nsys.exit(0)")

        # --- Create a mock directory structure with failures ---
        self.run_a_dir = os.path.join(self.output_dir, "run_A_failure_L0")
        run_a_queries = os.path.join(self.run_a_dir, "session_queries")
        run_a_responses = os.path.join(self.run_a_dir, "session_responses")
        os.makedirs(run_a_queries); os.makedirs(run_a_responses)
        with open(os.path.join(run_a_queries, "llm_query_002.txt"), "w") as f: f.write("q2")

        level1_dir = os.path.join(self.output_dir, "level1")
        os.makedirs(level1_dir)
        self.run_c_dir = os.path.join(level1_dir, "run_C_failure_L1")
        run_c_queries = os.path.join(self.run_c_dir, "session_queries")
        run_c_responses = os.path.join(self.run_c_dir, "session_responses")
        os.makedirs(run_c_queries); os.makedirs(run_c_responses)
        with open(os.path.join(run_c_queries, "llm_query_004.txt"), "w") as f: f.write("q4")

    def tearDown(self):
        """
        Restore the original scripts and clean up the temporary directory.
        """
        for backup_path, real_path in self.scripts_to_restore:
            if os.path.exists(real_path):
                os.remove(real_path)
            if os.path.exists(backup_path):
                os.rename(backup_path, real_path)
        
        self.test_project_root_obj.cleanup()
    
    def _mock_script(self, script_name, exit_code=0, message=""):
        """Helper to create a mock script with a specific exit code."""
        real_path = os.path.join(REAL_SRC_DIR, script_name)
        backup_path = real_path + ".bak"
        
        if not any(real_path in pair for pair in self.scripts_to_restore):
             if os.path.exists(real_path):
                os.rename(real_path, backup_path)
                self.scripts_to_restore.append((backup_path, real_path))

        with open(real_path, "w") as f:
            f.write(f"#!/usr/bin/env python3\nimport sys\n"
                    f"print('Mock {script_name} ran. {message}')\n"
                    f"sys.exit({exit_code})")

    def _run_script(self, *args):
        """
        Helper to run the REAL script under coverage in a subprocess, ensuring
        the coverage data file is written to the project root.
        """
        real_script_path = os.path.join(REAL_SRC_DIR, 'retry_failed_sessions.py')

        command = [
            sys.executable, "-m", "coverage", "run",
            "--parallel-mode",
            real_script_path
        ] + list(args)
        
        # THIS IS THE KEY: Run the subprocess from the main project root.
        # This makes coverage write its data files to a persistent location
        # instead of the temporary directory that gets deleted.
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

    def test_depth_0_finds_only_top_level_failures(self):
        result = self._run_script(self.output_dir, "--depth", "0")
        self.assertEqual(result.returncode, 1, f"Script should exit 1 after repairs. Stderr:\n{result.stderr}")
        self.assertIn("Found 1 failed session(s) in run_A_failure_L0", result.stdout)
        self.assertNotIn("run_C_failure_L1", result.stdout)

    def test_depth_1_finds_nested_failures(self):
        result = self._run_script(self.output_dir, "--depth", "1")
        self.assertEqual(result.returncode, 1, f"Script should exit 1 after repairs. Stderr:\n{result.stderr}")
        self.assertIn("Found 1 failed session(s) in run_A_failure_L0", result.stdout)
        self.assertIn("Found 1 failed session(s) in run_C_failure_L1", result.stdout)

    def test_depth_minus_1_finds_all_failures_recursively(self):
        result = self._run_script(self.output_dir, "--depth", "-1")
        self.assertEqual(result.returncode, 1, f"Script should exit 1 after repairs. Stderr:\n{result.stderr}")
        self.assertIn("Found 1 failed session(s) in run_A_failure_L0", result.stdout)
        self.assertIn("Found 1 failed session(s) in run_C_failure_L1", result.stdout)

    def test_no_failures_found(self):
        os.remove(os.path.join(self.run_a_dir, "session_queries", "llm_query_002.txt"))
        os.remove(os.path.join(self.run_c_dir, "session_queries", "llm_query_004.txt"))
        result = self._run_script(self.output_dir, "--depth", "-1")
        self.assertEqual(result.returncode, 0, f"Script should exit 0 when no work is done. Stderr:\n{result.stderr}")
        self.assertIn("No sessions to retry. Nothing to do.", result.stdout)

    def test_manual_retry_rejects_invalid_args(self):
        result = self._run_script(self.output_dir, '--indices', '1', '2')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error: --indices can only be used when specifying a single run directory", result.stderr)
    
    def test_successful_manual_retry(self):
        """Tests the successful path for manual retry with --indices."""
        result = self._run_script(self.run_a_dir, '--indices', '2')
        self.assertEqual(result.returncode, 1, f"Script should exit 1 after repairs. Stderr:\n{result.stderr}")
        # For manual retries, the script does NOT scan, it goes straight to retrying.
        self.assertNotIn("Scanning for failed sessions", result.stdout)
        self.assertIn("Submitting 1 tasks for: run_A_failure_L0", result.stdout)
        self.assertIn("Retry Phase Complete: 1 successful, 0 failed.", result.stdout)

    def test_retry_phase_handles_worker_failure(self):
        """Tests that a failure during the retry of a worker script is caught."""
        self._mock_script("run_llm_sessions.py", exit_code=1, message="Intentional failure")

        result = self._run_script(self.output_dir, "--depth", "0")
        # The script exits 1 when no sessions are successfully repaired. This is correct.
        self.assertEqual(result.returncode, 1, f"Script should exit 1 on total retry failure. Stderr:\n{result.stderr}")
        self.assertIn("Retry Phase Complete: 0 successful, 1 failed.", result.stdout)
        self.assertIn("No sessions were successfully retried. Halting before re-analysis.", result.stdout)
        self.assertIn("Retry for index 2 in run_A_failure_L0 FAILED", result.stdout)

    def test_script_exits_if_target_is_not_a_directory(self):
        """Tests that the script exits if the main argument is a file."""
        dummy_file = os.path.join(self.test_project_root, "dummy_file.txt")
        with open(dummy_file, "w") as f:
            f.write("I am not a directory.")
            
        result = self._run_script(dummy_file)
        self.assertNotEqual(result.returncode, 0)
        # The script's logging is configured to use stdout, so we check there.
        self.assertIn("Error: Target directory does not exist", result.stdout)
    
    def test_ignores_malformed_query_filename(self):
        """Tests that a query file with a non-integer index is ignored."""
        # Create a malformed query file that should be skipped by the scanner.
        with open(os.path.join(self.run_a_dir, "session_queries", "llm_query_bad.txt"), "w") as f:
            f.write("this file should be ignored")
        
        # Run the script. It should still find the one valid failure.
        result = self._run_script(self.output_dir, "--depth", "0")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Found 1 failed session(s) in run_A_failure_L0", result.stdout)
        # Ensure the script did not log an error for the bad file.
        self.assertNotIn("ValueError", result.stderr)
        self.assertNotIn("TypeError", result.stderr)

    def test_exits_if_required_script_is_missing(self):
        """Tests that the script fails gracefully if a dependency is missing."""
        # Hide one of the required scripts.
        os.remove(os.path.join(REAL_SRC_DIR, "analyze_performance.py"))

        result = self._run_script(self.output_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Error: Could not find required script", result.stdout)

    def test_manual_mode_requires_indices(self):
        """Tests that using a specific run directory requires the --indices flag."""
        # Target a specific run directory but omit the required --indices flag.
        result = self._run_script(self.run_a_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("The --indices argument is required", result.stderr)

    def test_handles_failure_in_analysis_phase(self):
        """Tests that a failure during re-analysis is caught and reported."""
        # Make the analysis script fail after a successful retry.
        self._mock_script("process_llm_responses.py", exit_code=1, message="Analysis Error")

        result = self._run_script(self.output_dir, "--depth", "0")
        self.assertNotEqual(result.returncode, 0)
        # The retry itself should succeed.
        self.assertIn("Retry Phase Complete: 1 successful, 0 failed.", result.stdout)
        # The script should then fail and report the error during the analysis update.
        self.assertIn("A failure occurred during the analysis update phase", result.stdout)
        self.assertIn("Analysis Error", result.stdout) # Check for the mock script's error message

if __name__ == '__main__':
    unittest.main()
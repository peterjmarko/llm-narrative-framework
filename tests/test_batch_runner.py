import unittest
import os
import sys
import shutil
import tempfile
import subprocess
import platform

# This script is designed to be run from the project root by pytest
# It tests the PowerShell batch runner script.

class TestBatchRunner(unittest.TestCase):

    def setUp(self):
        """Set up a temporary project environment for the batch runner test."""
        if platform.system() != "Windows":
            self.skipTest("PowerShell batch runner tests are designed for Windows.")

        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="test_batch_runner_")
        self.test_project_root = self.test_project_root_obj.name

        # Create mock directories
        self.src_dir = os.path.join(self.test_project_root, 'src')
        self.output_dir = os.path.join(self.test_project_root, 'output')
        os.makedirs(self.src_dir)
        os.makedirs(self.output_dir)

        # Copy the real PowerShell script to the test environment
        real_ps1_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'run_replications.ps1'))
        self.test_ps1_path = os.path.join(self.test_project_root, 'run_replications.ps1')
        shutil.copy2(real_ps1_path, self.test_ps1_path)
        
        # --- Create a MOCK orchestrate_experiment.py ---
        mock_orchestrator_path = os.path.join(self.src_dir, 'orchestrate_experiment.py')
        mock_orchestrator_code = f"""
import sys, os, datetime, json, argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replication_num', required=True, type=int)
    # Add other args to prevent "unrecognized arguments" error
    parser.add_argument('-m', type=int)
    parser.add_argument('-k', type=int)
    parser.add_argument('--base_seed', type=int)
    parser.add_argument('--qgen_base_seed', type=int)
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()

    # --- SIMULATE FAILURE for a specific replication number ---
    if args.replication_num == 2:
        print("Simulating failure for replication 2", file=sys.stderr)
        sys.exit(1)

    # --- SIMULATE SUCCESS ---
    run_dir_name = f"run_{{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}}_rep-{{args.replication_num:02d}}_mock"
    run_dir_path = os.path.join('output', run_dir_name)
    os.makedirs(run_dir_path, exist_ok=True)
    
    report_path = os.path.join(run_dir_path, f"replication_report_{{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}}.txt")
    
    # Create a predictable JSON block for parsing
    metrics = {{
        'mean_mrr': 0.85 + (args.replication_num / 100.0),
        'mean_top_1_acc': 0.80 + (args.replication_num / 100.0)
    }}
    
    # Simulate that parsing was successful
    report_content = f"Final Status: COMPLETED\\n"
    report_content += f"Parsing Status: 100/100 responses parsed\\n"
    report_content += '<<<METRICS_JSON_START>>>\\n'
    report_content += json.dumps(metrics)
    report_content += '\\n<<<METRICS_JSON_END>>>'
    
    with open(report_path, 'w') as f:
        f.write(report_content)
    
    print(f"Mock orchestrator ran successfully for replication {{args.replication_num}}.")
    sys.exit(0)

if __name__ == '__main__':
    main()
"""
        with open(mock_orchestrator_path, 'w') as f:
            f.write(mock_orchestrator_code)

        # --- Create a MOCK compile_results.py ---
        mock_compiler_path = os.path.join(self.src_dir, 'compile_results.py')
        mock_compiler_code = """
import sys, os
# Simulate creating the final CSV
output_dir = sys.argv[1] if len(sys.argv) > 1 else 'output'
final_csv_path = os.path.join(output_dir, 'final_summary_results.csv')
with open(final_csv_path, 'w') as f:
    f.write("header1,header2\\n")
    f.write("data1,data2\\n")
print("Mock compiler ran successfully.")
sys.exit(0)
"""
        with open(mock_compiler_path, 'w') as f:
            f.write(mock_compiler_code)

        # --- Create a MOCK retry_failed_sessions.py ---
        mock_retry_path = os.path.join(self.src_dir, 'retry_failed_sessions.py')
        # This mock will exit 0, indicating no remaining failures.
        with open(mock_retry_path, 'w') as f:
            f.write("import sys; print('Mock retry script: no failures found.'); sys.exit(0)")

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_project_root_obj.cleanup()

    def test_batch_runner_happy_path(self):
        """Tests a successful run of the batch script with 2 replications."""
        # Arrange
        start_rep = 1
        end_rep = 1 # Run only one for a quick happy path test

        # Act
        # Execute the PowerShell script from the temporary project root
        # Use -ExecutionPolicy Bypass to ensure the script can run in restricted environments.
        result = subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", self.test_ps1_path, "-Start", str(start_rep), "-End", str(end_rep)],
            cwd=self.test_project_root,
            capture_output=True,
            text=True
        )

        # Assert
        self.assertEqual(result.returncode, 0, f"PowerShell script failed. STDERR:\n{result.stderr}")
        
        # Check console output
        self.assertIn("RUNNING GLOBAL REPLICATION 1", result.stdout)
        self.assertIn("Replication 1 finished", result.stdout)
        self.assertIn("BATCH RUN COMPLETE - COMPILING FINAL RESULTS", result.stdout)
        self.assertIn("Batch run finished", result.stdout)

        # Check file system artifacts
        batch_log_path = os.path.join(self.output_dir, 'batch_run_log.csv')
        self.assertTrue(os.path.exists(batch_log_path))
        with open(batch_log_path, 'r') as f:
            log_content = f.read()
            self.assertIn("COMPLETED", log_content)
            self.assertNotIn("FAILED", log_content)
            # Check for the new parsing status column
            self.assertIn("100/100 responses parsed", log_content)
            # Check for the parsed metrics
            self.assertIn("0.8600", log_content) # MRR = 0.85 + 1/100
            self.assertIn("81.00%", log_content) # Top1 Acc = 0.80 + 1/100

        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'final_summary_results.csv')))

    def test_batch_runner_failure_path(self):
        """Tests that the batch script handles a failure in one replication and continues."""
        # Arrange
        start_rep = 1
        end_rep = 3 # Run 3 reps, where rep #2 is designed to fail

        # Act
        result = subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", self.test_ps1_path, "-Start", str(start_rep), "-End", str(end_rep)],
            cwd=self.test_project_root,
            capture_output=True,
            text=True
        )

        # Assert
        self.assertEqual(result.returncode, 0, "PowerShell script should finish successfully even if one replication fails.")
        
        # Check console output
        self.assertIn("RUNNING GLOBAL REPLICATION 1", result.stdout)
        self.assertIn("RUNNING GLOBAL REPLICATION 2", result.stdout)
        self.assertIn("RUNNING GLOBAL REPLICATION 3", result.stdout)
        self.assertIn("Orchestrator failed on replication 2", result.stdout)

        # Check batch log file for correct status
        batch_log_path = os.path.join(self.output_dir, 'batch_run_log.csv')
        self.assertTrue(os.path.exists(batch_log_path))
        with open(batch_log_path, 'r') as f:
            log_content = f.read()

        # Check that the log contains the expected outcomes, accounting for PowerShell's CSV quoting.
        self.assertIn('"1","COMPLETED",', log_content)
        self.assertIn('"2","FAILED",', log_content)
        self.assertIn('"3","COMPLETED",', log_content)
        # Check the final summary row for 2 completed, 1 failed.
        self.assertRegex(log_content, r"Totals,.*,2,1")

        # The final compilation should still run
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'final_summary_results.csv')))

if __name__ == '__main__':
    unittest.main()
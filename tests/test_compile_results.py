import unittest
import os
import sys
import shutil
import tempfile
import csv
import subprocess
import configparser
import json

# Path to the real 'src' directory and the script under test
REAL_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
COMPILE_RESULTS_SCRIPT_PATH = os.path.join(REAL_SRC_DIR, 'compile_results.py')
PROJECT_ROOT_TEST = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class TestCompileResultsBase(unittest.TestCase):
    """Base class with setup, teardown, and helper methods."""
    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = self.temp_dir_obj.name

    def tearDown(self):
        self.temp_dir_obj.cleanup()

    def _run_main_script(self, *args):
        """
        Runs the script as a subprocess to simulate command-line execution,
        ensuring it runs under coverage measurement.
        """
        # This command explicitly runs the script under coverage.
        cmd = [
            sys.executable,
            "-m", "coverage", "run",
            "--parallel-mode",
            "--source", REAL_SRC_DIR,  # Use the absolute path to the src directory
            COMPILE_RESULTS_SCRIPT_PATH
        ]
        cmd.extend(args)

        # Set the environment for the subprocess
        env = os.environ.copy()
        
        # --- THIS IS THE CRITICAL FIX ---
        # Force the subprocess to write its coverage data file to the project root.
        # In parallel mode, coverage.py will automatically add a unique suffix.
        # This ensures the data file is not created in the temporary directory.
        env['COVERAGE_FILE'] = os.path.join(PROJECT_ROOT_TEST, '.coverage')

        # Run the subprocess.
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            # The script's CWD is still the temp dir, which is correct for its own file operations.
            cwd=self.temp_dir,
            encoding='utf-8',
            env=env  # Pass the modified environment with the correct data path.
        )

        # This will help debug if any other issue occurs.
        if result.returncode != 0:
            print("--- SUBPROCESS FAILED ---")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            print("-------------------------")

        return result

    def _create_mock_run(self, base_dir, run_name, config_params, metrics_json):
        """Helper to create a mock run directory with config and report files."""
        run_dir = os.path.join(base_dir, run_name)
        os.makedirs(run_dir, exist_ok=True)
        config_path = os.path.join(run_dir, 'config.ini.archived')
        config = configparser.ConfigParser()
        config['LLM'] = config_params
        with open(config_path, 'w') as f:
            config.write(f)
        report_path = os.path.join(run_dir, f"replication_report_{run_name}.txt")
        with open(report_path, "w") as f:
            f.write("<<<METRICS_JSON_START>>>\n")
            f.write(json.dumps(metrics_json) + "\n")
            f.write("<<<METRICS_JSON_END>>>\n")
        return run_dir

    def _read_csv_output(self, file_path):
        """Reads the generated CSV file."""
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            return list(csv.DictReader(f))

class TestCompileResultsHierarchical(TestCompileResultsBase):
    """Tests for the new default 'hierarchical' mode."""

    def setUp(self):
        super().setUp()
        # Create a complex, multi-level directory structure
        self.study_dir = os.path.join(self.temp_dir, "study_A")
        exp1_dir = os.path.join(self.study_dir, "experiment_1")
        exp2_dir = os.path.join(self.study_dir, "experiment_2")

        # Create mock runs
        self._create_mock_run(exp1_dir, "run_A1", {'model': 'gpt-3.5'}, {'mrr': 0.91})
        self._create_mock_run(exp1_dir, "run_A2", {'model': 'gpt-3.5'}, {'mrr': 0.92})
        self._create_mock_run(exp2_dir, "run_B1", {'model': 'gpt-4.0'}, {'mrr': 0.98})

    def test_hierarchical_aggregation(self):
        """Verify that summaries are created at every level with correct row counts."""
        # Run the script in default hierarchical mode
        result = self._run_main_script(self.study_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Running in hierarchical mode", result.stdout)

        # --- Verification ---
        # Level 3 (Run folders)
        run_a1_summary = self._read_csv_output(os.path.join(self.study_dir, "experiment_1", "run_A1", "final_summary_results.csv"))
        self.assertIsNotNone(run_a1_summary)
        self.assertEqual(len(run_a1_summary), 1)

        # Level 2 (Experiment folders)
        exp1_summary = self._read_csv_output(os.path.join(self.study_dir, "experiment_1", "final_summary_results.csv"))
        self.assertIsNotNone(exp1_summary)
        self.assertEqual(len(exp1_summary), 2, "Experiment 1 should aggregate 2 runs")

        exp2_summary = self._read_csv_output(os.path.join(self.study_dir, "experiment_2", "final_summary_results.csv"))
        self.assertIsNotNone(exp2_summary)
        self.assertEqual(len(exp2_summary), 1, "Experiment 2 should aggregate 1 run")

        # Level 1 (Study folder)
        study_summary = self._read_csv_output(os.path.join(self.study_dir, "final_summary_results.csv"))
        self.assertIsNotNone(study_summary)
        self.assertEqual(len(study_summary), 3, "Study should aggregate all 3 runs")
        models = {row['model'] for row in study_summary}
        self.assertEqual(models, {'gpt-3.5', 'gpt-4.0'})


class TestCompileResultsFlat(TestCompileResultsBase):
    """Tests for the legacy 'flat' mode with the --depth argument."""

    def setUp(self):
        super().setUp()
        # Create a nested structure for depth testing
        self.base_dir = os.path.join(self.temp_dir, "flat_test")
        level1_dir = os.path.join(self.base_dir, "level1")
        level2_dir = os.path.join(level1_dir, "level2")
        os.makedirs(level2_dir)

        self._create_mock_run(self.base_dir, "run_0", {'model': 'model0'}, {'mrr': 0.90})
        self._create_mock_run(level1_dir, "run_1", {'model': 'model1'}, {'mrr': 0.91})
        self._create_mock_run(level2_dir, "run_2", {'model': 'model2'}, {'mrr': 0.92})

    def test_flat_mode_depth_0(self):
        """Test flat mode with depth=0, finding only the top-level run."""
        result = self._run_main_script("--mode", "flat", "--depth", "0", self.base_dir)
        self.assertEqual(result.returncode, 0)
        
        master_summary = self._read_csv_output(os.path.join(self.base_dir, "final_summary_results.csv"))
        self.assertIsNotNone(master_summary)
        self.assertEqual(len(master_summary), 1)
        self.assertEqual(master_summary[0]['model'], 'model0')

    def test_flat_mode_depth_minus_1(self):
        """Test flat mode with depth=-1, finding all runs."""
        result = self._run_main_script("--mode", "flat", "--depth", "-1", self.base_dir)
        self.assertEqual(result.returncode, 0)
        
        master_summary = self._read_csv_output(os.path.join(self.base_dir, "final_summary_results.csv"))
        self.assertIsNotNone(master_summary)
        self.assertEqual(len(master_summary), 3)

        # Verify individual summaries were also created
        run_2_summary = self._read_csv_output(os.path.join(self.base_dir, "level1", "level2", "run_2", "final_summary_results.csv"))
        self.assertIsNotNone(run_2_summary)
        self.assertEqual(len(run_2_summary), 1)


if __name__ == '__main__':
    unittest.main()
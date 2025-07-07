import unittest
from unittest.mock import patch
import os
import sys
import tempfile
import csv
import configparser
import json

# Import the script we are testing as a module
import compile_results

# Define absolute paths to key project files and directories
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
COMPILE_RESULTS_SCRIPT_PATH = os.path.join(SRC_DIR, 'compile_results.py')
COVERAGERC_PATH = os.path.join(PROJECT_ROOT, '.coveragerc')

# Add the src directory to the path so modules can be found
sys.path.insert(0, SRC_DIR)

class TestCompileResultsBase(unittest.TestCase):
    """Base class with setup, teardown, and helper methods."""
    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = self.temp_dir_obj.name

    def tearDown(self):
        self.temp_dir_obj.cleanup()

    # The _run_main_script function is no longer needed because we are now
    # importing the script and calling its main() function directly.


    def _create_mock_run(self, base_dir, run_name, config_params, metrics_json, has_bias_metrics=False):
        run_dir = os.path.join(base_dir, run_name)
        os.makedirs(run_dir, exist_ok=True)
        config = configparser.ConfigParser()
        config['LLM'] = config_params
        config['Study'] = {'mapping_strategy': 'correct'}
        with open(os.path.join(run_dir, 'config.ini.archived'), 'w') as f:
            config.write(f)

        # Add a nested positional_bias_metrics block if requested for the test
        if has_bias_metrics:
            metrics_json['positional_bias_metrics'] = {
                'slope': 0.05,
                'p_value': 0.01
            }

        report_path = os.path.join(run_dir, f"replication_report_{run_name}.txt")
        with open(report_path, "w") as f:
            f.write("<<<METRICS_JSON_START>>>\n")
            f.write(json.dumps(metrics_json) + "\n")
            f.write("<<<METRICS_JSON_END>>>\n")
        return run_dir

    def _read_csv_output(self, file_path):
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            return list(csv.DictReader(f))

class TestCompileResultsHierarchical(TestCompileResultsBase):
    """Tests for the new default 'hierarchical' mode."""

    def setUp(self):
        super().setUp()
        self.study_dir = os.path.join(self.temp_dir, "study_A")
        self.exp1_dir = os.path.join(self.study_dir, "experiment_1")
        self.exp2_dir = os.path.join(self.study_dir, "experiment_2")
        # Store the exact path to the run directories created
        self.run_1_dir = self._create_mock_run(self.exp1_dir, "run_rep-1", {'model_name': 'gpt-3.5'}, {'mrr': 0.91}, has_bias_metrics=True)
        self.run_2_dir = self._create_mock_run(self.exp1_dir, "run_rep-2", {'model_name': 'gpt-3.5'}, {'mrr': 0.92})
        self.run_3_dir = self._create_mock_run(self.exp2_dir, "run_rep-3", {'model_name': 'gpt-4.0'}, {'mrr': 0.98})

    def test_hierarchical_aggregation(self):
        """Verify that summaries are created at every level with correct row counts."""
        # 1. Define the command-line arguments the script expects
        test_args = ['compile_results.py', self.study_dir]

        # 2. Use patch.object to temporarily set sys.argv, then call main()
        with patch.object(sys, 'argv', test_args):
            # Assert that the script returns a success code (e.g., 0)
            return_code = compile_results.main()
            self.assertEqual(return_code, 0, "compile_results.main() should return 0 on success.")

        # 3. All assertions now check for file-based side effects.
        
        # --- VERIFICATION (No changes needed) ---
        # Level 3 (REPLICATION): Check the individual run folder for its summary
        run_1_summary = self._read_csv_output(os.path.join(self.run_1_dir, "REPLICATION_results.csv"))
        self.assertIsNotNone(run_1_summary, "REPLICATION_results.csv should exist in run folder.")
        self.assertEqual(len(run_1_summary), 1, "Replication summary should have 1 row.")

        # Level 2 (EXPERIMENT): Check the experiment folder for its aggregated summary
        exp1_summary = self._read_csv_output(os.path.join(self.exp1_dir, "EXPERIMENT_results.csv"))
        self.assertIsNotNone(exp1_summary, "EXPERIMENT_results.csv should exist in experiment folder.")
        self.assertEqual(len(exp1_summary), 2, "Experiment summary should aggregate 2 runs.")

        # Level 1 (STUDY): Check the top-level study folder for the final aggregation
        study_summary = self._read_csv_output(os.path.join(self.study_dir, "STUDY_results.csv"))
        self.assertIsNotNone(study_summary, "STUDY_results.csv should exist in study folder.")
        self.assertEqual(len(study_summary), 3, "Study summary should aggregate all 3 runs.")


class TestCompileResultsEdgeCases(TestCompileResultsBase):
    """Tests for edge cases and error handling."""

    def test_invalid_base_directory(self):
        """Test that the script returns an error code for a non-existent directory."""
        invalid_path = os.path.join(self.temp_dir, "non_existent_dir")
        test_args = ['compile_results.py', invalid_path]

        with patch.object(sys, 'argv', test_args):
            return_code = compile_results.main()
            self.assertEqual(return_code, 1, "Script should return 1 for an invalid path.")

    def test_malformed_report_is_skipped(self):
        """Test that a run with a malformed JSON report is skipped gracefully."""
        # Create one valid run
        self._create_mock_run(self.temp_dir, "run_valid-1", {'model_name': 'abc'}, {'mrr': 0.5})

        # Create one invalid run
        invalid_run_dir = os.path.join(self.temp_dir, "run_invalid-2")
        os.makedirs(invalid_run_dir)
        with open(os.path.join(invalid_run_dir, 'config.ini.archived'), 'w') as f:
            f.write("[LLM]\nmodel_name=xyz")
        with open(os.path.join(invalid_run_dir, 'replication_report_x.txt'), 'w') as f:
            f.write("<<<METRICS_JSON_START>>>\n{this is not valid json\n<<<METRICS_JSON_END>>>")

        test_args = ['compile_results.py', self.temp_dir]
        with patch.object(sys, 'argv', test_args):
            compile_results.main()

        # Check that the final summary only contains the valid run.
        # FIX: The script correctly identifies this level as an "EXPERIMENT"
        # because it contains 'run_*' directories. The test must check for the correct filename.
        summary_path = os.path.join(self.temp_dir, "EXPERIMENT_results.csv")
        summary = self._read_csv_output(summary_path)

        self.assertIsNotNone(summary, f"Expected summary file was not found at {summary_path}")
        self.assertEqual(len(summary), 1, "Summary should only contain the one valid run.")

    def test_run_dir_missing_config_is_skipped(self):
        """Test that a run directory missing its config.ini.archived is skipped."""
        # Create a run directory but forget to add the config file
        run_dir_no_config = os.path.join(self.temp_dir, "run_no_config-1")
        os.makedirs(run_dir_no_config)
        with open(os.path.join(run_dir_no_config, 'replication_report_y.txt'), 'w') as f:
            f.write("<<<METRICS_JSON_START>>>\n{\"mrr\": 0.1}\n<<<METRICS_JSON_END>>>")

        test_args = ['compile_results.py', self.temp_dir]
        with patch.object(sys, 'argv', test_args):
            compile_results.main()

        # The process should complete but no summary file should be created
        summary_path = os.path.join(self.temp_dir, "STUDY_results.csv")
        self.assertFalse(os.path.exists(summary_path), "No summary file should be created if all runs are invalid.")

    def test_empty_summary_file_is_handled(self):
        """Test that an empty summary file from a sub-directory is handled gracefully."""
        exp_dir = os.path.join(self.temp_dir, "experiment")
        os.makedirs(exp_dir)

        # Sub-directory 1 has a valid run
        run_dir_1 = os.path.join(exp_dir, "run_good-1")
        self._create_mock_run(run_dir_1, "run_good-1", {'model_name': 'abc'}, {'mrr': 0.5})

        # Sub-directory 2 has an empty results file (simulating a failed lower-level aggregation)
        empty_dir = os.path.join(exp_dir, "empty_results_dir")
        os.makedirs(empty_dir)
        with open(os.path.join(empty_dir, "EXPERIMENT_results.csv"), 'w') as f:
            pass # Create an empty file

        test_args = ['compile_results.py', self.temp_dir]
        with patch.object(sys, 'argv', test_args):
            compile_results.main()

        summary = self._read_csv_output(os.path.join(self.temp_dir, "STUDY_results.csv"))
        self.assertIsNotNone(summary)
        self.assertEqual(len(summary), 1, "Final summary should correctly aggregate the one valid run.")


if __name__ == '__main__':
    unittest.main()

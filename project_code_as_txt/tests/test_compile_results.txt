import unittest
import os
import sys
import shutil
import tempfile
import json
import csv
import re
import subprocess # Added for running script as subprocess
from unittest.mock import patch, MagicMock
import time

# Path to the real 'src' directory
REAL_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Path to the script under test
COMPILE_RESULTS_SCRIPT_PATH = os.path.join(REAL_SRC_DIR, 'compile_results.py')
PROJECT_ROOT_TEST = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # For pytest.ini path

class TestCompileResults(unittest.TestCase):

    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = self.temp_dir_obj.name
        self.output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.output_dir)

        # Patch sys.stdout and sys.stderr for capturing print statements from the script
        # Note: This patching only affects the current Python process running the test.
        # Subprocess output is captured via subprocess.run(capture_output=True).
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.mock_stdout = MagicMock()
        self.mock_stderr = MagicMock()
        sys.stdout = self.mock_stdout
        sys.stderr = self.mock_stderr

    def tearDown(self):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        self.temp_dir_obj.cleanup()

    def _create_mock_report(self, run_name, header_params, metrics_json_content, output_dir=None):
        """Helper to create a mock replication report file."""
        if output_dir is None:
            output_dir = self.output_dir

        run_dir = os.path.join(output_dir, run_name)
        os.makedirs(run_dir, exist_ok=True)
        report_path = os.path.join(run_dir, f"replication_report_{run_name}.txt")

        # The run_directory in the report content should be the run_name itself,
        # as compile_results.py extracts temp/rep from this string.
        header_lines = [
            f"Run Directory: {run_name}", # Changed this line
            f"LLM Model: {header_params.get('model', 'test-model')}",
            f"Items per Query (k): {header_params.get('k', 5)}",
            f"Num Iterations (m): {header_params.get('m', 10)}",
            f"Personalities Source: {header_params.get('db', 'test_db.txt')}",
        ]
        # Removed lines that would add temperature/replication from header_params,
        # as compile_results.py derives them from the run_directory string itself.

        report_content = "\n".join(header_lines) + "\n\n"
        report_content += "<<<METRICS_JSON_START>>>\n"
        
        # Handle case where metrics_json_content might not be valid JSON (for error testing)
        if isinstance(metrics_json_content, dict):
            report_content += json.dumps(metrics_json_content, indent=2) + "\n"
        else:
            report_content += str(metrics_json_content) + "\n" # Write as string for malformed tests

        report_content += "<<<METRICS_JSON_END>>>\n"

        with open(report_path, "w", encoding='utf-8') as f:
            f.write(report_content)
        return report_path

    def _read_csv_output(self):
        csv_path = os.path.join(self.output_dir, "final_summary_results.csv")
        if not os.path.exists(csv_path):
            return []
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _run_main_script(self, *args):
        # We need to run the script as a subprocess to get accurate coverage
        # and to truly simulate command-line execution.
        coverage_config_path = os.path.join(PROJECT_ROOT_TEST, 'pytest.ini')
        cmd = [
            sys.executable,
            COMPILE_RESULTS_SCRIPT_PATH # Directly run the script
        ]
        cmd.extend(args)

        # Set environment variables for coverage.py in the subprocess
        env = os.environ.copy()
        # This tells the subprocess to start coverage using the specified config file.
        env['COVERAGE_PROCESS_START'] = coverage_config_path
        # Ensure the coverage data file is in the project root and unique.
        env['COVERAGE_FILE'] = os.path.join(PROJECT_ROOT_TEST, f'.coverage.{os.getpid()}.{time.time_ns()}')
        
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.temp_dir, # CWD is important for finding 'output' dir
            encoding='utf-8',
            env=env
        )

    # --- Test Cases ---

    # Helper to import and call functions from the script directly for unit testing
    # This avoids subprocess for unit tests of internal functions, improving speed and debugging.
    def parse_report_header_from_script(self, content):
        # Temporarily add src directory to path to import the script
        sys.path.insert(0, REAL_SRC_DIR) # REAL_SRC_DIR is now defined
        import compile_results
        # Reload module to ensure latest changes are picked up if file was modified
        import importlib
        importlib.reload(compile_results)
        result = compile_results.parse_report_header(content)
        sys.path.pop(0)
        return result

    def parse_metrics_json_from_script(self, content):
        sys.path.insert(0, REAL_SRC_DIR) # REAL_SRC_DIR is now defined
        import compile_results
        import importlib
        importlib.reload(compile_results)
        result = compile_results.parse_metrics_json(content)
        sys.path.pop(0)
        return result

    # Test parse_report_header function
    def test_parse_report_header_full(self):
        report_content = """
        Run Directory: C:/path/to/output/run_k5_m10_db_tmp-0.7_rep-1
        LLM Model: gpt-3.5-turbo
        Items per Query (k): 5
        Num Iterations (m): 10
        Personalities Source: my_personalities.txt
        """
        params = self.parse_report_header_from_script(report_content)
        self.assertEqual(params['run_directory'], "C:/path/to/output/run_k5_m10_db_tmp-0.7_rep-1")
        self.assertEqual(params['model'], "gpt-3.5-turbo")
        self.assertEqual(params['k'], "5")
        self.assertEqual(params['m'], "10")
        self.assertEqual(params['db'], "my_personalities.txt")
        self.assertEqual(params['temperature'], "0.7")
        self.assertEqual(params['replication'], "1")

    def test_parse_report_header_missing_fields(self):
        report_content = """
        Run Directory: C:/path/to/output/run_incomplete
        LLM Model: gpt-4
        """
        params = self.parse_report_header_from_script(report_content)
        self.assertEqual(params['run_directory'], "C:/path/to/output/run_incomplete")
        self.assertEqual(params['model'], "gpt-4")
        self.assertIsNone(params['k'])
        self.assertIsNone(params['m'])
        self.assertIsNone(params['db'])
        self.assertIsNone(params['temperature'])
        self.assertIsNone(params['replication'])

    # Test parse_metrics_json function
    def test_parse_metrics_json_valid(self):
        report_content = """
        Some header info
        <<<METRICS_JSON_START>>>
        {
            "mean_mrr": 0.5,
            "mean_top_1_acc": 0.8
        }
        <<<METRICS_JSON_END>>>
        Some footer info
        """
        metrics = self.parse_metrics_json_from_script(report_content)
        self.assertEqual(metrics, {"mean_mrr": 0.5, "mean_top_1_acc": 0.8})

    def test_parse_metrics_json_missing_tags(self):
        report_content = """
        Some header info
        {
            "mean_mrr": 0.5
        }
        Some footer info
        """
        metrics = self.parse_metrics_json_from_script(report_content)
        self.assertIsNone(metrics)

    def test_parse_metrics_json_malformed_json(self):
        report_content = """
        <<<METRICS_JSON_START>>>
        {
            "mean_mrr": 0.5,
            "mean_top_1_acc": 0.8
        <<<METRICS_JSON_END>>>
        """
        metrics = self.parse_metrics_json_from_script(report_content)
        self.assertIsNone(metrics)

    # Test cases for main function (end-to-end)
    def test_main_successful_compilation(self):
        # header_params should only contain what's directly extracted from lines
        header = {'model': 'gpt-3.5', 'k': 5, 'm': 10, 'db': 'db1'}
        metrics = {'mean_mrr': 0.5, 'mean_top_1_acc': 0.8}
        # run_name should contain the temp/rep info for extraction by compile_results.py
        self._create_mock_report("run_k5_m10_db_tmp-0.7_rep-1", header, metrics)

        result = self._run_main_script(self.output_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Successfully compiled 1 results into:", result.stdout)
        
        csv_data = self._read_csv_output()
        self.assertEqual(len(csv_data), 1)
        self.assertEqual(csv_data[0]['run_directory'], 'run_k5_m10_db_tmp-0.7_rep-1')
        self.assertEqual(csv_data[0]['mean_mrr'], '0.5') # CSV reads as string
        self.assertEqual(csv_data[0]['mean_top_1_acc'], '0.8')
        # Add assertions for temperature and replication, now correctly extracted
        self.assertEqual(csv_data[0]['temperature'], '0.7')
        self.assertEqual(csv_data[0]['replication'], '1')


    def test_main_default_output_dir(self):
        header = {'run_directory': 'run_default', 'model': 'default-model'}
        metrics = {'mean_mrr': 0.6}
        # FIX: Create report in self.output_dir, which is self.temp_dir/output
        self._create_mock_report("run_default", header, metrics, output_dir=self.output_dir) 

        result = self._run_main_script() # No args, should default to 'output'
        self.assertEqual(result.returncode, 0)
        self.assertIn("No output directory specified. Defaulting to './output'", result.stdout)
        self.assertIn("Successfully compiled 1 results into:", result.stdout)
        
        csv_data = self._read_csv_output()
        self.assertEqual(len(csv_data), 1)
        self.assertEqual(csv_data[0]['run_directory'], 'run_default')

    def test_main_output_dir_does_not_exist(self):
        non_existent_dir = os.path.join(self.temp_dir, "non_existent")
        result = self._run_main_script(non_existent_dir)
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"Error: Specified output directory '{non_existent_dir}' does not exist.", result.stdout)

    def test_main_no_report_files_found(self):
        # No reports created in setUp
        result = self._run_main_script(self.output_dir)
        self.assertEqual(result.returncode, 0) # Script exits 0 if no reports found
        self.assertIn(f"No report files found in subdirectories of '{self.output_dir}'.", result.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "final_summary_results.csv")))

    def test_main_report_with_unparsable_json(self):
        header = {'run_directory': 'run_bad_json'}
        # Malformed JSON
        self._create_mock_report("run_bad_json", header, "this is not json") 

        result = self._run_main_script(self.output_dir)
        self.assertEqual(result.returncode, 0) # Script should not crash, just warn
        self.assertIn("Warning: Could not find or parse metrics JSON in replication_report_run_bad_json.txt", result.stdout)
        self.assertIn("No valid results to compile.", result.stdout) # Because the one report was invalid
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "final_summary_results.csv")))

    def test_main_multiple_reports(self):
        # header_params should only contain what's directly extracted from lines
        # run_name should contain the temp/rep info for extraction by compile_results.py
        self._create_mock_report("run_001_tmp-0.1_rep-1", {'model': 'modelA', 'k': 5}, {'mean_mrr': 0.1})
        self._create_mock_report("run_002_tmp-0.2_rep-2", {'model': 'modelB', 'k': 5}, {'mean_mrr': 0.2})
        self._create_mock_report("run_003_tmp-0.3_rep-3", {'model': 'modelC', 'k': 5}, {'mean_mrr': 0.3})

        result = self._run_main_script(self.output_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Successfully compiled 3 results into:", result.stdout)
        
        csv_data = self._read_csv_output()
        self.assertEqual(len(csv_data), 3)
        # Assuming sorted order by run_name
        self.assertEqual(csv_data[0]['replication'], '1')
        self.assertEqual(csv_data[0]['temperature'], '0.1')
        self.assertEqual(csv_data[1]['replication'], '2')
        self.assertEqual(csv_data[1]['temperature'], '0.2')
        self.assertEqual(csv_data[2]['replication'], '3')
        self.assertEqual(csv_data[2]['temperature'], '0.3')

    def test_main_no_valid_results_to_compile(self):
        # Create a report, but with no JSON block
        run_dir = os.path.join(self.output_dir, "run_no_json")
        os.makedirs(run_dir)
        report_path = os.path.join(run_dir, "replication_report_no_json.txt")
        with open(report_path, "w", encoding='utf-8') as f:
            f.write("Run Directory: run_no_json\nLLM Model: test\n") # No JSON tags

        result = self._run_main_script(self.output_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Warning: Could not find or parse metrics JSON in replication_report_no_json.txt", result.stdout)
        self.assertIn("No valid results to compile.", result.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "final_summary_results.csv")))

    def test_main_float_rounding(self):
        header = {'run_directory': 'run_float', 'model': 'test'}
        metrics = {'metric1': 0.1234567, 'metric2': 123.456789, 'metric3': 0.9999999}
        self._create_mock_report("run_float", header, metrics)

        result = self._run_main_script(self.output_dir)
        self.assertEqual(result.returncode, 0)
        
        csv_data = self._read_csv_output()
        self.assertEqual(len(csv_data), 1)
        self.assertEqual(csv_data[0]['metric1'], '0.1235')
        self.assertEqual(csv_data[0]['metric2'], '123.4568')
        self.assertEqual(csv_data[0]['metric3'], '1.0') # 0.9999999 rounds up to 1.0

    def test_main_with_temperature_and_replication_in_run_directory(self):
        # This test specifically ensures that temp and rep are extracted from the run_directory string
        # even if not explicitly provided in the header_params.
        header = {'model': 'test-model', 'k': 5, 'm': 10, 'db': 'test_db.txt'}
        metrics = {'mean_mrr': 0.5}
        # The run_name itself contains the temperature and replication info
        self._create_mock_report("run_k5_m10_db_tmp-0.7_rep-1", header, metrics)

        result = self._run_main_script(self.output_dir)
        self.assertEqual(result.returncode, 0)
        
        csv_data = self._read_csv_output()
        self.assertEqual(len(csv_data), 1)
        self.assertEqual(csv_data[0]['temperature'], '0.7')
        self.assertEqual(csv_data[0]['replication'], '1')
        self.assertEqual(csv_data[0]['run_directory'], 'run_k5_m10_db_tmp-0.7_rep-1') # This should be the run_name from the report
    
    def test_main_comprehensive_metrics_and_header_sorting(self):
        """
        Tests that a comprehensive set of metrics are correctly processed and
        that the CSV header sorting logic (preferred_order vs. alphabetical) works.
        """
        header = {'model': 'complex-model', 'k': 5, 'm': 10, 'db': 'complex_db.txt'}
        metrics = {
            'mean_mrr': 0.55,
            'mrr_p': 0.001,
            'mean_top_1_acc': 0.85,
            'top_1_acc_p': 0.005,
            'mwu_stouffer_z': 1.96,
            'mwu_stouffer_p': 0.05,
            'mwu_fisher_chi2': 10.5, # Added
            'mwu_fisher_p': 0.01,    # Added
            'mean_effect_size_r': 0.3,
            'effect_size_r_p': 0.01,
            'mean_normalized_mrr': 0.6,
            'normalized_mrr_p': 0.002,
            'mean_top_3_acc': 0.9,
            'top_3_acc_p': 0.003,
            'new_custom_metric_Z': 123.45, # A metric not in preferred_order
            'another_custom_metric_A': 67.89, # Another custom metric
        }
        self._create_mock_report("run_complex_tmp-0.5_rep-10", header, metrics)

        result = self._run_main_script(self.output_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Successfully compiled 1 results into:", result.stdout)
        
        csv_data = self._read_csv_output()
        self.assertEqual(len(csv_data), 1)
        
        # Verify some specific values
        self.assertEqual(csv_data[0]['mean_mrr'], '0.55')
        self.assertEqual(csv_data[0]['mrr_p'], '0.001')
        self.assertEqual(csv_data[0]['new_custom_metric_Z'], '123.45')
        self.assertEqual(csv_data[0]['another_custom_metric_A'], '67.89')
        self.assertEqual(csv_data[0]['temperature'], '0.5')
        self.assertEqual(csv_data[0]['replication'], '10')

        # Verify the order of columns in the CSV header
        csv_path = os.path.join(self.output_dir, "final_summary_results.csv")
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header_row = next(reader)
        
        # Define the expected start of the header based on 'preferred_order'
        expected_start_of_header = [
            'run_directory', 'replication', 'model', 'temperature', 'k', 'm', 'db',
            'mwu_stouffer_z', 'mwu_stouffer_p', 'mwu_fisher_chi2', 'mwu_fisher_p',
            'mean_effect_size_r', 'effect_size_r_p',
            'mean_mrr', 'mrr_p',
            'mean_normalized_mrr', 'normalized_mrr_p',
            'mean_top_1_acc', 'top_1_acc_p',
            'mean_top_3_acc', 'top_3_acc_p'
        ]
        
        # Check that the initial columns match the preferred order
        for i, col_name in enumerate(expected_start_of_header):
            self.assertLess(i, len(header_row), f"Header too short. Missing {col_name}")
            self.assertEqual(header_row[i], col_name, f"Column {i} mismatch: Expected '{col_name}', Got '{header_row[i]}'")
        
        # Check that custom metrics are present and appear after preferred ones (alphabetically among themselves)
        self.assertIn('another_custom_metric_A', header_row)
        self.assertIn('new_custom_metric_Z', header_row)
        
        # Ensure 'another_custom_metric_A' comes before 'new_custom_metric_Z' (alphabetical for non-preferred)
        self.assertLess(header_row.index('another_custom_metric_A'), header_row.index('new_custom_metric_Z'))
        # Ensure they appear after the last preferred item (using a known last preferred item)
        self.assertGreater(header_row.index('another_custom_metric_A'), header_row.index('top_3_acc_p'))
    
    def test_main_no_reports_found_exit_path(self):
        """
        Test the scenario where no report files are found at all.
        This should hit the 'if not report_files:' branch.
        """
        # Ensure the output directory is empty, or doesn't even exist before the run
        shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir) # Recreate empty output dir

        result = self._run_main_script(self.output_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn(f"No report files found in subdirectories of '{self.output_dir}'.", result.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "final_summary_results.csv")))
    
    def test_main_no_valid_results_exit_path(self):
        """
        Test the scenario where report files are found, but none contain valid JSON metrics.
        This should hit the 'if not all_results:' branch.
        """
        # Create a report, but with no JSON block, making it invalid
        header = {'run_directory': 'run_invalid_json'}
        self._create_mock_report("run_invalid_json", header, "this is not json and will fail to parse") 

        result = self._run_main_script(self.output_dir)
        self.assertEqual(result.returncode, 0) # Script should not crash, just warn and exit 0
        self.assertIn("Warning: Could not find or parse metrics JSON in replication_report_run_invalid_json.txt", result.stdout)
        self.assertIn("No valid results to compile.", result.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, "final_summary_results.csv")))
import unittest
import os
import sys
import shutil
import tempfile
import subprocess
import csv
import argparse

# Path to the real 'src' directory
REAL_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
# The project root, where the final .coverage file should live
PROJECT_ROOT = os.path.abspath(os.path.join(REAL_SRC_DIR, '..'))

class TestRebuildBatchLog(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory structure for testing."""
        self.test_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = self.test_dir_obj.name
        self.output_dir = os.path.join(self.test_dir, 'output')
        os.makedirs(self.output_dir)

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir_obj.cleanup()

    def _run_script(self, *args):
        """Helper to run the script under coverage."""
        script_path = os.path.join(REAL_SRC_DIR, 'rebuild_batch_log.py')
        command = [
            sys.executable, "-m", "coverage", "run",
            "--parallel-mode",
            script_path
        ] + list(args)
        
        # Run from the project root so coverage data is saved correctly.
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

    def _create_run_dir(self, base_path, run_name, rep_num, start_time, end_time, mrr, top1_acc, duration_s, with_json=True, with_api_log=True, with_report=True):
        """A helper to create a realistic fake run directory."""
        run_dir = os.path.join(base_path, f"{run_name}_rep-{rep_num}_run_{start_time}")
        os.makedirs(run_dir, exist_ok=True)

        if with_report:
            report_name = f"replication_report_{end_time}.txt"
            report_path = os.path.join(run_dir, report_name)
            with open(report_path, 'w') as f:
                f.write("Some header text.\n")
                f.write("Parsing Status: All responses parsed successfully\n")
                if with_json:
                    f.write("<<<METRICS_JSON_START>>>\n")
                    f.write(f'{{"mean_mrr": {mrr}, "mean_top_1_acc": {top1_acc/100.0}}}\n')
                    f.write("<<<METRICS_JSON_END>>>\n")
                else:
                    f.write(f"Overall Ranking Performance (MRR) ... Mean: {mrr}\n")
                    f.write(f"Overall Ranking Performance (Top-1 Accuracy) ... Mean: {top1_acc}%\n")

        if with_api_log:
            api_log_path = os.path.join(run_dir, 'api_times.log')
            with open(api_log_path, 'w') as f:
                f.write(f"some_api\t1.23\t{duration_s}\n") # Only last line matters
        
        return run_dir

    def test_depth_0_finds_only_top_level_runs(self):
        """Tests that --depth 0 (default) does not enter subdirectories."""
        self._create_run_dir(self.output_dir, "run_A", 1, "20230101_100000", "20230101-100500", 0.8, 75.0, 300)
        nested_dir = os.path.join(self.output_dir, "level1")
        os.makedirs(nested_dir)
        self._create_run_dir(nested_dir, "run_B", 2, "20230101_110000", "20230101-110500", 0.9, 85.0, 300)

        result = self._run_script(self.output_dir, "--depth", "0")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Found 1 run directories. Processing...", result.stdout)

    def test_depth_1_finds_nested_runs(self):
        """Tests that --depth 1 finds runs in immediate subdirectories."""
        self._create_run_dir(self.output_dir, "run_A", 1, "20230101_100000", "20230101-100500", 0.8, 75.0, 300)
        nested_dir = os.path.join(self.output_dir, "level1")
        os.makedirs(nested_dir)
        self._create_run_dir(nested_dir, "run_B", 2, "20230101_110000", "20230101-110500", 0.9, 85.0, 300)

        result = self._run_script(self.output_dir, "--depth", "1")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Found 2 run directories. Processing...", result.stdout)

    def test_depth_minus_1_finds_all_runs_recursively(self):
        """Tests that --depth -1 finds runs at any level."""
        self._create_run_dir(self.output_dir, "run_A", 1, "20230101_100000", "20230101-100500", 0.8, 75.0, 300)
        level1_dir = os.path.join(self.output_dir, "level1")
        self._create_run_dir(level1_dir, "run_B", 2, "20230101_110000", "20230101-110500", 0.9, 85.0, 300)
        level2_dir = os.path.join(level1_dir, "level2")
        self._create_run_dir(level2_dir, "run_C", 3, "20230101_120000", "20230101-120500", 0.7, 65.0, 300)

        result = self._run_script(self.output_dir, "--depth", "-1")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Found 3 run directories. Processing...", result.stdout)

    def test_successful_run_with_json_and_api_log(self):
        """Tests the ideal case: all data is present and parsed correctly."""
        self._create_run_dir(self.output_dir, "run_A", 1, "20230101_100000", "20230101-100500", 0.8555, 75.1, 315)
        
        result = self._run_script(self.output_dir)
        self.assertEqual(result.returncode, 0)

        log_path = os.path.join(self.output_dir, "batch_run_log_rebuilt.csv")
        self.assertTrue(os.path.exists(log_path))

        with open(log_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = [row for row in reader if row.get('ReplicationNum', '').isdigit()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['ReplicationNum'], '1')
            self.assertEqual(row['Status'], 'COMPLETED')
            self.assertEqual(row['StartTime'], '2023-01-01 10:00:00')
            self.assertEqual(row['EndTime'], '2023-01-01 10:05:00')
            self.assertEqual(row['Duration'], '05:15') # From api_times.log
            self.assertEqual(row['MeanMRR'], '0.8555')
            self.assertEqual(row['MeanTop1Acc'], '75.10%')
            self.assertEqual(row['ErrorMessage'], 'N/A')

    def test_fallback_to_text_parsing_without_json(self):
        """Tests fallback to regex parsing when JSON block is missing."""
        self._create_run_dir(self.output_dir, "run_B", 2, "20230102_120000", "20230102-121000", 0.777, 60.0, 600, with_json=False)

        result = self._run_script(self.output_dir)
        self.assertEqual(result.returncode, 0)

        log_path = os.path.join(self.output_dir, "batch_run_log_rebuilt.csv")
        with open(log_path, 'r') as f:
            reader = csv.DictReader(f)
            row = list(reader)[0]
            self.assertEqual(row['MeanMRR'], '0.7770')
            self.assertEqual(row['MeanTop1Acc'], '60.00%')

    def test_fallback_to_calculated_duration(self):
        """Tests fallback to duration calculation when api_times.log is missing."""
        self._create_run_dir(self.output_dir, "run_C", 3, "20230103_140000", "20230103-140500", 0.8, 70.0, 999, with_api_log=False)

        result = self._run_script(self.output_dir)
        self.assertEqual(result.returncode, 0)

        log_path = os.path.join(self.output_dir, "batch_run_log_rebuilt.csv")
        with open(log_path, 'r') as f:
            reader = csv.DictReader(f)
            row = list(reader)[0]
            self.assertEqual(row['Duration'], '05:00') # Calculated from timestamps

    def test_handles_missing_report_file(self):
        """Tests graceful handling of an incomplete run (no report)."""
        self._create_run_dir(self.output_dir, "run_D", 4, "20230104_160000", "20230104-160500", 0, 0, 0, with_report=False)

        result = self._run_script(self.output_dir)
        self.assertEqual(result.returncode, 0)

        log_path = os.path.join(self.output_dir, "batch_run_log_rebuilt.csv")
        with open(log_path, 'r') as f:
            reader = csv.DictReader(f)
            row = list(reader)[0]
            self.assertEqual(row['Status'], 'UNKNOWN')
            self.assertEqual(row['ErrorMessage'], 'Report file not found.')

    def test_handles_no_run_dirs_found(self):
        """Tests behavior when no 'run_*' directories are in the target path."""
        result = self._run_script(self.output_dir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("No 'run_*' directories found", result.stdout)
        log_path = os.path.join(self.output_dir, "batch_run_log_rebuilt.csv")
        self.assertFalse(os.path.exists(log_path))

    def test_exits_if_target_dir_does_not_exist(self):
        """Tests that the script exits if the target directory is invalid."""
        invalid_path = os.path.join(self.test_dir, "non_existent_dir")
        result = self._run_script(invalid_path)
        self.assertNotEqual(result.returncode, 0)
        # Argparse prints its errors to stderr by default.
        self.assertIn("Error: Specified directory", result.stdout)

if __name__ == '__main__':
    unittest.main()
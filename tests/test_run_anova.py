# tests/test_run_anova.py

import unittest
from unittest.mock import patch
import os
import sys
import tempfile
import shutil
import pandas as pd

# Add src directory to path to allow importing the script under test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from run_anova import main as anova_main

class TestAnovaScript(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory structure for testing."""
        self.test_dir_obj = tempfile.TemporaryDirectory(prefix="test_anova_")
        self.test_dir = self.test_dir_obj.name

        # --- Create a nested directory structure for depth testing ---
        self.level1_dir = os.path.join(self.test_dir, 'level1')
        self.level2_dir = os.path.join(self.level1_dir, 'level2')
        os.makedirs(self.level2_dir)

        # --- Mock Data ---
        # Top-level file (depth 0)
        self.model_a_data = {'run_directory': ['run_A_1', 'run_A_2'], 'model': ['ModelA', 'ModelA'], 'mean_mrr': [0.8, 0.85], 'mean_top_1_acc': [0.9, 0.95]}
        pd.DataFrame(self.model_a_data).to_csv(os.path.join(self.test_dir, 'final_summary_results.csv'), index=False)

        # Level 1 file (depth 1)
        self.model_b_data = {'run_directory': ['run_B_1', 'run_B_2'], 'model': ['ModelB', 'ModelB'], 'mean_mrr': [0.7, 0.75], 'mean_top_1_acc': [0.8, 0.85]}
        pd.DataFrame(self.model_b_data).to_csv(os.path.join(self.level1_dir, 'final_summary_results.csv'), index=False)

        # Level 2 file (depth > 1)
        self.model_c_data = {'run_directory': ['run_C_1', 'run_C_2'], 'model': ['ModelC', 'ModelC'], 'mean_mrr': [0.6, 0.65], 'mean_top_1_acc': [0.7, 0.75]}
        pd.DataFrame(self.model_c_data).to_csv(os.path.join(self.level2_dir, 'final_summary_results.csv'), index=False)

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir_obj.cleanup()

    @patch('run_anova.plt.savefig')
    def test_depth_0_finds_only_top_level(self, mock_savefig):
        """Tests that --depth 0 finds the file in the target directory only."""
        cli_args = ['run_anova.py', self.test_dir, '--depth', '0']
        output_dir = os.path.join(self.test_dir, 'anova')
        master_csv_path = os.path.join(output_dir, 'MASTER_ANOVA_DATASET.csv')

        with patch.object(sys, 'argv', cli_args):
            anova_main()

        self.assertTrue(os.path.exists(master_csv_path))
        df_master = pd.read_csv(master_csv_path)
        self.assertEqual(len(df_master), 2, "Should only find the 2 rows from the top-level file.")
        self.assertEqual(df_master['model'].iloc[0], 'ModelA')

    @patch('run_anova.plt.savefig')
    def test_depth_1_finds_nested_files(self, mock_savefig):
        """Tests that --depth 1 finds files at the top level and one level down."""
        cli_args = ['run_anova.py', self.test_dir, '--depth', '1']
        output_dir = os.path.join(self.test_dir, 'anova')
        master_csv_path = os.path.join(output_dir, 'MASTER_ANOVA_DATASET.csv')

        with patch.object(sys, 'argv', cli_args):
            anova_main()

        self.assertTrue(os.path.exists(master_csv_path))
        df_master = pd.read_csv(master_csv_path)
        self.assertEqual(len(df_master), 4, "Should find the 4 rows from the top-level and level-1 files.")
        self.assertIn('ModelA', df_master['model'].values)
        self.assertIn('ModelB', df_master['model'].values)

    @patch('run_anova.plt.savefig')
    def test_depth_minus_1_finds_all_recursively_and_runs_analysis(self, mock_savefig):
        """Tests that --depth -1 finds all files and completes the analysis."""
        cli_args = ['run_anova.py', self.test_dir, '--depth', '-1', '--master_filename', 'deep_scan.csv']
        output_dir = os.path.join(self.test_dir, 'anova')
        master_csv_path = os.path.join(output_dir, 'deep_scan.csv')
        log_file_path = os.path.join(output_dir, 'deep_scan_analysis_log.txt')

        with patch.object(sys, 'argv', cli_args):
            anova_main()

        # --- Assert Aggregation ---
        self.assertTrue(os.path.exists(master_csv_path))
        df_master = pd.read_csv(master_csv_path)
        self.assertEqual(len(df_master), 6, "Should find all 6 rows from all levels.")

        # --- Assert Analysis ---
        self.assertTrue(os.path.exists(log_file_path))
        self.assertTrue(mock_savefig.called)
        self.assertGreaterEqual(mock_savefig.call_count, 2)

        with open(log_file_path, 'r') as f:
            log_content = f.read()
        self.assertIn("ANALYSIS FOR METRIC: 'mean_mrr'", log_content)
        self.assertIn("Formatted ANOVA Summary", log_content)
        self.assertIn("Performance Tiers", log_content)

    @patch('run_anova.plt.savefig')
    def test_analysis_from_pre_aggregated_file(self, mock_savefig):
        """Test the analysis logic when providing a direct file path."""
        # Arrange: Manually create the master CSV in the base test directory
        master_csv_path = os.path.join(self.test_dir, 'pre_made_data.csv')
        df_a = pd.DataFrame(self.model_a_data)
        df_b = pd.DataFrame(self.model_b_data)
        pd.concat([df_a, df_b]).to_csv(master_csv_path, index=False)
        
        cli_args = ['run_anova.py', master_csv_path]

        # Define expected output path inside the 'anova' subdirectory
        output_dir = os.path.join(self.test_dir, 'anova')
        log_file_path = os.path.join(output_dir, 'pre_made_data_analysis_log.txt')

        with patch.object(sys, 'argv', cli_args):
            anova_main()
            
        # Assert Analysis
        self.assertTrue(os.path.exists(log_file_path))
        self.assertTrue(mock_savefig.called)
        
        with open(log_file_path, 'r') as f:
            log_content = f.read()
        self.assertIn("ANALYSIS FOR METRIC: 'mean_mrr'", log_content)
        self.assertIn("Formatted ANOVA Summary", log_content)

    def test_no_files_found(self):
        """Test that the script handles the case where no summary files are found."""
        # Arrange: Use a new, empty subdirectory
        empty_dir = os.path.join(self.test_dir, 'empty')
        os.makedirs(empty_dir)
        cli_args = ['run_anova.py', empty_dir]

        with patch.object(sys, 'argv', cli_args), \
             patch('logging.error') as mock_log_error:
            anova_main()
        
        # Assert that the correct error message was logged
        mock_log_error.assert_called_with("ERROR: No 'final_summary_results.csv' files found. Cannot proceed.")

if __name__ == '__main__':
    unittest.main(verbosity=2)
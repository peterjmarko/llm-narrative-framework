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

        # Create mock summary files from two different "models"
        self.model_a_dir = os.path.join(self.test_dir, 'ModelA_results')
        self.model_b_dir = os.path.join(self.test_dir, 'ModelB_results')
        os.makedirs(self.model_a_dir)
        os.makedirs(self.model_b_dir)
        
        # --- Mock Data ---
        # Provide two data points per model to allow for ANOVA calculation.
        self.model_a_data = {
            'run_directory': ['run_A_1', 'run_A_2'], 'model': ['ModelA', 'ModelA'], 
            'mean_mrr': [0.8, 0.85], 'mean_top_1_acc': [0.75, 0.8]
        }
        self.model_b_data = {
            'run_directory': ['run_B_1', 'run_B_2'], 'model': ['ModelB', 'ModelB'],
            'mean_mrr': [0.6, 0.65], 'mean_top_1_acc': [0.55, 0.6]
        }
        
        # Create a CSV with an extra blank line and summary line to test cleanup
        model_a_csv_path = os.path.join(self.model_a_dir, 'final_summary_results.csv')
        pd.DataFrame(self.model_a_data).to_csv(model_a_csv_path, index=False)
        
        model_b_csv_path = os.path.join(self.model_b_dir, 'final_summary_results.csv')
        pd.DataFrame(self.model_b_data).to_csv(model_b_csv_path, index=False)


    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir_obj.cleanup()

    @patch('run_anova.plt.savefig') # Mock savefig to prevent plot windows
    def test_aggregation_and_analysis_from_directory(self, mock_savefig):
        """Test the full pipeline: aggregate from a directory and then analyze."""
        # Arrange: Arguments to run aggregation on the base test directory
        cli_args = ['run_anova.py', self.test_dir]

        with patch.object(sys, 'argv', cli_args):
            anova_main()

        # --- Assert Aggregation ---
        master_csv_path = os.path.join(self.test_dir, 'MASTER_ANOVA_DATASET.csv')
        self.assertTrue(os.path.exists(master_csv_path))
        
        # Check that the aggregated file has the correct content (4 data rows)
        df_master = pd.read_csv(master_csv_path)
        self.assertEqual(len(df_master), 4)
        self.assertFalse(df_master['model'].isnull().any(), "Junk rows were not filtered out")
        
        # --- Assert Analysis ---
        log_file_path = os.path.join(self.test_dir, 'MASTER_ANOVA_DATASET_analysis_log.txt')
        self.assertTrue(os.path.exists(log_file_path))
        
        # Check that plots were generated (by checking if savefig was called)
        self.assertTrue(mock_savefig.called)
        # Check for at least one MRR and one Top-1 plot
        self.assertGreaterEqual(mock_savefig.call_count, 2)
        
        # Check that the log file contains key analysis sections
        with open(log_file_path, 'r') as f:
            log_content = f.read()
        self.assertIn("ANALYSIS FOR METRIC: 'mean_mrr'", log_content)
        self.assertIn("Descriptive Statistics by Model", log_content)
        self.assertIn("Formatted ANOVA Summary", log_content)
        self.assertIn("Performance Tiers", log_content)

    @patch('run_anova.plt.savefig')
    def test_analysis_from_pre_aggregated_file(self, mock_savefig):
        """Test the analysis logic when providing a direct file path."""
        # Arrange: Manually create the master CSV
        master_csv_path = os.path.join(self.test_dir, 'pre_made_data.csv')
        df_a = pd.DataFrame(self.model_a_data)
        df_b = pd.DataFrame(self.model_b_data)
        pd.concat([df_a, df_b]).to_csv(master_csv_path, index=False)
        
        cli_args = ['run_anova.py', master_csv_path]

        with patch.object(sys, 'argv', cli_args):
            anova_main()
            
        # Assert Analysis
        log_file_path = os.path.join(self.test_dir, 'pre_made_data_analysis_log.txt')
        self.assertTrue(os.path.exists(log_file_path))
        
        # Check that plots were generated
        self.assertTrue(mock_savefig.called)
        
        # Check that the log file contains key analysis sections
        with open(log_file_path, 'r') as f:
            log_content = f.read()
        self.assertIn("ANALYSIS FOR METRIC: 'mean_mrr'", log_content)
        self.assertIn("Formatted ANOVA Summary", log_content)
        self.assertIn("Performance Tiers", log_content)

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
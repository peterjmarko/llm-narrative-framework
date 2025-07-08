# Filename: tests/test_run_anova.py

import unittest
from unittest.mock import patch
import os
import sys
import shutil
import tempfile
import pandas as pd
import importlib
import logging

# We can safely import the main function here. Our patching strategy will target
# the APP_CONFIG object *inside* the already-imported run_anova module.
from src.run_anova import main as anova_main

class TestAnovaScript(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory and mock DataFrame."""
        self.test_dir = tempfile.mkdtemp(prefix="test_anova_")
        
        # This DataFrame includes columns for all factors listed in the mock config below.
        data = {
            'model': ['gpt-4'] * 5 + ['claude-3'] * 5,
            'temperature': [0.5] * 10,
            'db': ['db1'] * 10,
            'k': [10] * 10,
            'm': [10] * 10,
            'mapping_strategy': ['strategy_A'] * 10,
            'persona_name': ['persona_1'] * 10,
            'mwu_stouffer_p': [0.01, 0.02, 0.015, 0.011, 0.018] + [0.8, 0.9, 0.85, 0.88, 0.91],
            'mean_top_1_acc': [0.95, 0.92, 0.94, 0.96, 0.91] + [0.55, 0.52, 0.54, 0.56, 0.51],
            'zero_variance_metric': [1.0] * 10
        }
        self.df = pd.DataFrame(data)
        
        # This dictionary represents our mock configuration data.
        self.test_config_data = {
            'Schema': {
                'factors': "model, temperature, db, k, m",
                'metrics': "mwu_stouffer_p, mean_top_1_acc, zero_variance_metric"
            },
            'Analysis': { 'min_valid_response_threshold': "0" },
            'ModelDisplayNames': {'gpt-4': 'GPT-4', 'claude-3': 'Claude 3 Opus'},
            'FactorDisplayNames': {'model': 'Model', 'k': 'Group Size (k)', 'm': 'Trials (m)'},
            'MetricDisplayNames': {
                'mwu_stouffer_p': 'MWU Stouffer p',
                'mean_top_1_acc': 'Top-1 Accuracy',
                'zero_variance_metric': 'Zero Var Metric'
            },
            'ModelNormalization': {'gpt-4': 'gpt-4', 'claude-3': 'claude-3'}
        }

    def configure_mock_config(self, mock_app_config):
        """Helper to apply our test data to a MagicMock object."""
        mock_app_config.get.side_effect = lambda s, k, **kwargs: self.test_config_data.get(s, {}).get(k)
        mock_app_config.items.side_effect = lambda s: self.test_config_data.get(s, {}).items()
        mock_app_config.getint.side_effect = lambda s, k, **kwargs: int(self.test_config_data.get(s, {}).get(k, kwargs.get('fallback', 0)))

    def tearDown(self):
        """Clean up the temporary directory and logging handlers."""
        # First, find all active logging handlers and close them to release file locks.
        logger = logging.getLogger()
        handlers = logger.handlers[:]
        for handler in handlers:
            handler.close()
            logger.removeHandler(handler)
        
        # Now that all files are closed, we can safely delete the directory.
        shutil.rmtree(self.test_dir)

        # Finally, reload the logging module to ensure a clean state for the next test.
        importlib.reload(logging)

    # Patch APP_CONFIG directly where it is used in the run_anova module.
    @patch('src.run_anova.APP_CONFIG')
    @patch('src.run_anova.plt.savefig')
    @patch('sys.exit')
    def test_happy_path_with_directory_input(self, mock_exit, mock_savefig, mock_app_config):
        """Test main execution with mock data and mock config."""
        self.configure_mock_config(mock_app_config)
        
        master_csv_path = os.path.join(self.test_dir, 'STUDY_results.csv')
        self.df.to_csv(master_csv_path, index=False)
        cli_args = ['run_anova.py', self.test_dir]
        
        with patch.object(sys, 'argv', cli_args):
            anova_main()

        mock_exit.assert_not_called()
        # 2 valid metrics ('mwu_stouffer_p', 'mean_top_1_acc') are processed.
        # For each, 1 factor ('model') is active.
        # This generates 1 diagnostic plot + 1 boxplot per metric.
        # Total plots = 2 metrics * 2 plots/metric = 4.
        self.assertEqual(mock_savefig.call_count, 4)

    @patch('src.run_anova.APP_CONFIG')
    @patch('sys.exit')
    @patch('logging.error')
    def test_no_summary_file_found(self, mock_log_error, mock_exit, mock_app_config):
        """Test script exits gracefully when no summary CSV is found."""
        self.configure_mock_config(mock_app_config)
        cli_args = ['run_anova.py', self.test_dir]
        with patch.object(sys, 'argv', cli_args):
            anova_main()
            
        mock_log_error.assert_any_call(f"ERROR: No summary CSV file found in {self.test_dir}.")
        mock_exit.assert_called_with(1)

    @patch('src.run_anova.APP_CONFIG')
    @patch('logging.warning')
    @patch('sys.exit')
    def test_zero_variance_metric_is_skipped(self, mock_exit, mock_log_warning, mock_app_config):
        """Test that metrics with no variance are skipped."""
        self.configure_mock_config(mock_app_config)
        
        master_csv_path = os.path.join(self.test_dir, 'STUDY_results.csv')
        self.df.to_csv(master_csv_path, index=False)
        cli_args = ['run_anova.py', self.test_dir]

        with patch.object(sys, 'argv', cli_args):
            anova_main()
            
        mock_exit.assert_not_called()
        mock_log_warning.assert_any_call("WARNING: Metric 'Zero Var Metric' has zero variance. Skipping all analysis.")

    @patch('src.run_anova.APP_CONFIG')
    @patch('logging.info')
    @patch('src.run_anova.plt.savefig')
    @patch('sys.exit')
    def test_performance_tier_generation(self, mock_exit, mock_savefig, mock_log_info, mock_app_config):
        """Test that performance tiers are generated for significant model effects."""
        self.configure_mock_config(mock_app_config)
        
        # Create data where 'model' has a clear, significant effect on 'mwu_stouffer_p'
        tier1_model = 'gpt-4'
        tier2_model = 'claude-3'
        tier3_model = 'gemini-pro'
        
        data = {
            'model': [tier1_model] * 5 + [tier2_model] * 5 + [tier3_model] * 5,
            'temperature': [0.5] * 15,
            'db': ['db1'] * 15,
            'k': [10] * 15,
            'm': [10] * 15,
            'mapping_strategy': ['strategy_A'] * 15,
            'persona_name': ['persona_1'] * 15,
             'n_valid_responses': [25] * 15,
            'mwu_stouffer_p': [0.95, 0.92, 0.94, 0.96, 0.91] +   # High tier
                              [0.55, 0.52, 0.54, 0.56, 0.51] +   # Mid tier
                              [0.15, 0.12, 0.14, 0.16, 0.11],     # Low tier
            'mean_top_1_acc': [0.5] * 15,
            'zero_variance_metric': [1.0] * 15
        }
        # Add a third model to display names
        self.test_config_data['ModelDisplayNames'][tier3_model] = 'Gemini Pro'
        
        df = pd.DataFrame(data)
        master_csv_path = os.path.join(self.test_dir, 'STUDY_results.csv')
        df.to_csv(master_csv_path, index=False)
        cli_args = ['run_anova.py', self.test_dir]
        
        with patch.object(sys, 'argv', cli_args):
            anova_main()
            
        mock_exit.assert_not_called()

        # Check that the performance group table was logged
        log_calls = [call.args[0] for call in mock_log_info.call_args_list]
        self.assertTrue(any("Performance Group" in str(log) and "Median Score" in str(log) for log in log_calls))

    @patch('src.run_anova.APP_CONFIG')
    @patch('logging.info')
    @patch('sys.exit')
    def test_model_filtering_by_response_rate(self, mock_exit, mock_log_info, mock_app_config):
        """Test that models below the valid response threshold are excluded."""
        # Set a threshold in the mock config
        self.test_config_data['Analysis']['min_valid_response_threshold'] = "10"
        self.configure_mock_config(mock_app_config)

        # Create data where one model is below the threshold
        data = {
            'model': ['gpt-4'] * 5 + ['claude-3'] * 5,
            'temperature': [0.5] * 10,
            'db': ['db1'] * 10,
            'k': [10] * 10,
            'm': [10] * 10,
            'mapping_strategy': ['strategy_A'] * 10,
            'persona_name': ['persona_1'] * 10,
            'n_valid_responses': [25] * 5 + [1] * 5, # gpt-4 is OK, claude-3 is not
            'mwu_stouffer_p': [0.5] * 10,
            'mean_top_1_acc': [0.5] * 10,
            'zero_variance_metric': [1.0] * 10
        }
        
        df = pd.DataFrame(data)
        master_csv_path = os.path.join(self.test_dir, 'STUDY_results.csv')
        df.to_csv(master_csv_path, index=False)
        cli_args = ['run_anova.py', self.test_dir]
        
        with patch.object(sys, 'argv', cli_args):
            anova_main()
            
        mock_exit.assert_not_called()

        # Verify that the log message confirms the model was excluded
        log_calls = [call.args[0] for call in mock_log_info.call_args_list]
        self.assertTrue(any("Excluding 1 model(s)" in str(log) and "claude-3" in str(log) for log in log_calls))

    @patch('src.run_anova.APP_CONFIG')
    @patch('sys.exit')
    @patch('src.run_anova.plt.savefig') # Patch savefig to avoid creating new plots
    def test_archiving_of_previous_results(self, mock_savefig, mock_exit, mock_app_config):
        """Test that existing files in the output dir are moved to an archive."""
        self.configure_mock_config(mock_app_config)

        # 1. Set up the environment with a results CSV and pre-existing output files
        master_csv_path = os.path.join(self.test_dir, 'STUDY_results.csv')
        self.df.to_csv(master_csv_path, index=False)
        
        output_dir = os.path.join(self.test_dir, 'anova')
        os.makedirs(output_dir, exist_ok=True)
        
        old_file_to_archive = os.path.join(output_dir, 'old_result.txt')
        with open(old_file_to_archive, 'w') as f:
            f.write('old data')
            
        old_dir_to_archive = os.path.join(output_dir, 'old_plots')
        os.makedirs(old_dir_to_archive)

        # 2. Run the main script
        cli_args = ['run_anova.py', self.test_dir]
        with patch.object(sys, 'argv', cli_args):
            anova_main()
            
        mock_exit.assert_not_called()

        # 3. Assert that the old results were moved to the archive subdirectory
        archived_file_path = os.path.join(output_dir, 'archive', 'old_result.txt')
        archived_dir_path = os.path.join(output_dir, 'archive', 'old_plots')
        
        self.assertFalse(os.path.exists(old_file_to_archive), "Old file should have been moved.")
        self.assertFalse(os.path.exists(old_dir_to_archive), "Old directory should have been moved.")
        self.assertTrue(os.path.exists(archived_file_path), "File should exist in archive.")
        self.assertTrue(os.path.isdir(archived_dir_path), "Directory should exist in archive.")


if __name__ == '__main__':
    unittest.main()


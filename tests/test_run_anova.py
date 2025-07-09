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
import configparser

from src.run_anova import main as anova_main

class TestAnovaScript(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory and mock DataFrame."""
        self.test_dir = tempfile.mkdtemp(prefix="test_anova_")
        
        self.df = pd.DataFrame({
            'model': ['gpt-4'] * 5 + ['claude-3'] * 5,
            'n_valid_responses': [25] * 10,
            'mwu_stouffer_p': [0.01, 0.02, 0.015, 0.011, 0.018] + [0.8, 0.9, 0.85, 0.88, 0.91],
            'mean_top_1_acc': [0.95, 0.92, 0.94, 0.96, 0.91] + [0.55, 0.52, 0.54, 0.56, 0.51],
            'zero_variance_metric': [1.0] * 10
        })
        
        self.test_config_data = {
            'Schema': {'factors': "model", 'metrics': "mwu_stouffer_p, mean_top_1_acc, zero_variance_metric"},
            'Analysis': { 'min_valid_response_threshold': "0" },
            'ModelDisplayNames': {'gpt-4': 'GPT-4', 'claude-3': 'Claude 3 Opus'},
            'FactorDisplayNames': {'model': 'Model'},
            'MetricDisplayNames': {
                'mwu_stouffer_p': 'MWU Stouffer p',
                'mean_top_1_acc': 'Top-1 Accuracy',
                'zero_variance_metric': 'Zero Var Metric'
            },
            'ModelNormalization': {'gpt-4': 'gpt-4', 'claude-3': 'claude-3'}
        }
        self.config_instance = configparser.ConfigParser()
        self.config_instance.read_dict(self.test_config_data)

    def tearDown(self):
        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
        shutil.rmtree(self.test_dir)
        importlib.reload(logging)

    def mock_get_config_list(self, cfg, section, key):
        """Mock implementation for get_config_list helper."""
        value = self.config_instance.get(section, key, fallback='')
        return [item.strip() for item in value.split(',') if item.strip()]

    def mock_get_config_section_as_dict(self, cfg, section):
        """Mock implementation for get_config_section_as_dict helper."""
        return dict(self.config_instance.items(section))

    @patch('src.run_anova.get_config_section_as_dict')
    @patch('src.run_anova.get_config_list')
    @patch('src.run_anova.APP_CONFIG')
    @patch('src.run_anova.plt.savefig')
    @patch('sys.exit')
    def test_happy_path_with_directory_input(self, mock_exit, mock_savefig, mock_app_config, mock_get_list, mock_get_dict):
        # Configure all mocks
        mock_get_list.side_effect = self.mock_get_config_list
        mock_get_dict.side_effect = self.mock_get_config_section_as_dict
        mock_app_config.getint.return_value = 0 # For min_valid_responses

        # Run test
        master_csv_path = os.path.join(self.test_dir, 'STUDY_results.csv')
        self.df.to_csv(master_csv_path, index=False)
        cli_args = ['run_anova.py', self.test_dir]
        
        with patch.object(sys, 'argv', cli_args):
            anova_main()

        # Assert
        mock_exit.assert_not_called()
        self.assertEqual(mock_savefig.call_count, 4)

    @patch('src.run_anova.get_config_section_as_dict')
    @patch('src.run_anova.get_config_list')
    @patch('src.run_anova.APP_CONFIG')
    @patch('logging.warning')
    @patch('sys.exit')
    def test_zero_variance_metric_is_skipped(self, mock_exit, mock_log_warning, mock_app_config, mock_get_list, mock_get_dict):
        # Configure all mocks
        mock_get_list.side_effect = self.mock_get_config_list
        mock_get_dict.side_effect = self.mock_get_config_section_as_dict
        mock_app_config.getint.return_value = 0 # For min_valid_responses

        # Run test
        master_csv_path = os.path.join(self.test_dir, 'STUDY_results.csv')
        self.df.to_csv(master_csv_path, index=False)
        cli_args = ['run_anova.py', self.test_dir]

        with patch.object(sys, 'argv', cli_args):
            anova_main()
            
        # Assert
        mock_exit.assert_not_called()
        mock_log_warning.assert_any_call("WARNING: Metric 'Zero Var Metric' has zero variance. Skipping all analysis.")

    @patch('src.run_anova.get_config_section_as_dict')
    @patch('src.run_anova.get_config_list')
    @patch('src.run_anova.APP_CONFIG')
    @patch('logging.info')
    @patch('src.run_anova.plt.savefig')
    @patch('sys.exit')
    def test_performance_tier_generation(self, mock_exit, mock_savefig, mock_log_info, mock_app_config, mock_get_list, mock_get_dict):
        # Configure all mocks
        mock_get_list.side_effect = self.mock_get_config_list
        mock_get_dict.side_effect = self.mock_get_config_section_as_dict
        mock_app_config.getint.return_value = 0 # For min_valid_responses

        # FIX: Create data with 3 model levels to trigger post-hoc analysis
        data = {
            'model': ['gpt-4'] * 5 + ['claude-3'] * 5 + ['gemini-pro'] * 5,
            'n_valid_responses': [25] * 15,
            'mwu_stouffer_p': [0.01] * 5 + [0.5] * 5 + [0.9] * 5, # 3 distinct tiers
            'mean_top_1_acc': [0.9] * 5 + [0.5] * 5 + [0.1] * 5,
            'zero_variance_metric': [1.0] * 15
        }
        self.test_config_data['ModelDisplayNames']['gemini-pro'] = 'Gemini Pro'
        df = pd.DataFrame(data)
        
        # Run test using the new specific dataframe
        master_csv_path = os.path.join(self.test_dir, 'STUDY_results.csv')
        df.to_csv(master_csv_path, index=False) # Use the local df
        cli_args = ['run_anova.py', self.test_dir]
        
        with patch.object(sys, 'argv', cli_args):
            anova_main()
            
        # Assert
        mock_exit.assert_not_called()
        log_calls = [call.args[0] for call in mock_log_info.call_args_list]
        self.assertTrue(any("Performance Group" in str(log) and "Median Score" in str(log) for log in log_calls))

if __name__ == '__main__':
    unittest.main()
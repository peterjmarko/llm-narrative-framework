# Filename: tests/test_compile_results.py

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import shutil
import tempfile
import pandas as pd
import configparser
import json

# Import the functions from the module we are testing
from src.compile_results import main as compile_main, parse_config_params

class TestCompileResultsScript(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory and mock config for each test."""
        self.test_dir = tempfile.mkdtemp(prefix="test_compile_")
        
        self.mock_config_data = {
            'Schema': {
                'csv_header_order': "run_directory,model,temperature,db,k,m,mapping_strategy,replication,mwu_stouffer_p,mean_top_1_acc,bias_slope,bias_p_value"
            }
        }
    
    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    def _create_mock_run(self, path, run_name, config_data, metrics_data):
        """A helper to create a complete mock run directory."""
        run_dir = os.path.join(path, f"run_{run_name}")
        os.makedirs(run_dir, exist_ok=True)
        
        # Create config.ini.archived
        config = configparser.ConfigParser()
        config['LLM'] = config_data.get('LLM', {})
        config['Study'] = config_data.get('Study', {})
        config['General'] = config_data.get('General', {})
        with open(os.path.join(run_dir, 'config.ini.archived'), 'w') as f:
            config.write(f)

        # Create replication_report_....txt
        report_path = os.path.join(run_dir, f"replication_report_{run_name}.txt")
        with open(report_path, "w") as f:
            f.write("Some text before.\n")
            f.write("<<<METRICS_JSON_START>>>\n")
            f.write(json.dumps(metrics_data) + "\n")
            f.write("<<<METRICS_JSON_END>>>\n")
            f.write("Some text after.\n")
        return run_dir

    @patch('src.compile_results.APP_CONFIG')
    def test_main_happy_path_hierarchical(self, mock_app_config):
        """Test hierarchical aggregation with bias metrics flattening."""
        mock_app_config.get.side_effect = lambda s, k: self.mock_config_data.get(s, {}).get(k)
        
        study_dir = os.path.join(self.test_dir, "MyStudy")
        exp1_dir = os.path.join(study_dir, "experiment_A")

        self._create_mock_run(
            exp1_dir, "gpt4_rep-1",
            config_data={'LLM': {'model_name': 'gpt-4', 'temperature': 0.7}},
            metrics_data={
                'mwu_stouffer_p': 0.95, 
                'positional_bias_metrics': {'slope': 0.05, 'p_value': 0.01}
            }
        )
        self._create_mock_run(
            exp1_dir, "claude3_rep-1",
            config_data={'LLM': {'model_name': 'claude-3', 'temperature': 0.5}},
            metrics_data={'mwu_stouffer_p': 0.88}
        )
        
        cli_args = ['compile_results.py', study_dir]
        with patch.object(sys, 'argv', cli_args):
            return_code = compile_main()

        self.assertIsNone(return_code, "The main function should return None on success.")
        
        study_output_path = os.path.join(study_dir, "STUDY_results.csv")
        self.assertTrue(os.path.exists(study_output_path))
        
        df = pd.read_csv(study_output_path)
        self.assertEqual(len(df), 2)
        
        gpt4_row = df[df['model'] == 'gpt-4'].iloc[0]
        self.assertEqual(gpt4_row['bias_slope'], 0.05)
        
        claude3_row = df[df['model'] == 'claude-3'].iloc[0]
        self.assertTrue(pd.isna(claude3_row['bias_slope']))

    @patch('src.compile_results.APP_CONFIG')
    @patch('logging.error')
    def test_invalid_base_directory(self, mock_log_error, mock_app_config):
        """Test script handles a non-existent directory correctly."""
        mock_app_config.get.side_effect = lambda s, k: self.mock_config_data.get(s, {}).get(k)
        invalid_path = os.path.join(self.test_dir, "non_existent")
        
        cli_args = ['compile_results.py', invalid_path]
        with patch.object(sys, 'argv', cli_args):
            return_code = compile_main()
            
        self.assertIsNone(return_code, "On failure, main() should return None.")
        mock_log_error.assert_called_with(f"Error: The specified directory does not exist: {invalid_path}")
    
    @patch('src.compile_results.APP_CONFIG')
    @patch('logging.warning')
    def test_skips_run_with_missing_config(self, mock_log_warning, mock_app_config):
        """Test that a run is skipped if config.ini.archived is missing."""
        mock_app_config.get.side_effect = lambda s, k: self.mock_config_data.get(s, {}).get(k)
        
        self._create_mock_run(self.test_dir, "valid_rep-1", {'LLM': {'model_name': 'a'}}, {'mrr': 0.5})
        
        invalid_run_dir = os.path.join(self.test_dir, "run_invalid_rep-1")
        os.makedirs(invalid_run_dir)
        with open(os.path.join(invalid_run_dir, 'replication_report_x.txt'), 'w') as f:
             f.write("<<<METRICS_JSON_START>>>\n{\"mrr\":0.1}\n<<<METRICS_JSON_END>>>")

        cli_args = ['compile_results.py', self.test_dir]
        with patch.object(sys, 'argv', cli_args):
            compile_main()
            
        final_summary_path = os.path.join(self.test_dir, "EXPERIMENT_results.csv")
        self.assertTrue(os.path.exists(final_summary_path), "A summary file should still be created for the valid run.")
        
        df = pd.read_csv(final_summary_path)
        self.assertEqual(len(df), 1, "Only the valid run should be in the final summary.")
        mock_log_warning.assert_any_call(f"    - Warning: 'config.ini.archived' not found in run_invalid_rep-1. Skipping.")

    def test_parse_config_robustness(self):
        """ Test the parse_config_params function with various legacy and current keys. """
        config = configparser.ConfigParser()
        config['LLM'] = {'model': 'model_A', 'temperature': '0.8'}
        config['Study'] = {'num_subjects': '10', 'num_trials': '20'}
        config['General'] = {'personalities_db_path': '/path/to/my_db.db'}
        config_path = os.path.join(self.test_dir, 'test_config.ini')
        with open(config_path, 'w') as f:
            config.write(f)
        
        params = parse_config_params(config_path)
        
        self.assertEqual(params['model'], 'model_A')
        self.assertEqual(params['temperature'], 0.8)
        self.assertEqual(params['k'], 10)
        self.assertEqual(params['m'], 20)
        self.assertEqual(params['db'], 'my_db.db')

if __name__ == '__main__':
    unittest.main()

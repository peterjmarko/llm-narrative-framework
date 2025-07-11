#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: tests/test_compilers.py

import unittest
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import pandas as pd
import configparser
import json

# Standard: Import modules under test at the top level.
# Pytest ensures 'src' is on the path, so this works correctly.
from src import results_compiler, compile_replication, compile_experiment, compile_study

class TestNewCompilationArchitecture(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory for each test."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up the temporary directory after each test."""
        shutil.rmtree(self.test_dir)

    def _create_mock_run_data(self, path, run_name, replication_num, model_name="test_model", k=10, m=100):
        """Helper to create a mock run directory with report and config."""
        # The run_name now includes the replication number, e.g., "rep-001_model-A"
        run_dir = os.path.join(path, f"run_{run_name}")
        os.makedirs(run_dir, exist_ok=True)
        
        # Create config.ini.archived
        config = configparser.ConfigParser()
        config['LLM'] = {'model_name': model_name}
        config['Study'] = {'group_size': str(k), 'num_trials': str(m)}
        with open(os.path.join(run_dir, 'config.ini.archived'), 'w') as f:
            config.write(f)

        # Create replication_report.txt with a name that matches what glob expects
        metrics_data = {
            "mean_mrr": 0.1 * replication_num,
            "mean_top_1_acc": 0.1 * replication_num,
            "positional_bias_metrics": {"slope": 0.01 * replication_num}
        }
        # The report filename can be simple, as long as it matches the glob pattern
        report_filename = f"replication_report_{run_name}.txt"
        with open(os.path.join(run_dir, report_filename), 'w') as f:
            f.write(f"<<<METRICS_JSON_START>>>\n{json.dumps(metrics_data)}\n<<<METRICS_JSON_END>>>")

    @patch('src.results_compiler.get_config_list')
    def test_compile_replication(self, mock_get_config_list):
        """Test the main logic of compile_replication.py."""
        mock_get_config_list.return_value = ['replication', 'model', 'k', 'm', 'mean_mrr', 'bias_slope']
        
        # The run directory path is now built inside the helper. We just pass the base path.
        run_name = "rep-001_model-A"
        run_dir_path = os.path.join(self.test_dir, f"run_{run_name}")
        self._create_mock_run_data(self.test_dir, run_name=run_name, replication_num=1, model_name="model_A", k=5, m=50)
        
        with patch.object(sys, 'argv', ['compile_replication.py', run_dir_path]):
            compile_replication.main()

        output_csv = os.path.join(run_dir_path, "REPLICATION_results.csv")
        self.assertTrue(os.path.exists(output_csv))
        df = pd.read_csv(output_csv)
        self.assertEqual(df.loc[0, 'replication'], 1)
        self.assertEqual(df.loc[0, 'model'], 'model_A')
        self.assertEqual(df.loc[0, 'k'], 5)
        self.assertEqual(df.loc[0, 'm'], 50)
        self.assertEqual(df.loc[0, 'mean_mrr'], 0.1)
        self.assertEqual(df.loc[0, 'bias_slope'], 0.01)

    def test_compile_experiment(self):
        """Test the main logic of compile_experiment.py."""
        exp_path = os.path.join(self.test_dir, "exp_A")
        
        run1_path = os.path.join(exp_path, "run_rep-001")
        os.makedirs(run1_path)
        pd.DataFrame([{'replication': 1, 'mean_mrr': 0.1}]).to_csv(os.path.join(run1_path, "REPLICATION_results.csv"), index=False)
        
        run2_path = os.path.join(exp_path, "run_rep-002")
        os.makedirs(run2_path)
        pd.DataFrame([{'replication': 2, 'mean_mrr': 0.2}]).to_csv(os.path.join(run2_path, "REPLICATION_results.csv"), index=False)

        with patch.object(sys, 'argv', ['compile_experiment.py', exp_path]):
            compile_experiment.main()
            
        output_csv = os.path.join(exp_path, "EXPERIMENT_results.csv")
        self.assertTrue(os.path.exists(output_csv))
        df = pd.read_csv(output_csv)
        self.assertEqual(len(df), 2)
        self.assertSetEqual(set(df['replication']), {1, 2})

    def test_compile_study(self):
        """Test the main logic of compile_study.py."""
        study_path = os.path.join(self.test_dir, "my_study")

        exp1_path = os.path.join(study_path, "exp_A")
        os.makedirs(exp1_path)
        pd.DataFrame([{'model': 'model_A', 'mean_mrr': 0.3}]).to_csv(os.path.join(exp1_path, "EXPERIMENT_results.csv"), index=False)
        
        exp2_path = os.path.join(study_path, "exp_B")
        os.makedirs(exp2_path)
        pd.DataFrame([{'model': 'model_B', 'mean_mrr': 0.4}]).to_csv(os.path.join(exp2_path, "EXPERIMENT_results.csv"), index=False)

        with patch.object(sys, 'argv', ['compile_study.py', study_path]):
            compile_study.main()
            
        output_csv = os.path.join(study_path, "STUDY_results.csv")
        self.assertTrue(os.path.exists(output_csv))
        df = pd.read_csv(output_csv)
        self.assertEqual(len(df), 2)
        self.assertSetEqual(set(df['model']), {'model_A', 'model_B'})

    def test_compile_study_invalid_directory(self):
        """Test compile_study with invalid directory."""
        invalid_path = os.path.join(self.test_dir, "nonexistent")
        
        with patch.object(sys, 'argv', ['compile_study.py', invalid_path]):
            with self.assertRaises(SystemExit) as cm:
                compile_study.main()
            self.assertEqual(cm.exception.code, 1)

    def test_compile_study_no_experiment_csvs(self):
        """Test compile_study when no experiment CSVs are found."""
        empty_study = os.path.join(self.test_dir, "empty_study")
        os.makedirs(empty_study)
        
        with patch.object(sys, 'argv', ['compile_study.py', empty_study]):
            with patch('src.compile_study.logging.warning') as mock_warn:
                compile_study.main()  # Should return without error
                mock_warn.assert_called()

    def test_compile_study_empty_csvs(self):
        """Test compile_study with empty experiment CSVs."""
        study_path = os.path.join(self.test_dir, "study_with_empty")
        exp_path = os.path.join(study_path, "exp_empty")
        os.makedirs(exp_path)
        
        # Create empty CSV
        pd.DataFrame().to_csv(os.path.join(exp_path, "EXPERIMENT_results.csv"), index=False)
        
        with patch.object(sys, 'argv', ['compile_study.py', study_path]):
            with self.assertRaises(SystemExit) as cm:
                compile_study.main()
            self.assertEqual(cm.exception.code, 1)

    def test_compile_study_corrupted_csv(self):
        """Test compile_study with CSV files that cause pandas errors."""
        study_path = os.path.join(self.test_dir, "study_corrupted")
        exp_path = os.path.join(study_path, "exp_bad")
        os.makedirs(exp_path)
        
        # Create a file that will actually cause pandas to fail
        with open(os.path.join(exp_path, "EXPERIMENT_results.csv"), 'w') as f:
            f.write("")  # Completely empty file will cause EmptyDataError
        
        with patch.object(sys, 'argv', ['compile_study.py', study_path]):
            with patch('src.compile_study.logging.warning') as mock_warning:
                with patch('src.compile_study.logging.error') as mock_error:
                    with self.assertRaises(SystemExit) as cm:
                        compile_study.main()
                    
                    # Should exit with code 1
                    self.assertEqual(cm.exception.code, 1)
                    # Should log a warning about empty CSV
                    mock_warning.assert_called()
                    # Should log error about all CSVs being empty
                    mock_error.assert_called()

    def test_compile_experiment_invalid_directory(self):
        """Test compile_experiment with invalid directory."""
        invalid_path = os.path.join(self.test_dir, "nonexistent")
        
        with patch.object(sys, 'argv', ['compile_experiment.py', invalid_path]):
            with self.assertRaises(SystemExit) as cm:
                compile_experiment.main()
            self.assertEqual(cm.exception.code, 1)

    def test_compile_experiment_no_replication_csvs(self):
        """Test compile_experiment when no replication CSVs are found."""
        empty_exp = os.path.join(self.test_dir, "empty_exp")
        os.makedirs(empty_exp)
        
        with patch.object(sys, 'argv', ['compile_experiment.py', empty_exp]):
            with patch('src.compile_experiment.logging.warning') as mock_warn:
                compile_experiment.main()  # Should return without error
                mock_warn.assert_called()

    def test_compile_experiment_empty_csvs(self):
        """Test compile_experiment with empty replication CSVs."""
        exp_path = os.path.join(self.test_dir, "exp_with_empty")
        run_path = os.path.join(exp_path, "run_001")
        os.makedirs(run_path)
        
        # Create empty CSV
        pd.DataFrame().to_csv(os.path.join(run_path, "REPLICATION_results.csv"), index=False)
        
        with patch.object(sys, 'argv', ['compile_experiment.py', exp_path]):
            with self.assertRaises(SystemExit) as cm:
                compile_experiment.main()
            self.assertEqual(cm.exception.code, 1)

    def test_compile_replication_invalid_directory(self):
        """Test compile_replication with invalid directory."""
        invalid_path = os.path.join(self.test_dir, "not_a_run_dir")
        
        with patch.object(sys, 'argv', ['compile_replication.py', invalid_path]):
            with self.assertRaises(SystemExit) as cm:
                compile_replication.main()
            self.assertEqual(cm.exception.code, 1)

    def test_compile_replication_missing_report(self):
        """Test compile_replication with missing report file."""
        run_dir = os.path.join(self.test_dir, "run_missing_report")
        os.makedirs(run_dir)
        
        # Create config but no report
        config = configparser.ConfigParser()
        config['LLM'] = {'model_name': 'test_model'}
        with open(os.path.join(run_dir, 'config.ini.archived'), 'w') as f:
            config.write(f)
        
        with patch.object(sys, 'argv', ['compile_replication.py', run_dir]):
            with self.assertRaises(SystemExit) as cm:
                compile_replication.main()
            self.assertEqual(cm.exception.code, 1)

    def test_compile_replication_missing_config(self):
        """Test compile_replication with missing config file."""
        run_dir = os.path.join(self.test_dir, "run_missing_config")
        os.makedirs(run_dir)
        
        # Create report but no config
        with open(os.path.join(run_dir, 'replication_report_test.txt'), 'w') as f:
            f.write("<<<METRICS_JSON_START>>>\n{\"mean_mrr\": 0.5}\n<<<METRICS_JSON_END>>>")
        
        with patch.object(sys, 'argv', ['compile_replication.py', run_dir]):
            with self.assertRaises(SystemExit) as cm:
                compile_replication.main()
            self.assertEqual(cm.exception.code, 1)

    def test_compile_replication_invalid_json(self):
        """Test compile_replication with invalid JSON in report."""
        run_dir = os.path.join(self.test_dir, "run_bad_json")
        os.makedirs(run_dir)
        
        # Create config
        config = configparser.ConfigParser()
        config['LLM'] = {'model_name': 'test_model'}
        with open(os.path.join(run_dir, 'config.ini.archived'), 'w') as f:
            config.write(f)
        
        # Create report with invalid JSON
        with open(os.path.join(run_dir, 'replication_report_test.txt'), 'w') as f:
            f.write("<<<METRICS_JSON_START>>>\n{invalid json}\n<<<METRICS_JSON_END>>>")
        
        with patch.object(sys, 'argv', ['compile_replication.py', run_dir]):
            with self.assertRaises(SystemExit) as cm:
                compile_replication.main()
            self.assertEqual(cm.exception.code, 1)

    def test_results_compiler_parse_metrics_json_invalid(self):
        """Test parse_metrics_json with various invalid inputs."""
        # Test with no JSON tags
        result = results_compiler.parse_metrics_json("No JSON here")
        self.assertIsNone(result)
        
        # Test with malformed JSON
        content_bad_json = "<<<METRICS_JSON_START>>>\n{invalid}\n<<<METRICS_JSON_END>>>"
        with patch('src.results_compiler.logging.warning') as mock_warn:
            result = results_compiler.parse_metrics_json(content_bad_json)
            self.assertIsNone(result)
            mock_warn.assert_called()

    def test_results_compiler_parse_metrics_json_with_bias(self):
        """Test parse_metrics_json flattens bias metrics correctly."""
        content = """
        <<<METRICS_JSON_START>>>
        {
            "mean_mrr": 0.5,
            "positional_bias_metrics": {
                "slope": -0.1,
                "r_squared": 0.85
            }
        }
        <<<METRICS_JSON_END>>>
        """
        
        result = results_compiler.parse_metrics_json(content)
        self.assertIsNotNone(result)
        self.assertEqual(result['mean_mrr'], 0.5)
        self.assertEqual(result['bias_slope'], -0.1)
        self.assertEqual(result['bias_r_squared'], 0.85)
        self.assertNotIn('positional_bias_metrics', result)

    def test_results_compiler_parse_config_params_missing_sections(self):
        """Test parse_config_params with missing/incomplete config."""
        # Create minimal config
        config_path = os.path.join(self.test_dir, "minimal_config.ini")
        config = configparser.ConfigParser()
        config['LLM'] = {}  # Empty section
        with open(config_path, 'w') as f:
            config.write(f)
        
        result = results_compiler.parse_config_params(config_path)
        
        # Should have defaults for missing values
        self.assertEqual(result['model'], 'unknown_model')
        self.assertEqual(result['k'], 0)
        self.assertEqual(result['m'], 0)

    def test_results_compiler_parse_config_params_file_error(self):
        """Test parse_config_params with config that causes parsing error."""
        config_path = os.path.join(self.test_dir, "bad_config.ini")
        
        # Create a config file that will cause a parsing error in the value conversion
        with open(config_path, 'w') as f:
            f.write("[Study]\nk_per_query = not_a_number\n")
        
        # The function handles missing files gracefully, but let's test the exception path
        with patch('configparser.ConfigParser.read', side_effect=Exception("Parse error")):
            with patch('src.results_compiler.logging.warning') as mock_warn:
                result = results_compiler.parse_config_params(config_path)
                self.assertIsInstance(result, dict)
                mock_warn.assert_called()

    def test_results_compiler_write_summary_csv_empty_results(self):
        """Test write_summary_csv with empty results list."""
        output_path = os.path.join(self.test_dir, "empty_output.csv")
        
        with patch('src.results_compiler.logging.warning') as mock_warn:
            results_compiler.write_summary_csv(output_path, [])
            mock_warn.assert_called_once()
            # Should not create file
            self.assertFalse(os.path.exists(output_path))

    @patch('src.results_compiler.get_config_list')
    def test_results_compiler_write_summary_csv_missing_config(self, mock_get_config_list):
        """Test write_summary_csv when config is missing."""
        mock_get_config_list.return_value = None
        output_path = os.path.join(self.test_dir, "test_output.csv")
        
        with patch('src.results_compiler.logging.error') as mock_error:
            results_compiler.write_summary_csv(output_path, [{'test': 'data'}])
            mock_error.assert_called()
            # Should not create file
            self.assertFalse(os.path.exists(output_path))

    def test_results_compiler_write_summary_csv_directory_creation(self):
        """Test write_summary_csv creates output directory."""
        nested_path = os.path.join(self.test_dir, "subdir", "nested", "output.csv")
        
        with patch('src.results_compiler.get_config_list') as mock_config:
            mock_config.return_value = ['test_col']
            results_compiler.write_summary_csv(nested_path, [{'test_col': 'value'}])
            
            # Should create the file and directories
            self.assertTrue(os.path.exists(nested_path))
            df = pd.read_csv(nested_path)
            self.assertEqual(len(df), 1)
            self.assertEqual(df.loc[0, 'test_col'], 'value')


if __name__ == '__main__':
    unittest.main()

# === End of tests/test_compilers.py ===
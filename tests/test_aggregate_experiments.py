#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 [Your Name/Institution]
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Filename: tests/test_aggregate_experiments.py

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
from src.aggregate_experiments import main as compile_main, parse_config_params

class TestAggregateExperimentsScript(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory for each test."""
        self.test_dir = tempfile.mkdtemp(prefix="test_compile_")
    
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
        with open(os.path.join(run_dir, 'config.ini.archived'), 'w') as f:
            config.write(f)

        # Create replication_report.txt
        with open(os.path.join(run_dir, f"replication_report_{run_name}.txt"), "w") as f:
            f.write(f"<<<METRICS_JSON_START>>>\n{json.dumps(metrics_data)}\n<<<METRICS_JSON_END>>>")
        return run_dir

    # Patch the source of the config object, which is safer
    @patch('config_loader.get_config_list')
    def test_main_happy_path_hierarchical(self, mock_get_config_list):
        """Test hierarchical aggregation with bias metrics flattening."""
        mock_get_config_list.return_value = ["run_directory", "model", "bias_slope"]
        
        study_dir = os.path.join(self.test_dir, "MyStudy")
        exp1_dir = os.path.join(study_dir, "experiment_A")

        self._create_mock_run(
            exp1_dir, "gpt4_rep-1",
            config_data={'LLM': {'model_name': 'gpt-4'}},
            metrics_data={'positional_bias_metrics': {'slope': 0.05}}
        )
        self._create_mock_run(
            exp1_dir, "claude3_rep-1",
            config_data={'LLM': {'model_name': 'claude-3'}},
            metrics_data={'mwu_stouffer_p': 0.88} # No bias metrics
        )
        
        with patch.object(sys, 'argv', ['aggregate_experiments.py', study_dir]):
            compile_main()

        study_output_path = os.path.join(study_dir, "STUDY_results.csv")
        self.assertTrue(os.path.exists(study_output_path))
        
        df = pd.read_csv(study_output_path)
        self.assertEqual(len(df), 2)
        
        gpt4_row = df[df['model'] == 'gpt-4'].iloc[0]
        self.assertEqual(gpt4_row['bias_slope'], 0.05)
        
        claude3_row = df[df['model'] == 'claude-3'].iloc[0]
        self.assertTrue(pd.isna(claude3_row['bias_slope']))

    @patch('logging.error')
    def test_invalid_base_directory(self, mock_log_error):
        """Test script handles a non-existent directory correctly."""
        invalid_path = os.path.join(self.test_dir, "non_existent")
        
        with patch.object(sys, 'argv', ['aggregate_experiments.py', invalid_path]):
            compile_main()
            
        mock_log_error.assert_called_with(f"Error: The specified directory does not exist: {invalid_path}")

    def test_parse_config_robustness(self):
        """Test the parse_config_params function with various legacy and current keys."""
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

# === End of tests/test_aggregate_experiments.py ===

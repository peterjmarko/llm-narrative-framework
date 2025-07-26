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
# Filename: tests/test_run_bias_analysis.py

import unittest
import os
import tempfile
import pathlib
import json
import pandas as pd
from unittest.mock import patch

# Add src to path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.run_bias_analysis import (
    main as run_bias_analysis_main,
    build_long_format_df,
    calculate_bias_metrics,
)

import argparse

class TestRunBiasAnalysis(unittest.TestCase):

    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.replication_dir = pathlib.Path(self.temp_dir_obj.name)
        self.analysis_dir = self.replication_dir / "analysis_inputs"
        self.analysis_dir.mkdir()

        # Report file
        self.report_filename = "replication_report_20240101_120000.txt"
        self.report_file = self.replication_dir / self.report_filename
        report_json_string = json.dumps({"metric": 1}, indent=4)
        self.report_file.write_text(f"<<<METRICS_JSON_START>>>\n{report_json_string}\n<<<METRICS_JSON_END>>>")

        # Data for k=3
        self.k_value = 3
        k_scores_content_block = "0.1 0.8 0.1\n0.2 0.2 0.6\n0.9 0.05 0.05\n"
        # Explicitly write two blocks separated by a double newline
        (self.analysis_dir / "all_scores.txt").write_text(k_scores_content_block + "\n" + k_scores_content_block)
        (self.analysis_dir / "all_mappings.txt").write_text("2 3 1\n3 1 2\n")

    def tearDown(self):
        self.temp_dir_obj.cleanup()

    def test_build_df_happy_path(self):
        """Test DataFrame construction with valid inputs."""
        df = build_long_format_df(str(self.replication_dir), self.k_value)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2 * 3 * 3) # 2 trials * k * k

    def test_build_df_skips_malformed_matrices(self):
        """Test that matrices with incorrect shapes are skipped."""
        malformed_scores = "0.1 0.1\n0.1 0.1\n\n" # A 2x2 matrix
        (self.analysis_dir / "all_scores.txt").write_text(malformed_scores + (self.analysis_dir / "all_scores.txt").read_text())
        # Add a dummy mapping line for the malformed matrix, which should be skipped along with the matrix
        (self.analysis_dir / "all_mappings.txt").write_text("9 9 9\n" + (self.analysis_dir / "all_mappings.txt").read_text())

        with self.assertLogs('root', level='WARNING') as cm:
            df = build_long_format_df(str(self.replication_dir), self.k_value)
            # The malformed matrix (and its mapping) are skipped, so only the 2 valid matrices are processed.
            self.assertEqual(len(df), 2 * 3 * 3)
            self.assertIn("expected (3, 3). Skipping.", cm.output[0])

    def test_build_df_handles_missing_files(self):
        """Test that None is returned if data files are missing."""
        (self.analysis_dir / "all_scores.txt").unlink()
        with self.assertLogs('root', level='WARNING'):
            self.assertIsNone(build_long_format_df(str(self.replication_dir), self.k_value))

    def test_build_df_handles_file_read_error(self):
        """Test that None is returned on file I/O error."""
        with patch('builtins.open', side_effect=IOError("Cannot read")):
            with self.assertLogs('root', level='ERROR'):
                self.assertIsNone(build_long_format_df(str(self.replication_dir), self.k_value))

    def test_calculate_metrics_empty_df(self):
        """Test metric calculation returns empty dict for empty DataFrame."""
        self.assertEqual(calculate_bias_metrics(pd.DataFrame(), self.k_value), {})

    @patch.object(argparse.ArgumentParser, 'parse_args')
    def test_main_happy_path(self, mock_parse_args):
        """Test a full successful run of the main function."""
        mock_parse_args.return_value = argparse.Namespace(
            replication_dir=str(self.replication_dir),
            k_value=self.k_value,
            verbose=True
        )
        run_bias_analysis_main()
        report_text = self.report_file.read_text()
        self.assertIn("positional_bias_metrics", report_text)
        self.assertIn("top1_pred_bias_std", report_text)

    @patch.object(argparse.ArgumentParser, 'parse_args')
    def test_main_no_report_file(self, mock_parse_args):
        """Test main exits gracefully if the report file is missing."""
        mock_parse_args.return_value = argparse.Namespace(
            replication_dir=str(self.replication_dir),
            k_value=self.k_value,
            verbose=True
        )
        self.report_file.unlink()
        with self.assertLogs('root', level='ERROR') as cm:
            run_bias_analysis_main()
            self.assertIn("No replication_report_*.txt file found", cm.output[0])
            
    @patch.object(argparse.ArgumentParser, 'parse_args')
    def test_main_no_json_block_in_report(self, mock_parse_args):
        """Test main exits gracefully if the report's JSON block is missing."""
        mock_parse_args.return_value = argparse.Namespace(
            replication_dir=str(self.replication_dir),
            k_value=self.k_value,
            verbose=True
        )
        self.report_file.write_text("This report is missing the json block")
        with self.assertLogs('root', level='ERROR') as cm:
            run_bias_analysis_main()
            self.assertIn("Could not find JSON block", cm.output[0])

    @patch.object(argparse.ArgumentParser, 'parse_args')
    def test_main_empty_dataframe(self, mock_parse_args):
        """Test main exits gracefully if the dataframe cannot be built."""
        mock_parse_args.return_value = argparse.Namespace(
            replication_dir=str(self.replication_dir),
            k_value=self.k_value,
            verbose=True
        )
        (self.analysis_dir / "all_scores.txt").unlink() # Cause df to be None
        with self.assertLogs('root', level='WARNING') as cm:
            run_bias_analysis_main()
            self.assertTrue(any("DataFrame is empty" in s for s in cm.output))

if __name__ == '__main__':
    unittest.main()

# === End of tests/test_run_bias_analysis.py ===

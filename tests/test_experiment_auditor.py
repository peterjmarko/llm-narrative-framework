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
# Filename: tests/test_experiment_auditor.py

"""
Unit Tests for the Experiment Auditor.

This script validates the state-detection logic of experiment_auditor.py
in an isolated environment with a mocked file system and configuration.
"""

import unittest
from unittest.mock import patch
import sys
import tempfile
from pathlib import Path
import configparser
import types
import importlib

# Import the module to test
from src import experiment_auditor

class TestExperimentAuditor(unittest.TestCase):
    """Test suite for experiment_auditor.py."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="exp_auditor_test_")
        self.exp_dir = Path(self.test_dir.name)
        
        self.sys_exit_patcher = patch('src.experiment_auditor.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()
        
        self._setup_mock_config()

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()
        self.config_patcher.stop()

    def _setup_mock_config(self):
        """Creates a mock config and applies it to the module."""
        mock_app_config = configparser.ConfigParser()
        mock_app_config.read_dict({
            'Study': {'num_replications': '2'}
        })
        
        fake_mod = types.ModuleType("config_loader")
        fake_mod.APP_CONFIG = mock_app_config
        fake_mod.get_config_value = lambda cfg, sec, key, **kwargs: cfg.get(sec, key, **kwargs)

        self.config_patcher = patch.dict('sys.modules', {'config_loader': fake_mod})
        self.config_patcher.start()
        importlib.reload(experiment_auditor)

    def test_get_experiment_state_new_needed_for_empty_dir(self):
        """Verify that an empty directory is correctly identified as needing a new run."""
        # --- Arrange ---
        expected_reps = 2
        
        # --- Act ---
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, expected_reps)
        
        # --- Assert ---
        self.assertEqual(state_name, "NEW_NEEDED")
        self.assertEqual(payload, [])


if __name__ == '__main__':
    unittest.main()

# === End of tests/test_experiment_auditor.py ===

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
# Filename: tests/test_robustness.py

import unittest
from unittest.mock import patch
import os
import sys
import tempfile
import configparser
import types
import importlib
import shutil

# This test no longer needs to know about the real source directory's path,
# as it will be imported via Python's standard module system.

class TestPipelineRobustness(unittest.TestCase):

    def setUp(self):
        """Create a temporary directory for output and config, but run the real source code."""
        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="robust_test_proj_")
        self.test_project_root = self.test_project_root_obj.name

        # The output directory will be inside our temporary project root.
        self.output_dir = os.path.join(self.test_project_root, 'output')
        os.makedirs(self.output_dir)

        # We will create the config in each test to control its content.
        self.mock_config = configparser.ConfigParser()

        # Patch sys.modules to replace the real config_loader with our fake one.
        # This is a robust way to handle dependencies without file patching.
        self.original_sys_modules = dict(sys.modules)
        self._setup_fake_config_loader()

        # Now, import the orchestrator from the REAL src directory.
        # The coverage tool will see this execution.
        # We must reload it to ensure it uses our faked config_loader module.
        import src.orchestrate_replication
        importlib.reload(src.orchestrate_replication)
        self.orchestrator_main = src.orchestrate_replication.main

    def tearDown(self):
        """Clean up the temporary directory and restore system state."""
        # Restore sys.modules to its original state to prevent test leakage.
        for name in list(sys.modules.keys()):
            if name not in self.original_sys_modules:
                del sys.modules[name]
        for name, module in self.original_sys_modules.items():
            if name not in sys.modules or sys.modules[name] is not module:
                sys.modules[name] = module
        
        # Clean up the temporary directory and its contents.
        self.test_project_root_obj.cleanup()

    def _setup_fake_config_loader(self):
        """Replaces the config_loader in sys.modules with a mock."""
        if 'config_loader' in sys.modules:
            del sys.modules['config_loader']
        
        fake_mod = types.ModuleType("config_loader")
        fake_mod.PROJECT_ROOT = self.test_project_root
        fake_mod.APP_CONFIG = self.mock_config
        
        def dummy_get_config_value(config, section, key, fallback=None, value_type=str, **kwargs):
            # CORRECTED LOGIC: This now correctly returns the found value.
            if config.has_option(section, key):
                try:
                    if value_type is int: return config.getint(section, key)
                    if value_type is float: return config.getfloat(section, key)
                    return config.get(section, key)
                except (ValueError, configparser.NoOptionError):
                    return fallback
            return fallback
            
        fake_mod.get_config_value = dummy_get_config_value
        sys.modules['config_loader'] = fake_mod

    def test_orchestrator_handles_missing_temperature_key(self):
        """Test that generate_run_dir_name uses fallback for a missing config key."""
        with patch('src.orchestrate_replication.run_script') as mock_run_script:
            self.mock_config['General'] = {'base_output_dir': 'output'}
            self.mock_config['LLM'] = {'model_name': 'test-model'} # No temperature key
            self.mock_config['Filenames'] = {'personalities_src': 'db.txt'}
            self.mock_config['Study'] = {'num_trials': '1', 'group_size': '1'}
            mock_run_script.return_value = ("Mocked success", 0, None)

            with open(os.path.join(self.test_project_root, 'config.ini'), 'w') as f:
                self.mock_config.write(f)

            orchestrator_args = ['orchestrate_replication.py', '--replication_num', '1']
            with patch.object(sys, 'argv', orchestrator_args):
                self.orchestrator_main()

            run_dirs = [d for d in os.listdir(self.output_dir) if d.startswith('run_')]
            self.assertEqual(len(run_dirs), 1, "Expected exactly one run directory.")
            self.assertIn("tmp-NA", run_dirs[0], "Directory name should contain the fallback 'tmp-NA'.")

    def test_orchestrator_handles_invalid_temperature_value(self):
        """Test that generate_run_dir_name handles non-numeric temperature value."""
        with patch('src.orchestrate_replication.run_script') as mock_run_script:
            self.mock_config['General'] = {'base_output_dir': 'output'}
            self.mock_config['LLM'] = {'model_name': 'test-model', 'temperature': 'not-a-float'}
            self.mock_config['Filenames'] = {'personalities_src': 'db.txt'}
            self.mock_config['Study'] = {'num_trials': '1', 'group_size': '1'}
            mock_run_script.return_value = ("Mocked success", 0, None)

            with open(os.path.join(self.test_project_root, 'config.ini'), 'w') as f:
                self.mock_config.write(f)

            orchestrator_args = ['orchestrate_replication.py', '--replication_num', '1']
            with patch.object(sys, 'argv', orchestrator_args):
                self.orchestrator_main()

            run_dirs = [d for d in os.listdir(self.output_dir) if d.startswith('run_')]
            self.assertEqual(len(run_dirs), 1)
            self.assertIn("tmp-NA", run_dirs[0], "Directory name should contain 'tmp-NA' for invalid temperature.")

# === End of tests/test_robustness.py ===

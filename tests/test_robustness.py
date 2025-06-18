import unittest
from unittest.mock import patch
import os
import sys
import tempfile
import configparser
import types
import importlib
import shutil

# --- Test Configuration & Setup ---
SCRIPT_DIR_TEST = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_FOR_TEST = os.path.abspath(os.path.join(SCRIPT_DIR_TEST, '..'))
SRC_DIR_REAL = os.path.join(PROJECT_ROOT_FOR_TEST, 'src')

ORCHESTRATOR_SCRIPT_NAME = "orchestrate_experiment.py"

class TestPipelineRobustness(unittest.TestCase):

    def setUp(self):
        """Create a temporary project structure for an isolated test run."""
        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="robust_test_proj_")
        self.test_project_root = self.test_project_root_obj.name

        self.src_dir = os.path.join(self.test_project_root, 'src')
        self.output_dir = os.path.join(self.test_project_root, 'output')
        
        os.makedirs(self.src_dir)
        os.makedirs(self.output_dir)
        
        # Copy the orchestrator script to the temp src directory
        shutil.copy2(os.path.join(SRC_DIR_REAL, ORCHESTRATOR_SCRIPT_NAME), self.src_dir)

        # We will create the config in each test to control its content
        self.mock_config = configparser.ConfigParser()

        # Patch sys.path and sys.modules
        self.original_sys_path = list(sys.path)
        self.original_sys_modules = dict(sys.modules)
        sys.path.insert(0, self.src_dir)
        
        self._setup_fake_config_loader()
        
        # Import the main function from the orchestrator script
        module_name = os.path.splitext(ORCHESTRATOR_SCRIPT_NAME)[0]
        if module_name in sys.modules:
            reloaded_module = importlib.reload(sys.modules[module_name])
            self.orchestrator_main = reloaded_module.main
        else:
            imported_module = importlib.import_module(module_name)
            self.orchestrator_main = imported_module.main

    def tearDown(self):
        """Clean up the temporary directory and restore system state."""
        sys.path[:] = self.original_sys_path
        for name in list(sys.modules.keys()):
            if name not in self.original_sys_modules:
                del sys.modules[name]
        for name, module in self.original_sys_modules.items():
            if name not in sys.modules or sys.modules[name] is not module:
                sys.modules[name] = module
        self.test_project_root_obj.cleanup()

    def _setup_fake_config_loader(self):
        """Replaces the config_loader in sys.modules with a mock."""
        if 'config_loader' in sys.modules:
            del sys.modules['config_loader']
        
        fake_mod = types.ModuleType("config_loader")
        fake_mod.PROJECT_ROOT = self.test_project_root
        fake_mod.APP_CONFIG = self.mock_config
        
        def dummy_get_config_value(config, section, key, fallback=None, value_type=str):
            # This is a simplified version for testing; the real one is more robust.
            if not config.has_option(section, key): return fallback
            try:
                if value_type is int: return config.getint(section, key)
                if value_type is float: return config.getfloat(section, key)
                return config.get(section, key)
            except (ValueError, configparser.NoOptionError):
                return fallback
            
        fake_mod.get_config_value = dummy_get_config_value
        sys.modules['config_loader'] = fake_mod

    @patch('orchestrate_experiment.run_script') # Mock run_script to prevent running subprocesses
    def test_orchestrator_handles_missing_temperature_key(self, mock_run_script):
        """Test that generate_run_dir_name uses fallback for a missing config key."""
        # --- Setup a config file MISSING the 'temperature' key ---
        self.mock_config['General'] = {'base_output_dir': 'output'}
        self.mock_config['LLM'] = {'model_name': 'test-model'}
        self.mock_config['Filenames'] = {'personalities_src': 'db.txt'}
        
        # Mock run_script to simply return success so the pipeline "completes"
        mock_run_script.return_value = "Mocked success"
        
        # --- Run the orchestrator ---
        # The orchestrator now reads k and m from config, so we add them here
        # and remove the obsolete command-line arguments.
        self.mock_config['Study'] = {'num_trials': '1', 'group_size': '1'}
        orchestrator_args = ['orchestrate_experiment.py']
        with patch.object(sys, 'argv', orchestrator_args):
            self.orchestrator_main()

        # --- Assertions ---
        # Find the created run directory
        run_dirs = [d for d in os.listdir(self.output_dir) if d.startswith('run_')]
        self.assertEqual(len(run_dirs), 1, "Expected exactly one run directory.")
        
        # Check that the directory name contains the fallback temperature
        # The generate_run_dir_name function defaults to 0.0, which formats to "tmp-0.00"
        self.assertIn("tmp-0.00", run_dirs[0], "Directory name should contain the fallback temperature 'tmp-0.00'.")

    @patch('orchestrate_experiment.run_script')
    def test_orchestrator_handles_invalid_temperature_value(self, mock_run_script):
        """Test that generate_run_dir_name handles non-numeric temperature value."""
        # --- Setup a config file with an INVALID 'temperature' value ---
        self.mock_config['General'] = {'base_output_dir': 'output'}
        self.mock_config['LLM'] = {
            'model_name': 'test-model',
            'temperature': 'not-a-float' # Invalid value
        }
        self.mock_config['Filenames'] = {'personalities_src': 'db.txt'}
        
        mock_run_script.return_value = "Mocked success"
        
        # --- Run the orchestrator ---
        # The orchestrator now reads k and m from config, so we add them here
        # and remove the obsolete command-line arguments.
        self.mock_config['Study'] = {'num_trials': '1', 'group_size': '1'}
        orchestrator_args = ['orchestrate_experiment.py']
        with patch.object(sys, 'argv', orchestrator_args):
            self.orchestrator_main()

        # --- Assertions ---
        run_dirs = [d for d in os.listdir(self.output_dir) if d.startswith('run_')]
        self.assertEqual(len(run_dirs), 1)
        
        # The try-except block in generate_run_dir_name should catch the ValueError
        # and use the default formatted value "tmp-0.00".
        self.assertIn("tmp-0.00", run_dirs[0], "Directory name should contain the fallback 'tmp-0.00' for invalid temperature.")
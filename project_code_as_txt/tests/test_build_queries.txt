import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import os
import sys
import shutil
import tempfile
import configparser
import types 
import pandas as pd
import importlib
import subprocess # For CompletedProcess

SCRIPT_DIR_TEST = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_FOR_SRC = os.path.abspath(os.path.join(SCRIPT_DIR_TEST, '..'))
SRC_DIR_REAL_PROJECT = os.path.join(PROJECT_ROOT_FOR_SRC, 'src')

build_queries_main_under_test = None

class TestBuildQueries(unittest.TestCase):

    DUMMY_QGEN_FILENAME = "query_generator.py" # This is what build_queries.py uses

    @classmethod
    def setUpClass(cls):
        cls.original_sys_path = list(sys.path)
        if SRC_DIR_REAL_PROJECT not in sys.path:
            sys.path.insert(0, SRC_DIR_REAL_PROJECT)

    @classmethod
    def tearDownClass(cls):
        sys.path = cls.original_sys_path
        if SRC_DIR_REAL_PROJECT in sys.path:
            try: sys.path.remove(SRC_DIR_REAL_PROJECT)
            except ValueError: pass

    def setUp(self):
        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="test_build_queries_proj_")
        self.test_project_root = self.test_project_root_obj.name

        self.test_src_dir = os.path.join(self.test_project_root, "src")
        self.test_data_dir = os.path.join(self.test_project_root, "data")
        self.cfg_base_output_dir_name = "output"
        self.cfg_queries_subdir_name = "session_queries_bq"
        
        # This is the directory that will be passed to the --run_output_dir argument
        self.test_run_dir = os.path.join(self.test_project_root, self.cfg_base_output_dir_name, "run_test_build_queries")

        os.makedirs(self.test_src_dir, exist_ok=True)
        os.makedirs(self.test_data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.test_project_root, self.cfg_base_output_dir_name), exist_ok=True)
        # build_queries.py itself will create self.final_queries_output_dir

        self.mock_config_parser_obj = configparser.ConfigParser()
        self.mock_config_parser_obj['General'] = {
            'default_log_level': 'DEBUG', 'default_k': '3', 
            'default_build_iterations': '2', 
            'base_output_dir': self.cfg_base_output_dir_name,
            'queries_subdir': self.cfg_queries_subdir_name,
        }
        self.mock_config_parser_obj['Filenames'] = {
            'personalities_src': 'test_personalities.txt',
            'base_query_src': 'test_base_query.txt', # build_queries reads this to pass to qgen
            'temp_subset_personalities': 'temp_subset_bq.txt',
            'used_indices_log': 'used_indices_bq.log',
            'aggregated_mappings_in_queries_dir': 'mappings_bq.txt',
            'qgen_temp_prefix': '' 
        }
        self.mock_config_parser_obj['LLM'] = {}
        self.mock_config_parser_obj['MetaAnalysis'] = {}

        self.original_sys_modules = dict(sys.modules)
        self._setup_fake_config_loader_in_sys_modules()

        # Create dummy base_query_file in the test data directory, as build_queries will pass its name
        # and the real query_generator (if called) would try to find it via PROJECT_ROOT/data
        # Our mock for subprocess.run will intercept this, but good for completeness.
        self.dummy_base_query_path = os.path.join(self.test_data_dir, 
                                                 self.mock_config_parser_obj['Filenames']['base_query_src'])
        with open(self.dummy_base_query_path, "w") as f: f.write("BaseQueryText\nDummy base query content.")


        self.master_personalities_path = os.path.join(self.test_data_dir, 
                                                      self.mock_config_parser_obj['Filenames']['personalities_src'])
        self._create_dummy_master_personalities_file(self.master_personalities_path, num_personalities=20)

        module_name_to_test = 'build_queries'
        global build_queries_main_under_test
        if module_name_to_test in sys.modules:
            reloaded_module = importlib.reload(sys.modules[module_name_to_test])
            build_queries_main_under_test = reloaded_module.main
        else:
            imported_module = importlib.import_module(module_name_to_test)
            build_queries_main_under_test = imported_module.main

    def _setup_fake_config_loader_in_sys_modules(self):
        # ... (same as before)
        if "config_loader" in sys.modules: del sys.modules["config_loader"]
        fake_mod = types.ModuleType("config_loader")
        fake_mod.PROJECT_ROOT = self.test_project_root 
        fake_mod.APP_CONFIG = self.mock_config_parser_obj
        def dummy_get_config_value(config, section, key, fallback=None, value_type=str):
            if not config.has_section(section) or not config.has_option(section,key): return fallback
            val_str = config.get(section, key)
            if value_type is int: return int(val_str)
            if value_type is float: return float(val_str)
            if value_type is bool: return val_str.lower() in ['true', '1', 'yes', 'on']
            return val_str
        fake_mod.get_config_value = dummy_get_config_value
        fake_mod.ENV_LOADED = False
        sys.modules["config_loader"] = fake_mod

    def _create_dummy_master_personalities_file(self, filepath, num_personalities=20):
        # ... (same as before)
        header = "Index\tName\tBirthYear\tDescriptionText\n"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header)
            for i in range(1, num_personalities + 1):
                f.write(f"{100+i}\tPersonality_{i}\t{1900+i}\tDescription for personality {i}.\n")

    def tearDown(self):
        # ... (same robust tearDown as in test_process_llm_responses)
        current_sys_modules = dict(sys.modules)
        for name in list(current_sys_modules.keys()): 
            if name not in self.original_sys_modules:
                del sys.modules[name]
        for name, module in self.original_sys_modules.items():
            if name not in sys.modules or sys.modules[name] is not module:
                sys.modules[name] = module
        self.test_project_root_obj.cleanup()

    def mock_query_generator_subprocess(self, cmd_list_args, **kwargs):
        """
        Mock for subprocess.run specifically when calling query_generator.py.
        It needs to simulate file creation by query_generator.py.
        """
        k_val = 3
        output_basename_prefix = None
        seed_val = None

        try:
            k_idx = cmd_list_args.index('-k')
            k_val = int(cmd_list_args[k_idx+1])
            prefix_idx = cmd_list_args.index('--output_basename_prefix')
            output_basename_prefix = cmd_list_args[prefix_idx+1]
            if '--seed' in cmd_list_args:
                seed_idx = cmd_list_args.index('--seed')
                seed_val = int(cmd_list_args[seed_idx+1])
        except (ValueError, IndexError) as e:
            return subprocess.CompletedProcess(args=cmd_list_args, returncode=1, stdout="", stderr=f"Mock QGEN: Arg parsing error: {e}")

        if not output_basename_prefix:
            return subprocess.CompletedProcess(args=cmd_list_args, returncode=1, stdout="", stderr="Mock QGEN: Missing output_basename_prefix")

        # The CWD is set by build_queries.py to its own script's directory.
        # In the test setup, this directory is mocked, but we can rely on the 'cwd' kwarg.
        worker_cwd = kwargs.get('cwd', os.getcwd())
        
        # The prefix contains the temporary directory name, e.g., "temp_qgen_outputs_iter_001/iter_001_"
        # We need to create this directory inside the worker's CWD.
        qgen_output_dir = os.path.join(worker_cwd, os.path.dirname(output_basename_prefix))
        qgen_base_filename = os.path.basename(output_basename_prefix)
        
        os.makedirs(qgen_output_dir, exist_ok=True)

        # Simulate query_generator.py creating its files
        query_text_path = os.path.join(qgen_output_dir, qgen_base_filename + "llm_query.txt")
        with open(query_text_path, "w") as f:
            f.write(f"Mocked llm query for k={k_val}, seed={seed_val}\n")
            for i in range(k_val):
                f.write(f"Mocked Person {i+1} from QGEN\n")

        mapping_filepath = os.path.join(qgen_output_dir, qgen_base_filename + "mapping.txt")
        with open(mapping_filepath, "w") as f:
            map_header = "\t".join([f"Map_idx{j+1}" for j in range(k_val)])
            f.write(map_header + "\n")
            mapping_data = list(range(1, k_val + 1))
            if seed_val is not None:
                for i_map in range(k_val):
                    swap_idx = (seed_val + i_map) % k_val
                    mapping_data[i_map], mapping_data[swap_idx] = mapping_data[swap_idx], mapping_data[i_map]
            f.write("\t".join(map(str, mapping_data)) + "\n")
        
        # ADD THIS BLOCK: Simulate creation of the manifest file
        manifest_filepath = os.path.join(qgen_output_dir, qgen_base_filename + "manifest.txt")
        with open(manifest_filepath, "w") as f:
            f.write("Name_in_Query\tName_Ref_ID\tShuffled_Desc_Index\tDesc_Ref_ID\tDesc_in_Query\n")
            # Create dummy manifest data that is consistent with the mapping data
            for i_manifest in range(k_val):
                name_ref_id = i_manifest # Simplified for mock
                desc_index = mapping_data[i_manifest]
                f.write(f"Mock Name {i_manifest}\t{name_ref_id}\t{desc_index}\t{name_ref_id}\tMock Desc\n")

        return subprocess.CompletedProcess(args=cmd_list_args, returncode=0, stdout="Mock QGEN success", stderr="")


    @patch('builtins.input', return_value='new')
    @patch('subprocess.run') # Patch subprocess.run globally for this test method
    def test_new_run_creates_files_and_logs(self, mock_subprocess_run, mock_input):
        mock_subprocess_run.side_effect = self.mock_query_generator_subprocess
        num_iterations = 2
        k_per_query = self.mock_config_parser_obj.getint('General', 'default_k')

        cli_args = [
            'build_queries.py', '-m', str(num_iterations), '-k', str(k_per_query),
            '--base_seed', '42', '--qgen_base_seed', '100',
            '--run_output_dir', self.test_run_dir
        ]
        with patch.object(sys, 'argv', cli_args):
            build_queries_main_under_test()

        # Assertions now check inside the run-specific queries subdirectory
        run_queries_dir = os.path.join(self.test_run_dir, self.cfg_queries_subdir_name)
        self.assertTrue(os.path.exists(run_queries_dir))
        for i in range(1, num_iterations + 1):
            query_file = os.path.join(run_queries_dir, f"llm_query_{i:03d}.txt")
            self.assertTrue(os.path.exists(query_file), f"{query_file} not found")
        
        # Note: run_queries_dir was already defined earlier in this test.
        mappings_file_path = os.path.join(run_queries_dir, self.mock_config_parser_obj['Filenames']['aggregated_mappings_in_queries_dir'])
        self.assertTrue(os.path.exists(mappings_file_path))
        with open(mappings_file_path, "r") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), num_iterations + 1)
            self.assertTrue(lines[0].startswith("Map_idx1"))

        used_indices_file_path = os.path.join(run_queries_dir, self.mock_config_parser_obj['Filenames']['used_indices_log'])
        self.assertTrue(os.path.exists(used_indices_file_path))
        with open(used_indices_file_path, "r") as f:
            used_indices_lines = [line.strip() for line in f.readlines() if line.strip()]
        self.assertEqual(len(used_indices_lines), num_iterations * k_per_query)
        self.assertEqual(len(set(used_indices_lines)), num_iterations * k_per_query)

    @patch('builtins.input', return_value='new')
    @patch('subprocess.run')
    def test_seeding_is_deterministic(self, mock_subprocess_run, mock_input):
        """
        Tests that providing the same seeds results in identical output files across two separate runs.
        """
        mock_subprocess_run.side_effect = self.mock_query_generator_subprocess
        
        # --- Define Test Parameters ---
        num_iterations = 2
        k_per_query = 3
        # The base run directory is defined in setUp, we just use it here.
        test_run_dir = self.test_run_dir
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        
        # Command-line arguments with fixed seeds
        cli_args = [
            'build_queries.py', '-m', str(num_iterations), '-k', str(k_per_query),
            '--mode', 'new', '--base_seed', '777', '--qgen_base_seed', '888',
            '--run_output_dir', test_run_dir
        ]

        # --- First Run ---
        print("\n--- Seeding Test: First Run ---")
        with patch.object(sys, 'argv', cli_args):
            build_queries_main_under_test()
            
        # Assert files were created and read their content
        mappings_path_run1 = os.path.join(run_queries_dir, self.mock_config_parser_obj['Filenames']['aggregated_mappings_in_queries_dir'])
        query_path_run1 = os.path.join(run_queries_dir, "llm_query_001.txt")
        
        self.assertTrue(os.path.exists(mappings_path_run1))
        self.assertTrue(os.path.exists(query_path_run1))
        
        with open(mappings_path_run1, 'r') as f:
            content_mappings_run1 = f.read()
        with open(query_path_run1, 'r') as f:
            content_query_run1 = f.read()

        # --- Second Run ---
        # The key is that build_queries with --mode new will clear the directory,
        # so we are testing a full regeneration.
        print("\n--- Seeding Test: Second Run (with same seed) ---")
        with patch.object(sys, 'argv', cli_args):
            # Reload the module to reset any internal state if necessary, although a well-written
            # script shouldn't need this, it's safer for testing.
            if 'build_queries' in sys.modules:
                reloaded_module = importlib.reload(sys.modules['build_queries'])
                reloaded_module.main()
            else:
                build_queries_main_under_test()

        # Assert files were re-created and read their new content
        mappings_path_run2 = os.path.join(run_queries_dir, self.mock_config_parser_obj['Filenames']['aggregated_mappings_in_queries_dir'])
        query_path_run2 = os.path.join(run_queries_dir, "llm_query_001.txt")

        self.assertTrue(os.path.exists(mappings_path_run2))
        self.assertTrue(os.path.exists(query_path_run2))

        with open(mappings_path_run2, 'r') as f:
            content_mappings_run2 = f.read()
        with open(query_path_run2, 'r') as f:
            content_query_run2 = f.read()
            
        # --- Final Assertion ---
        # The content of the files from both runs must be identical.
        self.assertEqual(content_mappings_run1, content_mappings_run2, "Mappings file content differs between seeded runs.")
        self.assertEqual(content_query_run1, content_query_run2, "Query file content differs between seeded runs.")

    @patch('builtins.input')
    @patch('subprocess.run')
    def test_continue_run_appends_and_respects_used(self, mock_subprocess_run, mock_input):
        mock_subprocess_run.side_effect = self.mock_query_generator_subprocess
        num_iterations_initial = 1
        num_iterations_continue = 1
        k_per_query = self.mock_config_parser_obj.getint('General', 'default_k')
        total_personalities_needed = (num_iterations_initial + num_iterations_continue) * k_per_query
        self._create_dummy_master_personalities_file(self.master_personalities_path, num_personalities=total_personalities_needed + 5)

        mock_input.return_value = 'new'
        cli_args_run1 = ['build_queries.py', '-m', str(num_iterations_initial), '-k', str(k_per_query), '--base_seed', '10', '--qgen_base_seed', '110', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args_run1):
            build_queries_main_under_test()

        if 'build_queries' in sys.modules:
            reloaded_bq_module = importlib.reload(sys.modules['build_queries'])
            current_main_to_call = reloaded_bq_module.main
        else:
            current_main_to_call = build_queries_main_under_test

        mock_input.return_value = 'continue'
        cli_args_run2 = ['build_queries.py', '-m', str(num_iterations_continue), '-k', str(k_per_query), '--base_seed', '20', '--qgen_base_seed', '120', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args_run2):
            current_main_to_call()

        run_queries_dir = os.path.join(self.test_run_dir, self.cfg_queries_subdir_name)
        self.assertTrue(os.path.exists(os.path.join(run_queries_dir, f"llm_query_{num_iterations_initial + 1:03d}.txt")))

        mappings_file_path = os.path.join(run_queries_dir, self.mock_config_parser_obj['Filenames']['aggregated_mappings_in_queries_dir'])
        with open(mappings_file_path, "r") as f:
            lines2 = f.readlines()
        self.assertEqual(len(lines2), (num_iterations_initial + num_iterations_continue) + 1)

        used_indices_file_path = os.path.join(run_queries_dir, self.mock_config_parser_obj['Filenames']['used_indices_log'])
        with open(used_indices_file_path, "r") as f:
            used_indices_lines = [line.strip() for line in f.readlines() if line.strip()]
        self.assertEqual(len(used_indices_lines), (num_iterations_initial + num_iterations_continue) * k_per_query)
        self.assertEqual(len(set(used_indices_lines)), (num_iterations_initial + num_iterations_continue) * k_per_query)
        
        # Note: run_queries_dir was already defined earlier in this test.
        used_indices_file_path = os.path.join(run_queries_dir, self.mock_config_parser_obj['Filenames']['used_indices_log'])
        with open(used_indices_file_path, "r") as f: 
            used_indices_lines = [line.strip() for line in f.readlines() if line.strip()]
        self.assertEqual(len(used_indices_lines), (num_iterations_initial + num_iterations_continue) * k_per_query)
        self.assertEqual(len(set(used_indices_lines)), (num_iterations_initial + num_iterations_continue) * k_per_query)


    @patch('subprocess.run') # Not actually called if exit happens early
    @patch('builtins.input', return_value='new')
    @patch('sys.exit') 
    @patch('logging.error') 
    def test_insufficient_personalities(self, mock_log_error, mock_sys_exit, mock_input, mock_subprocess_run_placeholder):
        num_iterations = 3
        k_per_query = self.mock_config_parser_obj.getint('General', 'default_k')
        needed = num_iterations * k_per_query
        self._create_dummy_master_personalities_file(self.master_personalities_path, num_personalities=needed - 1)

        cli_args = ['build_queries.py', '-m', str(num_iterations), '-k', str(k_per_query), '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            if 'build_queries' in sys.modules:
                reloaded_bq_module = importlib.reload(sys.modules['build_queries'])
                reloaded_bq_module.main()
            else:
                build_queries_main_under_test()
        
        mock_sys_exit.assert_called_once_with(1)
        error_found = any("Not enough unique *available* personalities" in str(call_arg) for call_arg in mock_log_error.call_args_list)
        self.assertTrue(error_found, "Expected 'Not enough personalities' error message not logged.")

    @patch('builtins.input', return_value='new')
    @patch('subprocess.run')
    def test_manifest_creation_and_consistency(self, mock_subprocess_run, mock_input):
        """
        Tests that build_queries orchestrates the creation of manifest files
        and that their content is consistent with the final aggregated mappings.txt.
        """
        mock_subprocess_run.side_effect = self.mock_query_generator_subprocess
        num_iterations = 2
        k_per_query = 3

        cli_args = [
            'build_queries.py', '-m', str(num_iterations), '-k', str(k_per_query),
            '--base_seed', '999', '--qgen_base_seed', '888',
            '--run_output_dir', self.test_run_dir
        ]
        with patch.object(sys, 'argv', cli_args):
            build_queries_main_under_test()

        # --- Assertions ---
        run_queries_dir = os.path.join(self.test_run_dir, self.cfg_queries_subdir_name)
        # 1. Check that manifest files were created
        for i in range(1, num_iterations + 1):
            manifest_file = os.path.join(run_queries_dir, f"llm_query_{i:03d}_manifest.txt")
            self.assertTrue(os.path.exists(manifest_file), f"{manifest_file} was not created.")

        # 2. Read the final aggregated mappings file
        # Note: run_queries_dir was already defined earlier in this test.
        mappings_file_path = os.path.join(run_queries_dir, self.mock_config_parser_obj['Filenames']['aggregated_mappings_in_queries_dir'])
        with open(mappings_file_path, "r") as f:
            mapping_lines = f.read().strip().split('\n')
        
        # Header + num_iterations lines
        self.assertEqual(len(mapping_lines), num_iterations + 1)
        
        aggregated_mappings = [line.strip().split('\t') for line in mapping_lines[1:]]

        # 3. Cross-validate each manifest against the aggregated mappings
        for i in range(num_iterations):
            # OLD LINE:
            # manifest_file_path = os.path.join(self.final_queries_output_dir, f"llm_query_{i+1:03d}_manifest.txt")
            
            # NEW, CORRECTED LINE:
            manifest_file_path = os.path.join(run_queries_dir, f"llm_query_{i+1:03d}_manifest.txt")

            # Read the manifest into a more usable format (e.g., list of dicts)
            with open(manifest_file_path, "r") as f:
                manifest_lines = f.read().strip().split('\n')
            
            manifest_header = manifest_lines[0].split('\t')
            manifest_data = [dict(zip(manifest_header, line.split('\t'))) for line in manifest_lines[1:]]
            
            # The order of rows in the manifest corresponds to the shuffled names (List A).
            # The mapping file line also corresponds to the shuffled names in the same order.
            # So, the nth value in the mapping line should equal the 'Shuffled_Desc_Index' of the nth row in the manifest.
            
            mapping_for_this_iter = aggregated_mappings[i]
            self.assertEqual(len(mapping_for_this_iter), k_per_query)
            
            for j in range(k_per_query):
                manifest_row = manifest_data[j]
                
                # Get the true description index from the manifest
                desc_index_from_manifest = manifest_row.get('Shuffled_Desc_Index')
                self.assertIsNotNone(desc_index_from_manifest, "Manifest is missing 'Shuffled_Desc_Index' column.")
                
                # Get the mapping from the aggregated file
                mapping_from_agg_file = mapping_for_this_iter[j]
                
                # Compare them
                self.assertEqual(
                    int(desc_index_from_manifest),
                    int(mapping_from_agg_file),
                    f"Mismatch in iter {i+1}, item {j+1}: manifest says desc index is {desc_index_from_manifest}, "
                    f"but mappings.txt says it is {mapping_from_agg_file}."
                )


if __name__ == '__main__':
    unittest.main(verbosity=2)
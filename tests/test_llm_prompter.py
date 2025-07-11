import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import json
import subprocess
import requests
from pathlib import Path
import tempfile
import importlib

# --- CORRECT PATH DEFINITIONS USING PATHLIB ---
PROJECT_ROOT_TEST = Path(__file__).resolve().parent.parent
SRC_DIR_TEST = PROJECT_ROOT_TEST / "src"
LLM_PROMPTER_SCRIPT_PATH = SRC_DIR_TEST / "llm_prompter.py"

# Modify sys.path using the new Path objects (converted to strings)
if str(SRC_DIR_TEST) not in sys.path:
    sys.path.insert(0, str(SRC_DIR_TEST))
if str(PROJECT_ROOT_TEST) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_TEST))

# Now that sys.path is correct, import the module for unit testing
from src import llm_prompter


class TestLLMPrompterEndToEnd(unittest.TestCase):

    def setUp(self):
        self.test_run_dir_obj = tempfile.TemporaryDirectory(prefix="test_llm_prompter_run_")
        self.test_run_dir = self.test_run_dir_obj.name
        self.input_query_file = os.path.join(self.test_run_dir, "test_query_input.txt")
        self.output_response_file = os.path.join(self.test_run_dir, "test_response_output.txt")
        self.output_error_file = os.path.join(self.test_run_dir, "test_error_output.txt")

    def tearDown(self):
        self.test_run_dir_obj.cleanup()

    def create_test_input_query_file(self, content="Default test query content."):
        with open(self.input_query_file, "w", encoding='utf-8') as f:
            f.write(content)

    def run_llm_prompter_subprocess(self, query_id, cli_extra_args=None, custom_env=None, cwd_override=None):
        coveragerc_path = PROJECT_ROOT_TEST / ".coveragerc"
        script_to_run_path = LLM_PROMPTER_SCRIPT_PATH
        base_cmd = [
            sys.executable, "-m", "coverage", "run",
            "--rcfile", str(coveragerc_path), "--parallel-mode",
            str(script_to_run_path), query_id,
            "--input_query_file", self.input_query_file,
            "--output_response_file", self.output_response_file,
            "--output_error_file", self.output_error_file,
        ]
        if cli_extra_args:
            base_cmd.extend(cli_extra_args)
        env_for_subprocess = custom_env if custom_env is not None else os.environ.copy()
        cwd_for_subprocess = cwd_override if cwd_override is not None else str(PROJECT_ROOT_TEST)
        return subprocess.run(
            base_cmd, capture_output=True, text=True,
            cwd=cwd_for_subprocess, encoding='utf-8', env=env_for_subprocess,
        )

    def test_llm_prompter_success_scenario(self):
        self.create_test_input_query_file(content="Success query.")
        extra_args = ["--test_mock_api_outcome", "success", "--test_mock_api_content", "Mocked success."]
        result = self.run_llm_prompter_subprocess("test_success_001", extra_args)
        self.assertEqual(result.returncode, 0)

    def test_llm_prompter_api_failure_scenario(self):
        self.create_test_input_query_file(content="API failure query.")
        extra_args = ["--test_mock_api_outcome", "api_returns_none"]
        result = self.run_llm_prompter_subprocess("test_fail_002", extra_args)
        self.assertNotEqual(result.returncode, 0)

    def test_llm_prompter_input_file_not_found(self):
        if os.path.exists(self.input_query_file): os.remove(self.input_query_file)
        result = self.run_llm_prompter_subprocess("test_nofile_003")
        self.assertNotEqual(result.returncode, 0)

    def test_llm_prompter_api_timeout_scenario(self):
        self.create_test_input_query_file(content="Timeout query.")
        extra_args = ["--test_mock_api_outcome", "api_timeout"]
        result = self.run_llm_prompter_subprocess("test_timeout_004", extra_args)
        self.assertNotEqual(result.returncode, 0)

    def test_llm_prompter_interactive_mode(self):
        cmd = [
            sys.executable, str(LLM_PROMPTER_SCRIPT_PATH), "--interactive_test_mode",
            "--test_mock_api_outcome", "success", "--test_mock_api_content", "Interactive success."
        ]
        env_with_key = os.environ.copy()
        env_with_key["OPENROUTER_API_KEY"] = "dummy-key"
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SRC_DIR_TEST), encoding='utf-8', env=env_with_key)
        self.assertEqual(result.returncode, 0, f"STDERR: {result.stderr}")
        for f in ["interactive_test_query.txt", "interactive_test_response.txt", "interactive_test_error.txt", "interactive_test_response_full.json"]:
            if os.path.exists(SRC_DIR_TEST / f): os.remove(SRC_DIR_TEST / f)

    def test_llm_prompter_empty_input_file(self):
        self.create_test_input_query_file(content="")
        result = self.run_llm_prompter_subprocess("test_emptyfile_005")
        self.assertNotEqual(result.returncode, 0)

    def test_llm_prompter_generic_exception_scenario(self):
        self.create_test_input_query_file(content="Generic exception query.")
        extra_args = ["--test_mock_api_outcome", "generic_exception_in_api"]
        result = self.run_llm_prompter_subprocess("test_generic_exception_007", extra_args)
        self.assertNotEqual(result.returncode, 0)

    def test_llm_prompter_keyboard_interrupt_scenario(self):
        self.create_test_input_query_file(content="Interrupt query.")
        extra_args = ["--test_mock_api_outcome", "keyboard_interrupt"]
        result = self.run_llm_prompter_subprocess("test_interrupt_008", extra_args)
        self.assertNotEqual(result.returncode, 0)

    def test_llm_prompter_api_http_401_scenario(self):
        self.create_test_input_query_file(content="401 query.")
        extra_args = ["--test_mock_api_outcome", "api_http_401"]
        result = self.run_llm_prompter_subprocess("test_http_401_009", extra_args)
        self.assertNotEqual(result.returncode, 0)

    def test_llm_prompter_api_http_500_scenario(self):
        self.create_test_input_query_file(content="500 query.")
        extra_args = ["--test_mock_api_outcome", "api_http_500"]
        result = self.run_llm_prompter_subprocess("test_http_500_010", extra_args)
        self.assertNotEqual(result.returncode, 0)

    def test_llm_prompter_empty_content_response(self):
        self.create_test_input_query_file(content="Empty content query.")
        extra_args = ["--test_mock_api_outcome", "success", "--test_mock_api_content", ""]
        result = self.run_llm_prompter_subprocess("test_empty_content_011", extra_args)
        self.assertEqual(result.returncode, 0)

    def test_llm_prompter_quiet_mode_success(self):
        self.create_test_input_query_file(content="Quiet success query.")
        extra_args = ["--quiet", "--test_mock_api_outcome", "success", "--test_mock_api_content", "Quiet success."]
        result = self.run_llm_prompter_subprocess("test_quiet_012", extra_args)
        self.assertEqual(result.returncode, 0)

    def test_llm_prompter_interactive_mode_with_paths_warning(self):
        self.create_test_input_query_file()
        extra_args = ["--interactive_test_mode", "--test_mock_api_outcome", "success", "-v"]
        result = self.run_llm_prompter_subprocess("test_interactive_warning_013", extra_args)
        self.assertEqual(result.returncode, 0)

    def test_llm_prompter_no_api_key(self):
        self.create_test_input_query_file()
        env_without_key = os.environ.copy()
        env_without_key["OPENROUTER_API_KEY"] = ""
        import shutil
        shutil.copy(PROJECT_ROOT_TEST / "config.ini", self.test_run_dir)
        result = self.run_llm_prompter_subprocess(
            "test_no_api_key_016", custom_env=env_without_key, cwd_override=self.test_run_dir
        )
        self.assertNotEqual(result.returncode, 0)

    def test_interactive_mode_clears_old_files(self):
        dummy_query = SRC_DIR_TEST / "interactive_test_query.txt"
        dummy_response = SRC_DIR_TEST / "interactive_test_response.txt"
        dummy_query.write_text("dummy query") # Must be non-empty
        dummy_response.touch()
        cmd = [
            sys.executable, str(LLM_PROMPTER_SCRIPT_PATH), "--interactive_test_mode",
            "--test_mock_api_outcome", "success", "--test_mock_api_content", "Cleaned up.", "-v"
        ]
        env_with_key = os.environ.copy()
        env_with_key["OPENROUTER_API_KEY"] = "dummy-key-for-cleanup-test"
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SRC_DIR_TEST), encoding='utf-8', env=env_with_key)
        self.assertEqual(result.returncode, 0, f"STDERR: {result.stderr}")
        for f_path in [dummy_query, dummy_response, SRC_DIR_TEST / "interactive_test_error.txt", SRC_DIR_TEST / "interactive_test_response_full.json"]:
            if os.path.exists(f_path): os.remove(f_path)


class TestLLMPrompterUnit(unittest.TestCase):
    @patch('src.llm_prompter.requests.post')
    def test_call_api_success(self, mock_post):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"id": "test_id"}
        mock_post.return_value = mock_response
        _, duration = llm_prompter.call_openrouter_api("q", "m", "k", "e", "r", 5, "id", quiet=True)
        self.assertGreaterEqual(duration, 0)

    @patch('src.llm_prompter.requests.post', side_effect=requests.exceptions.Timeout)
    def test_call_api_handles_timeout(self, mock_post):
        with self.assertRaises(requests.exceptions.Timeout):
            llm_prompter.call_openrouter_api("q", "m", "k", "e", "r", 5, "id", quiet=True)

    @patch('src.llm_prompter.requests.post')
    def test_call_api_handles_http_error(self, mock_post):
        mock_response = MagicMock(status_code=401, text="Unauthorized")
        http_error = requests.exceptions.HTTPError("401", response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response
        with self.assertRaises(requests.exceptions.HTTPError):
            llm_prompter.call_openrouter_api("q", "m", "k", "e", "r", 5, "id", quiet=True)

    @patch('src.llm_prompter.requests.post', side_effect=ValueError)
    def test_call_api_handles_generic_exception(self, mock_post):
        with self.assertRaises(ValueError):
            llm_prompter.call_openrouter_api("q", "m", "k", "e", "r", 5, "id", quiet=True)


class TestLLMPrompterImportFallbacks(unittest.TestCase):
    def test_import_error_fallback(self):
        # The llm_prompter module is already imported at the top level of the test file.
        # To test the fallback, we reload it within a patched context where 'config_loader' is unavailable.

        # Ensure the real config_loader is available for restoration after the test.
        import config_loader
        original_config_loader = sys.modules.get('config_loader')

        with patch.dict('sys.modules', {'config_loader': None}):
            # Reloading the module re-executes its top-level code.
            # Inside this 'with' block, the import of 'config_loader' will fail, triggering the fallback.
            importlib.reload(llm_prompter)
            self.assertIsInstance(llm_prompter.APP_CONFIG, llm_prompter.DummyConfig)

        # Restore the original state to avoid affecting other tests.
        # Put the real config_loader back into sys.modules.
        if original_config_loader:
            sys.modules['config_loader'] = original_config_loader
        
        # Reload llm_prompter one more time to restore it to its normal state.
        importlib.reload(llm_prompter)


if __name__ == '__main__':
    unittest.main(verbosity=2)
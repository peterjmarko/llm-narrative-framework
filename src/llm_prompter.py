#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/llm_prompter.py

"""
LLM Prompter Worker Script (llm_prompter.py)

Purpose:
This script is the worker responsible for sending a single query to the configured
Large Language Model (LLM) and logging the API call duration. It is called as a
subprocess by `run_llm_sessions.py`.

Workflow (Worker Mode):
1.  Receives a query identifier and paths for I/O, including the absolute path
    for the API timing log file (`--api_log_file`).
2.  Loads API key and LLM parameters.
3.  Reads the query text from the specified input file.
4.  Makes an API call to the LLM provider.
5.  Appends the API call duration to the specified log file.
6.  **On success**:
    a. Writes the full, raw JSON response to `stdout`, wrapped in delimiters.
    b. Extracts the primary text content and writes it to the output response file.
    c. Exits with code 0.
7.  **On failure**:
    a. Writes an error message to the output error file.
    b. Exits with a non-zero code.

Required Arguments for Orchestrated Runs:
    query_identifier        Identifier for this query (e.g., '001').
    --input_query_file      Path to the input query file.
    --output_response_file  Path for the output response file.
    --output_error_file     Path for the output error file.
    --api_log_file          Absolute path to the API timing log file to append to.
"""

# === Start of src/llm_prompter.py ===

import argparse
import os
import sys
import time
import logging
import json
import requests
import threading
import itertools
from dotenv import load_dotenv
from typing import Optional, Dict, List, Tuple, Any

# --- Import from config_loader ---
try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError:
    current_script_dir_lprompter = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir_lprompter not in sys.path:
        sys.path.insert(0, current_script_dir_lprompter)
    try:
        from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
    except ImportError:
        project_root_for_loader_lprompter = os.path.dirname(current_script_dir_lprompter)
        if project_root_for_loader_lprompter not in sys.path:
            sys.path.insert(0, project_root_for_loader_lprompter)
        try:
            from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
        except ImportError as e_lprompter:
            class DummyConfig: # Fallback for tests if config_loader is truly missing
                def has_section(self, section): return False
                def has_option(self, section, key): return False
                def get(self, section, key, fallback=None): return fallback
                def getint(self, section, key, fallback=None): return fallback
                def getfloat(self, section, key, fallback=None): return fallback
                def getboolean(self, section, key, fallback=None): return fallback
            APP_CONFIG = DummyConfig()
            def get_config_value(cfg, section, key, fallback=None, value_type=str): return fallback
            PROJECT_ROOT = os.getcwd() # Best guess
            print(f"WARNING: llm_prompter.py - Could not fully import from config_loader.py. Error: {e_lprompter}. "
                  "Using minimal fallbacks. This might affect functionality if config is essential.")


# --- Default filenames for standalone interactive test mode ---
INTERACTIVE_TEST_QUERY_FILE = "interactive_test_query.txt"
INTERACTIVE_TEST_RESPONSE_FILE = "interactive_test_response.txt"
INTERACTIVE_TEST_ERROR_FILE = "interactive_test_error.txt"
DEFAULT_QUERY_IDENTIFIER_INTERACTIVE = "interactive_test"

# --- Spinner constants ---
SPINNER_FRAMES = ['-', '\\', '|', '/']
SPINNER_INTERVAL = 0.1 
CLEANUP_DELAY = 0.1

# --- Global CONFIG object & Logging Setup ---
DEFAULT_LOG_LEVEL_STR_PROMPTER = get_config_value(APP_CONFIG, 'General', 'default_log_level', fallback='INFO')
numeric_log_level_prompter = getattr(logging, DEFAULT_LOG_LEVEL_STR_PROMPTER.upper(), logging.INFO)
logging.basicConfig(level=numeric_log_level_prompter,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
DOTENV_PATH = ".env"

# Force stdout and stderr to use UTF-8 encoding to prevent UnicodeEncodeError on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# --- Helper: Spinner Animation ---
def animate_spinner(stop_event, query_identifier: str):
    start_time = time.time()
    for c in itertools.cycle(SPINNER_FRAMES):
        if stop_event.is_set(): break
        elapsed = time.time() - start_time
        # Write spinner to stderr to keep stdout clean for data
        sys.stderr.write(f'\r{c} Query {query_identifier}: Waiting for LLM response... ({elapsed:.1f}s)')
        sys.stderr.flush()
        time.sleep(SPINNER_INTERVAL)
    # Clear the spinner line from stderr
    sys.stderr.write('\r' + ' ' * (len(query_identifier) + 60) + '\r')
    sys.stderr.flush()

# --- Helper: LLM API Call ---
# --- Helper: LLM API Call ---
def call_openrouter_api(query_text: str, model_name: str, api_key: str, api_endpoint: str,
                        referer: str, timeout_seconds: int, query_identifier: str,
                        max_tokens: Optional[int] = None, temperature: Optional[float] = None,
                        quiet: bool = False
                       ) -> Tuple[Optional[Dict[str, Any]], float]:

    result_container = {"data": None, "duration": 0.0, "exception": None}

    def _api_worker():
        """This function runs in a separate thread to make the blocking API call."""
        api_start_time = time.time()
        try:
            messages = [{"role": "user", "content": query_text}]
            payload: Dict[str, Any] = {"model": model_name, "messages": messages}
            if max_tokens is not None: payload["max_tokens"] = max_tokens
            if temperature is not None: payload["temperature"] = temperature

            headers = {"Authorization": f"Bearer {api_key}", "HTTP-Referer": referer, "Content-Type": "application/json"}
            logging.debug(f"API Request Payload for Query {query_identifier}: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            
            logging.info(f"  Query {query_identifier}: Calling API with model='{model_name}', "
                         f"max_tokens={payload.get('max_tokens')}, temperature={payload.get('temperature')}")

            response = requests.post(api_endpoint, headers=headers, json=payload, timeout=timeout_seconds)
            response.raise_for_status()
            result_container["data"] = response.json()
            logging.info(f"  Query {query_identifier}: API call successful.")

        except Exception as e:
            # Capture any exception to be re-raised in the main thread
            result_container["exception"] = e
        finally:
            # Always record the duration
            result_container["duration"] = time.time() - api_start_time

    # --- Threading setup ---
    stop_event = threading.Event()
    spinner_thread = threading.Thread(target=animate_spinner, args=(stop_event, query_identifier))
    api_thread = threading.Thread(target=_api_worker, daemon=True)

    # Start threads
    if not quiet:
        spinner_thread.start()
    api_thread.start()

    # --- Interruptible wait loop ---
    # The main thread now waits in this loop, which can be interrupted by Ctrl+C.
    while api_thread.is_alive():
        api_thread.join(timeout=0.1)

    # --- Cleanup and return results ---
    if not quiet:
        stop_event.set()
        if spinner_thread.is_alive():
            spinner_thread.join()
        time.sleep(CLEANUP_DELAY)

    # Handle exceptions that occurred in the worker thread
    if result_container["exception"]:
        exc = result_container["exception"]
        duration = result_container['duration']
        if isinstance(exc, requests.exceptions.Timeout):
            logging.error(f"  Query {query_identifier}: API request timed out after {duration:.2f}s (timeout_setting={timeout_seconds}s).")
        elif isinstance(exc, requests.exceptions.HTTPError):
            logging.error(f"  Query {query_identifier}: API request failed with HTTP error: {exc}")
            if exc.response is not None: logging.error(f"  Response content: {exc.response.text}")
        else:
            logging.exception(f"  Query {query_identifier}: An unexpected error occurred in the API worker thread: {exc}")
        return None, duration

    # Return successful data
    return result_container["data"], result_container["duration"]

def main():
    parser = argparse.ArgumentParser(description="Worker/Standalone Test: Sends a single query to LLM.")
    parser.add_argument("query_identifier", nargs='?', default=DEFAULT_QUERY_IDENTIFIER_INTERACTIVE,
                        help=f"Identifier for this query (e.g., '001'). Default for standalone: '{DEFAULT_QUERY_IDENTIFIER_INTERACTIVE}'.")
    parser.add_argument("--input_query_file", default=None,
                        help=f"Path to the input query file. Default for standalone use only: '{INTERACTIVE_TEST_QUERY_FILE}'.")
    parser.add_argument("--output_response_file", default=None,
                        help=f"Path for the output response file. Default for standalone use only: '{INTERACTIVE_TEST_RESPONSE_FILE}'.")
    parser.add_argument("--output_error_file", default=None,
                        help=f"Path for the output error file. Default for standalone use only: '{INTERACTIVE_TEST_ERROR_FILE}'.")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase verbosity level (-v for INFO, -vv for DEBUG).")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress non-essential info logs and the console spinner.")
    parser.add_argument("--interactive_test_mode", action="store_true",
                        help="Force use of default filenames and create sample query for interactive testing.")
    # Test hook arguments
    parser.add_argument("--test_mock_api_outcome", type=str, default=None,
                        choices=['success', 'api_returns_none', 'api_timeout', 'api_http_401', 'api_http_500'],
                        help="FOR TESTING ONLY: Simulate API outcome instead of making a real call.")
    parser.add_argument("--test_mock_api_content", type=str, default="Default mock content from prompter.",
                        help="FOR TESTING ONLY: String content for a 'success' mock API response.")

    args = parser.parse_args()

    # --- Adjust Log Level FIRST ---
    if args.quiet:
        log_level_str = "WARNING"
    elif args.verbose >= 2:
        log_level_str = "DEBUG"
    elif args.verbose == 1:
        log_level_str = "INFO"
    else:
        log_level_str = DEFAULT_LOG_LEVEL_STR_PROMPTER
    
    numeric_log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    logging.basicConfig(level=numeric_log_level,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        force=True)

    # --- Now continue with the rest of the script ---
    script_dir_worker = os.path.dirname(os.path.abspath(__file__))

    is_worker_provided_paths = (args.input_query_file is not None and
                                args.output_response_file is not None and
                                args.output_error_file is not None)
    run_as_interactive_test = args.interactive_test_mode or not is_worker_provided_paths

    if run_as_interactive_test:
        if is_worker_provided_paths and args.interactive_test_mode:
            logging.warning("--interactive_test_mode flag is set, but specific file paths were also provided. File path arguments will take precedence.")
            input_query_file_abs = os.path.abspath(args.input_query_file)
            output_response_file_abs = os.path.abspath(args.output_response_file)
            output_error_file_abs = os.path.abspath(args.output_error_file)
        else:
            logging.info("Running in standalone interactive test mode with default file names.")
            input_query_file_abs = os.path.join(script_dir_worker, INTERACTIVE_TEST_QUERY_FILE)
            output_response_file_abs = os.path.join(script_dir_worker, INTERACTIVE_TEST_RESPONSE_FILE)
            output_error_file_abs = os.path.join(script_dir_worker, INTERACTIVE_TEST_ERROR_FILE)

            debug_json_filename_default = os.path.splitext(output_response_file_abs)[0] + "_full.json"
            files_to_clear_interactive = [output_response_file_abs, output_error_file_abs, debug_json_filename_default]
            for f_path in files_to_clear_interactive:
                if os.path.exists(f_path):
                    try: os.remove(f_path); logging.info(f"  Interactive mode: Cleared old file: {os.path.basename(f_path)}")
                    except OSError as e: logging.warning(f"  Interactive mode: Could not clear old file {os.path.basename(f_path)}: {e}")

            if not os.path.exists(input_query_file_abs):
                try:
                    with open(input_query_file_abs, 'w', encoding='utf-8') as f_iq:
                        f_iq.write("This is an interactive test query.\nWhat is the capital of the Moon?")
                    logging.info(f"Created sample query file: {input_query_file_abs}")
                except IOError as e: logging.error(f"Error creating sample query file {input_query_file_abs}: {e}"); sys.exit(1)
    else:
        logging.info("Running in worker mode (paths provided by orchestrator or user).")
        input_query_file_abs = os.path.abspath(args.input_query_file)
        output_response_file_abs = os.path.abspath(args.output_response_file)
        output_error_file_abs = os.path.abspath(args.output_error_file)
    
    logging.info(f"LLM Prompter for ID '{args.query_identifier}' started. Log level: {log_level_str}")
    logging.info(f"  Input query file: {input_query_file_abs}")
    logging.info(f"  Output response file: {output_response_file_abs}")
    logging.info(f"  Output error file: {output_error_file_abs}")

    # Load .env
    dotenv_paths_to_try = [
        os.path.join(script_dir_worker, DOTENV_PATH), # Alongside script
        os.path.join(os.getcwd(), DOTENV_PATH)        # In CWD
    ]
    if 'PROJECT_ROOT' in globals() and PROJECT_ROOT:
        dotenv_paths_to_try.insert(0, os.path.join(PROJECT_ROOT, DOTENV_PATH))

    env_loaded_path = None
    for d_path in dotenv_paths_to_try:
        if os.path.exists(d_path) and load_dotenv(d_path):
            env_loaded_path = d_path
            break
    if env_loaded_path:
        logging.info(f"LLM Prompter: Loaded .env from: {env_loaded_path}")
    else:
        logging.warning("LLM Prompter: .env file not found in typical locations. API key must be in environment.")

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logging.error("LLM Prompter: OPENROUTER_API_KEY not found.")
        with open(output_error_file_abs, 'w', encoding='utf-8') as f_err: f_err.write("OPENROUTER_API_KEY not set.")
        sys.exit(1)
    logging.info("LLM Prompter: OPENROUTER_API_KEY loaded.")

    # Get LLM parameters from config
    model_name_cfg = get_config_value(APP_CONFIG, 'LLM', 'model_name', fallback="google/gemini-1.5-pro-latest")
    api_endpoint_cfg = get_config_value(APP_CONFIG, 'LLM', 'api_endpoint', fallback='https://openrouter.ai/api/v1/chat/completions')
    api_timeout_cfg = get_config_value(APP_CONFIG, 'LLM', 'api_timeout_seconds', fallback=120, value_type=int)
    referer_header_cfg = get_config_value(APP_CONFIG, 'LLM', 'referer_header', fallback="http://localhost:3000")
    max_tokens_cfg = get_config_value(APP_CONFIG, 'LLM', 'max_tokens', fallback=1000, value_type=int)
    temperature_cfg = get_config_value(APP_CONFIG, 'LLM', 'temperature', fallback=None, value_type=float)

    try:
        if not os.path.exists(input_query_file_abs):
            raise FileNotFoundError(f"Input query file not found: {input_query_file_abs}")

        with open(input_query_file_abs, 'r', encoding='utf-8') as f_query:
            query_text_content = f_query.read()

        if not query_text_content.strip():
            logging.warning(f"  Query file '{os.path.basename(input_query_file_abs)}' is empty.")
            with open(output_error_file_abs, 'w', encoding='utf-8') as f_err: f_err.write("Query file was empty.")
            sys.exit(1)

        raw_llm_response_json = None
        if args.test_mock_api_outcome:
            logging.warning(f"!!! RUNNING IN API MOCK MODE: {args.test_mock_api_outcome} FOR QUERY {args.query_identifier} !!!")
            if args.test_mock_api_outcome == 'success':
                raw_llm_response_json = {"choices": [{"message": {"content": args.test_mock_api_content}}]}
            logging.info(f"  MOCK API: Outcome for query {args.query_identifier} set to '{args.test_mock_api_outcome}'.")
        else:
            raw_llm_response_json, _ = call_openrouter_api(
                query_text=query_text_content, model_name=model_name_cfg,
                api_key=api_key, api_endpoint=api_endpoint_cfg,
                referer=referer_header_cfg, timeout_seconds=api_timeout_cfg,
                query_identifier=args.query_identifier,
                max_tokens=max_tokens_cfg, temperature=temperature_cfg,
                quiet=args.quiet
            )

        if raw_llm_response_json:
            sys.stdout.write("---LLM_RESPONSE_JSON_START---\n")
            json.dump(raw_llm_response_json, sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n---LLM_RESPONSE_JSON_END---\n")
            sys.stdout.flush()

            response_content_to_save = ""
            try:
                if isinstance(raw_llm_response_json.get('choices'), list) and raw_llm_response_json['choices']:
                    message = raw_llm_response_json['choices'][0].get('message', {})
                    response_content_to_save = message.get('content', '')
                if not response_content_to_save.strip():
                     # Downgraded from WARNING to INFO, so it will be hidden in quiet mode.
                     logging.info("  LLM Prompter: Response content is empty or whitespace.")
            except Exception as e_parse:
                # This is a more serious parsing error, so it remains a WARNING.
                logging.warning(f"  LLM Prompter: Error extracting message content from LLM JSON: {e_parse}. Saving empty response.")

            with open(output_response_file_abs, 'w', encoding='utf-8') as f_response:
                f_response.write(response_content_to_save)

            logging.info(f"  LLM Prompter: Success. Wrote response to '{os.path.basename(output_response_file_abs)}'.")
            sys.exit(0)
        else:
            logging.error(f"  LLM Prompter: LLM call failed for '{os.path.basename(input_query_file_abs)}'. No response data.")
            with open(output_error_file_abs, 'w', encoding='utf-8') as f_err:
                f_err.write("LLM API call returned None or failed (see worker log).")
            sys.exit(1)

    except FileNotFoundError as e_fnf:
        logging.error(f"  LLM Prompter: File error: {e_fnf}")
        err_file_path = args.output_error_file if args.output_error_file else os.path.join(script_dir_worker, INTERACTIVE_TEST_ERROR_FILE)
        with open(os.path.abspath(err_file_path), 'w', encoding='utf-8') as f_err: f_err.write(str(e_fnf))
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("\nLLM Prompter: Interrupted by user (Ctrl+C).")
        err_file_path = args.output_error_file if args.output_error_file else os.path.join(script_dir_worker, INTERACTIVE_TEST_ERROR_FILE)
        with open(os.path.abspath(err_file_path), 'w', encoding='utf-8') as f_err: f_err.write("Processing interrupted by user (Ctrl+C).")
        sys.exit(1)
    except Exception as e:
        logging.exception(f"  LLM Prompter: Unhandled error processing query {args.query_identifier}: {e}")
        err_file_path = args.output_error_file if args.output_error_file else os.path.join(script_dir_worker, INTERACTIVE_TEST_ERROR_FILE)
        with open(os.path.abspath(err_file_path), 'w', encoding='utf-8') as f_err: f_err.write(f"Unhandled error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
    
# === End of src/llm_prompter.py ===
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
# Filename: src/experiment_manager.py

"""
Backend State-Machine Controller for a Single Experiment.

This script is the high-level, intelligent backend controller for managing the
entire lifecycle of a single experiment. It is invoked by user-facing
PowerShell wrappers (e.g., `new_experiment.ps1`, `repair_experiment.ps1`).

It operates as a state machine: when pointed at an experiment directory, it
verifies the experiment's status and automatically takes the correct action
(`REPAIR`, `REPROCESS`, or `MIGRATE`) until the experiment is fully complete.
If invoked without a target directory, it creates a new one and runs the
experiment from scratch.

Its core function is to orchestrate `orchestrate_replication.py` to create or
repair individual replication runs. Once all replications are valid, it performs
a finalization step by calling `compile_experiment_results.py` to generate the
top-level summary CSV for the experiment.

It supports several modes:
- **Default (State Machine)**: Intelligently ensures an experiment reaches completion.
- **`--reprocess`**: Forces a full re-processing of all analysis artifacts.
- **`--migrate`**: Transforms a legacy experiment into the modern format.
- **`--verify-only`**: Performs a read-only audit and prints a detailed report.

User-facing usage examples are provided in the main project `DOCUMENTATION.md`.
"""

import sys
import os
import subprocess
import logging
import glob
import time
import datetime
import argparse
import json
import re
import shutil
import configparser
from configparser import ConfigParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path

# tqdm is a library that provides a clean progress bar.
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs): return iterable

def _prompt_for_confirmation(prompt_text: str) -> bool:
    """Prompts the user for a Y/N confirmation and loops until valid input is received."""
    while True:
        choice = input(prompt_text).strip().lower()
        if choice == 'y':
            return True
        if choice == 'n':
            return False
        # If input is invalid, the loop continues, effectively re-prompting.

def _format_header(message, total_width=80):
    """Formats a message into a symmetrical header line with ### bookends."""
    prefix = "###"
    suffix = "###"
    # Center the message with a space on each side within the available space.
    content = f" {message} ".center(total_width - len(prefix) - len(suffix), ' ')
    return f"{prefix}{content}{suffix}"

def _create_new_experiment_directory(colors):
    """Generates a unique name and creates a new experiment directory."""
    C_CYAN = colors['cyan']
    C_RESET = colors['reset']
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    base_output = get_config_value(APP_CONFIG, 'General', 'base_output_dir', fallback='output')
    new_exp_subdir = get_config_value(APP_CONFIG, 'General', 'new_experiments_subdir', fallback='new_experiments')
    exp_prefix = get_config_value(APP_CONFIG, 'General', 'experiment_dir_prefix', fallback='experiment_')
    base_path = os.path.join(PROJECT_ROOT, base_output, new_exp_subdir)
    final_output_dir = os.path.join(base_path, f"{exp_prefix}{timestamp}")
    
    os.makedirs(final_output_dir)
    # This message is now clearer for the new_experiment.ps1 workflow.
    relative_path = os.path.relpath(final_output_dir, PROJECT_ROOT)
    print(f"{C_CYAN}New experiment directory created:\n{relative_path}{C_RESET}\n")
    
    return final_output_dir

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError as e:
    print(f"FATAL: Could not import config_loader.py. Error: {e}", file=sys.stderr)
    sys.exit(1)

# Audit exit codes for --verify-only mode and internal signals
AUDIT_ALL_VALID = 0
AUDIT_NEEDS_REPROCESS = 1 # Replications have analysis issues
AUDIT_NEEDS_REPAIR = 2      # Replications have data issues (query/response)
AUDIT_NEEDS_MIGRATION = 3   # Experiment is legacy format
AUDIT_NEEDS_AGGREGATION = 4 # Replications are valid, but experiment summary is not
AUDIT_ABORTED_BY_USER = 99  # Specific exit code when user aborts via prompt

#==============================================================================
#   CENTRAL FILE MANIFEST & REPORT CRITERIA
#==============================================================================
FILE_MANIFEST = {
    "config": {
        "path": "config.ini.archived",
        "type": "config_file",
        "required_keys": {
            # canonical_name: [(section, key), (fallback_section, fallback_key), ...]
            "model_name": [("LLM", "model_name"), ("LLM", "model")],
            "temperature": [("LLM", "temperature")],
            "mapping_strategy": [("Study", "mapping_strategy")],
            "num_subjects": [("Study", "group_size"), ("Study", "k_per_query")],
            "num_trials": [("Study", "num_trials"), ("Study", "num_iterations")],
            "personalities_db_path": [("Filenames", "personalities_src")],
        },
    },
    "queries_dir":   {"path": "session_queries"},
    "query_files":   {"path": "session_queries/llm_query_*.txt", "pattern": r"llm_query_(\d+)\.txt"},
    "trial_manifests": {"path": "session_queries/llm_query_*_manifest.txt", "pattern": r"llm_query_(\d+)_manifest\.txt"},
    "aggregated_mappings_file": {"path": "session_queries/mappings.txt"},
    "responses_dir": {"path": "session_responses"},
    "response_files":{"path": "session_responses/llm_response_*.txt", "pattern": r"llm_response_(\d+)\.txt"},
    "response_json_files": {"path": "session_responses/llm_response_*_full.json", "pattern": r"llm_response_(\d+)_full\.json"},
    "analysis_dir":  {"path": "analysis_inputs"},
    "scores_file":   {"path": "analysis_inputs/all_scores.txt"},
    "mappings_file": {"path": "analysis_inputs/all_mappings.txt"},
    "replication_report": {"pattern": r"replication_report_\d{4}-\d{2}-\d{2}.*\.txt"},
}

REPORT_REQUIRED_METRICS = {
    "n_valid_responses", "mwu_stouffer_z", "mwu_stouffer_p", "mwu_fisher_chi2",
    "mwu_fisher_p", "mean_effect_size_r", "effect_size_r_p", "mean_mrr",
    "mrr_p", "mean_top_1_acc", "top_1_acc_p", "mean_top_3_acc",
    "top_3_acc_p", "mean_rank_of_correct_id", "rank_of_correct_id_p",
    "bias_slope", "bias_intercept", "bias_r_value", "bias_p_value", "bias_std_err",
    "mean_mrr_lift", "mean_top_1_acc_lift", "mean_top_3_acc_lift"
}

# Define required nested dictionaries and the keys they must contain
REPORT_REQUIRED_NESTED_KEYS = {
    "positional_bias_metrics": {"top1_pred_bias_std", "true_false_score_diff"}
}

# --- Verification Helper Functions ---

def _get_file_indices(run_path: Path, spec: dict) -> set[int]:
    """Extracts the numerical indices from a set of files using regex."""
    indices = set()
    regex = re.compile(spec["pattern"])
    files = run_path.glob(spec["path"])
    for f in files:
        match = regex.match(os.path.basename(f))
        if match:
            indices.add(int(match.group(1)))
    return indices

def _count_lines_in_file(filepath: str, skip_header: bool = True) -> int:
    """Counts data lines in a file, optionally skipping a header."""
    if not os.path.exists(filepath):
        return 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        start_index = 1 if skip_header and lines else 0
        return len([line for line in lines[start_index:] if line.strip()])
    except Exception:
        return 0

def _count_matrices_in_file(filepath: str, k: int) -> int:
    """Counts how many k x k matrices are in a file."""
    if not os.path.exists(filepath) or k <= 0:
        return 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line for line in f.read().splitlines() if line.strip()]
        return len(lines) // k
    except Exception:
        return 0

# ------------------------------------------------------------------ helpers
def _check_config_manifest(run_path: Path, k_expected: int, m_expected: int):
    cfg_path = run_path / FILE_MANIFEST["config"]["path"]
    required_keys_map = FILE_MANIFEST["config"]["required_keys"]

    try:
        cfg = ConfigParser()
        # Use a `with open` block to ensure the file handle is always closed, preventing file locks.
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg.read_file(f)
        if not cfg.sections():
            return "CONFIG_MALFORMED"
    except Exception:
        return "CONFIG_MALFORMED"

    # Generic function to find a key's value using the fallback map
    def _get_value(canonical_name, value_type=str):
        for section, key in required_keys_map[canonical_name]:
            if cfg.has_option(section, key):
                try:
                    if value_type is int:
                        return cfg.getint(section, key)
                    if value_type is float:
                        return cfg.getfloat(section, key)
                    return cfg.get(section, key)
                except (configparser.Error, ValueError):
                    continue  # Try next fallback
        return None

    # Check for presence of all required keys
    missing_keys = [name for name in required_keys_map if _get_value(name) is None]
    if missing_keys:
        return f"CONFIG_MISSING_KEYS: {', '.join(missing_keys)}"

    # Validate k and m values against directory name
    k_cfg = _get_value("num_subjects", value_type=int)
    m_cfg = _get_value("num_trials", value_type=int)

    mismatched = []
    if k_cfg != k_expected:
        mismatched.append(f"k (expected {k_expected}, found {k_cfg})")
    if m_cfg != m_expected:
        mismatched.append(f"m (expected {m_expected}, found {m_cfg})")

    if mismatched:
        return f"CONFIG_MISMATCH: {', '.join(mismatched)}"

    return "VALID"

def _check_file_set(run_path: Path, spec: dict, expected_count: int):
    glob_pattern = spec["path"]
    regex_pattern = spec.get("pattern")

    all_files_in_dir = list(run_path.glob(glob_pattern))

    # If a specific regex pattern is provided, filter the glob results for a more precise count.
    if regex_pattern:
        regex = re.compile(regex_pattern)
        actual = [f for f in all_files_in_dir if regex.match(os.path.basename(f))]
    else:
        # If no regex is provided, use the glob results directly.
        actual = all_files_in_dir

    label = glob_pattern.split("/", 1)[0]  # e.g. session_queries
    if not actual:
        return f"{label.upper()}_MISSING"

    count = len(actual)
    if count < expected_count:
        return f"{label.upper()}_INCOMPLETE"
    if count > expected_count:
        return f"{label.upper()}_TOO_MANY"
    return "VALID"


def _check_analysis_files(run_path: Path, expected_entries: int, k_value: int):
    scores_p = run_path / FILE_MANIFEST["scores_file"]["path"]
    mappings_p = run_path / FILE_MANIFEST["mappings_file"]["path"]
    for p in (scores_p, mappings_p):
        if not p.exists():
            return "ANALYSIS_FILES_MISSING"
    try:
        # Mappings are simple line-delimited files; we assume a potential header.
        n_mappings = _count_lines_in_file(mappings_p, skip_header=True)
        # The number of score matrices depends on 'k' (group size).
        n_scores = _count_matrices_in_file(scores_p, k_value)
    except Exception:
        return "ANALYSIS_DATA_MALFORMED"
    if n_scores != expected_entries or n_mappings != expected_entries:
        return "ANALYSIS_DATA_INCOMPLETE"
    return "VALID"


def _check_report(run_path: Path):
    reports = sorted(run_path.glob("replication_report_*.txt"))
    if not reports:
        return "REPORT_MISSING"
    latest = reports[-1]
    try:
        text = latest.read_text(encoding="utf-8")
    except Exception:
        return "REPORT_MALFORMED"
    if "<<<METRICS_JSON_START>>>" not in text or "<<<METRICS_JSON_END>>>" not in text:
        return "REPORT_MALFORMED"
    try:
        start = text.index("<<<METRICS_JSON_START>>>")
        end = text.index("<<<METRICS_JSON_END>>>")
        j = json.loads(text[start + len("<<<METRICS_JSON_START>>>"):end])
    except Exception:
        return "REPORT_MALFORMED"

    # Check for required top-level metric keys
    missing_metrics = REPORT_REQUIRED_METRICS - j.keys()
    if missing_metrics:
        return f"REPORT_INCOMPLETE_METRICS: {', '.join(sorted(missing_metrics))}"

    # Check for required nested dictionaries and their internal keys
    for nested_key, required_sub_keys in REPORT_REQUIRED_NESTED_KEYS.items():
        nested_dict = j.get(nested_key)
        if not isinstance(nested_dict, dict):
            return f"REPORT_MISSING_NESTED_DICT: {nested_key}"

        missing_sub_keys = required_sub_keys - nested_dict.keys()
        if missing_sub_keys:
            return f"REPORT_INCOMPLETE_NESTED_KEYS ({nested_key}): {', '.join(sorted(missing_sub_keys))}"

    return "VALID"

def _verify_single_run_completeness(run_path: Path) -> tuple[str, list[str]]:
    status_details = []

    # 1. name validity
    # This regex now correctly handles the new format without a trailing '$' to allow for the new parts.
    name_match = re.search(r"sbj-(\d+)_trl-(\d+)", run_path.name)
    if not run_path.name.startswith("run_") or not name_match:
        status_details = [f"{run_path.name} does not match required run_*_sbj-NN_trl-NNN* pattern"]
        return "INVALID_NAME", status_details
    k_expected, m_expected = int(name_match.group(1)), int(name_match.group(2))

    # 2. config
    stat_cfg = _check_config_manifest(run_path, k_expected, m_expected)
    if stat_cfg != "VALID":
        status_details.append(stat_cfg)
    else:
        status_details.append("config OK")

    # 3. queries
    stat_q = _check_file_set(run_path, FILE_MANIFEST["query_files"], m_expected)
    if stat_q != "VALID":
        status_details.append(stat_q)
    else:
        status_details.append("queries OK")

    # 4. Check for mappings file and optional trial manifests
    aggregated_mappings_path = run_path / FILE_MANIFEST["aggregated_mappings_file"]["path"]
    if not aggregated_mappings_path.exists():
        status_details.append("AGGREGATED_MAPPINGS_MISSING")

    # Conditionally check for trial manifests, as they may not exist in legacy runs.
    # First, do a quick check to see if ANY manifest files are present.
    manifest_spec = FILE_MANIFEST["trial_manifests"]
    if list(run_path.glob(manifest_spec["path"])):
        # If manifests are found, then perform the full, strict check for completeness.
        stat_q_manifests = _check_file_set(run_path, manifest_spec, m_expected)
        if stat_q_manifests != "VALID":
            status_details.append("MANIFESTS_INCOMPLETE")

    # 5. Check response files
    expected_responses = m_expected
    response_details = []

    # Check file counts first
    stat_r_txt = _check_file_set(run_path, FILE_MANIFEST["response_files"], expected_responses)
    stat_r_json = _check_file_set(run_path, FILE_MANIFEST["response_json_files"], expected_responses)

    if stat_r_txt != "VALID":
        response_details.append(f"TXT: {stat_r_txt}")
    if stat_r_json != "VALID":
        response_details.append(f"JSON: {stat_r_json}")

    # If counts seem okay, perform a deeper check for index consistency
    if not response_details:
        query_indices = _get_file_indices(run_path, FILE_MANIFEST["query_files"])
        response_txt_indices = _get_file_indices(run_path, FILE_MANIFEST["response_files"])
        response_json_indices = _get_file_indices(run_path, FILE_MANIFEST["response_json_files"])
        
        mismatches = []
        if query_indices != response_txt_indices:
            mismatches.append("txt")
        if query_indices != response_json_indices:
            mismatches.append("json")
        
        if mismatches:
            response_details.append(f"QUERY_RESPONSE_INDEX_MISMATCH ({','.join(mismatches)})")

    if response_details:
        # Consolidate all response issues into a single failure string
        status_details.append(f"SESSION_RESPONSES_ISSUE: {'; '.join(response_details)}")
    else:
        status_details.append("responses OK")

    # 6. Consolidated Analysis, Report, and Summary Check
    # Any failure in these downstream artifacts is considered a single, non-critical ANALYSIS_ISSUE.
    analysis_ok = True
    
    # First, check the final replication summary. If it's missing, it's an analysis issue.
    if not (run_path / "REPLICATION_results.csv").exists():
        status_details.append("REPLICATION_RESULTS_MISSING")
        analysis_ok = False
    
    # Second, check the report. A missing or malformed report is also an analysis issue.
    stat_rep = _check_report(run_path)
    if stat_rep != "VALID":
        status_details.append(stat_rep)
        analysis_ok = False

    # Third, check the intermediate analysis files, but only if the other checks haven't failed.
    # This prevents error-masking and double-counting.
    if analysis_ok:
        try:
            latest_report = sorted(run_path.glob("replication_report_*.txt"))[-1]
            text = latest_report.read_text(encoding="utf-8")
            start = text.index("<<<METRICS_JSON_START>>>")
            end = text.index("<<<METRICS_JSON_END>>>")
            j = json.loads(text[start + len("<<<METRICS_JSON_START>>>"):end])
            expected_entries = j.get("n_valid_responses")

            if expected_entries is not None and expected_entries >= 0:
                stat_a = _check_analysis_files(run_path, expected_entries, k_expected)
                if stat_a != "VALID":
                    status_details.append(stat_a)
                    analysis_ok = False
            else:
                status_details.append("ANALYSIS_SKIPPED_BAD_REPORT")
                analysis_ok = False
        except (IndexError, ValueError, KeyError):
            status_details.append("ANALYSIS_SKIPPED_BAD_REPORT")
            analysis_ok = False

    if analysis_ok:
        status_details.append("analysis OK")

    # --- Roll-up Logic: Classify based on the number of issues found ---
    failures = [d for d in status_details if not d.endswith(" OK")]
    num_failures = len(failures)

    if num_failures == 0:
        return "VALIDATED", status_details
    
    # If there are 2 or more distinct failures, the run is considered corrupted.
    if num_failures >= 2:
        return "RUN_CORRUPTED", status_details

    # --- If there is exactly one failure, classify it for targeted repair ---
    failure = failures[0]
    if "INVALID_NAME" in failure:
        return "INVALID_NAME", status_details
    if "CONFIG" in failure:
        return "CONFIG_ISSUE", status_details
    if any(err in failure for err in ["SESSION_QUERIES", "MAPPINGS_MISSING", "MANIFESTS_INCOMPLETE"]):
        return "QUERY_ISSUE", status_details
    if any(err in failure for err in ["SESSION_RESPONSES", "QUERY_RESPONSE_INDEX_MISMATCH"]):
        return "RESPONSE_ISSUE", status_details
    
    # Any other single, non-fatal issue is a less severe ANALYSIS_ISSUE.
    return "ANALYSIS_ISSUE", status_details

def _get_experiment_state(target_dir: Path, expected_reps: int, verbose=False) -> tuple[str, list, dict]:
    """
    High-level state machine driver with correct state priority.

    Returns:
        A tuple containing:
        - str: The high-level state of the experiment (e.g., "REPAIR_NEEDED").
        - list: The detailed payload for the action (e.g., list of failed runs).
        - dict: A granular map of {run_name: (status, details)} for every run.
    """
    run_dirs = sorted([p for p in target_dir.glob("run_*") if p.is_dir()])
    
    # Handle the brand-new experiment case first.
    if not run_dirs:
        return "NEW_NEEDED", [], {}

    run_paths_by_name = {p.name: p for p in run_dirs}
    granular = {p.name: _verify_single_run_completeness(p) for p in run_dirs}
    fails = {n: (s, d) for n, (s, d) in granular.items() if s != "VALIDATED"}

    # --- State Priority 1: REPAIR_NEEDED ---
    # Check for critical issues that require re-running parts of the pipeline.
    runs_needing_session_repair = []
    runs_needing_full_replication_repair = []
    for run_name, (status, details_list) in fails.items():
        if status == "RESPONSE_ISSUE":
            run_path = run_paths_by_name[run_name]
            query_indices = _get_file_indices(run_path, FILE_MANIFEST["query_files"])
            
            # Check for missing indices from both .txt and .json response files
            response_txt_indices = _get_file_indices(run_path, FILE_MANIFEST["response_files"])
            response_json_indices = _get_file_indices(run_path, FILE_MANIFEST["response_json_files"])

            # A failed index is any query index that is missing either its .txt or .json response
            failed_txt_indices = query_indices - response_txt_indices
            failed_json_indices = query_indices - response_json_indices
            
            # Combine them into a single set of unique failed indices
            failed_indices = sorted(list(failed_txt_indices.union(failed_json_indices)))

            if failed_indices:
                runs_needing_session_repair.append({"dir": str(run_path), "failed_indices": failed_indices, "repair_type": "session_repair"})
        elif status == "CONFIG_ISSUE":
            # This is now a distinct, less destructive repair type.
            run_path = run_paths_by_name[run_name] # Correctly get the path using the run's name
            runs_needing_session_repair.append({"dir": str(run_path), "repair_type": "config_repair"})
        elif status in {"QUERY_ISSUE", "INVALID_NAME"}:
            runs_needing_full_replication_repair.append({"dir": str(run_paths_by_name[run_name]), "repair_type": "full_replication_repair"})

    if runs_needing_full_replication_repair:
        return "REPAIR_NEEDED", runs_needing_full_replication_repair, granular
    if runs_needing_session_repair:
        return "REPAIR_NEEDED", runs_needing_session_repair, granular

    # --- State Priority 2: REPROCESS_NEEDED ---
    # If no critical repairs are needed, check for analysis issues.
    if any(status == "ANALYSIS_ISSUE" for status, _ in fails.values()):
        analysis_fails = [
            {"dir": str(run_paths_by_name[name])}
            for name, (status, _) in fails.items()
            if status == "ANALYSIS_ISSUE"
        ]
        return "REPROCESS_NEEDED", analysis_fails, granular

    # --- State Priority 3: NEW_NEEDED ---
    # If all existing runs are valid but there are not enough of them.
    if not fails and len(run_dirs) < expected_reps:
        return "NEW_NEEDED", [], granular

    # --- State Priority 4: COMPLETE ---
    # If all existing runs are valid and the count is correct.
    if not fails and len(run_dirs) >= expected_reps:
        return "COMPLETE", [], granular
        
    # Fallback for any unhandled state.
    return "UNKNOWN", [], granular

# --- Mode Execution Functions ---

def _verify_experiment_level_files(target_dir: Path) -> tuple[bool, list[str]]:
    """Checks for top-level summary files for the entire experiment."""
    is_complete = True
    details = []
    
    # These consolidated summary files should exist in the experiment's root directory.
    required_files = [
        "batch_run_log.csv",
        "EXPERIMENT_results.csv"
    ]

    for filename in required_files:
        if not (target_dir / filename).exists():
            is_complete = False
            details.append(f"MISSING: {filename}")

    # Check if the batch log is finalized (contains a summary line)
    log_path = target_dir / "batch_run_log.csv"
    if log_path.exists():
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if "BatchSummary" not in content:
                is_complete = False
                details.append("batch_run_log.csv NOT FINALIZED")
        except Exception:
            is_complete = False
            details.append("batch_run_log.csv UNREADABLE")

    return is_complete, details

def _run_verify_only_mode(target_dir: Path, expected_reps: int, colors, suppress_exit: bool = False, print_report: bool = True, is_verify_only_cli: bool = False, non_interactive: bool = False, quiet_mode: bool = False) -> int:
    """
    Runs a read-only verification and prints a detailed summary table.

    Args:
        ...
        non_interactive (bool): If True, suppresses the main "Running Experiment Audit"
            header and the final recommendation text. Used when the audit is
            called from a wrapper script that provides its own context.
        ...
    Returns:
        int: An audit exit code (AUDIT_ALL_VALID, AUDIT_NEEDS_REPROCESS, etc.).
    """
    C_CYAN, C_GREEN, C_YELLOW, C_RED, C_RESET = colors.values()
    if print_report and not quiet_mode:
        relative_path = os.path.relpath(target_dir, PROJECT_ROOT)
        # In non-interactive mode, the wrapper script provides its own header.
        if not non_interactive:
            print(f"\n{C_CYAN}{'#'*80}{C_RESET}")
            print(f"{C_CYAN}{_format_header('Running Experiment Audit')}{C_RESET}")
            print(f"{C_CYAN}{'#'*80}{C_RESET}")
        print(f"\n--- Verifying Data Completeness in: ---")
        print(f"{relative_path}")
    run_dirs = sorted([p for p in glob.glob(os.path.join(target_dir, 'run_*')) if os.path.isdir(p)])

    audit_result_code = AUDIT_ALL_VALID # Default to valid

    if not run_dirs:
        if print_report:
            print(f"\n{C_YELLOW}Diagnosis: No 'run_*' directories found.{C_RESET}")
            print("This indicates an empty or critically malformed experiment.")
        audit_result_code = AUDIT_NEEDS_MIGRATION
    else:
        all_runs_data = []
        total_expected_trials = 0
        total_valid_responses = 0
        total_complete_runs = 0

        for run_dir_path in run_dirs:
            run_dir = Path(run_dir_path)
            status, details = _verify_single_run_completeness(run_dir)

            if status == "VALIDATED":
                total_complete_runs += 1

            # Get total expected trials and actual valid responses for the summary
            try:
                # Total possible trials is still derived from the folder name
                name_match = re.search(r"_trl-(\d+)", run_dir.name)
                if name_match:
                    total_expected_trials += int(name_match.group(1))
                
                # Actual valid responses comes from the JSON report, but ONLY if the run is fully validated.
                n_valid_in_run = 0
                if status == "VALIDATED":
                    try:
                        latest_report = sorted(run_dir.glob("replication_report_*.txt"))[-1]
                        text = latest_report.read_text(encoding="utf-8")
                        start = text.index("<<<METRICS_JSON_START>>>")
                        end = text.index("<<<METRICS_JSON_END>>>")
                        j = json.loads(text[start + len("<<<METRICS_JSON_START>>>"):end])
                        n_valid_in_run = j.get("n_valid_responses", 0)
                    except (IndexError, ValueError, KeyError):
                        n_valid_in_run = 0 # Don't trust the report if it's malformed
                
                total_valid_responses += n_valid_in_run
                
            except (AttributeError, ValueError, IndexError, json.JSONDecodeError):
                # If anything goes wrong (bad name, no report, bad JSON),
                # we just skip adding to the totals for this run.
                pass

            all_runs_data.append({
                "name": run_dir.name,
                "status": status,
                "details": "; ".join(details)
            })

        if print_report:
            # Set a max width for the directory name column to keep the table compact
            MAX_NAME_WIDTH = 40
            max_name_len = min(max(len(run['name']) for run in all_runs_data), MAX_NAME_WIDTH) if all_runs_data else 20

            print(f"\n{'Run Directory':<{max_name_len}} {'Status':<20} {'Details'}")
            print(f"{'-'*max_name_len} {'-'*20} {'-'*45}")
            for run in all_runs_data:
                display_name = run['name']
                if len(display_name) > max_name_len:
                    display_name = display_name[:max_name_len - 3] + "..."

                status_color = C_GREEN if run['status'] == "VALIDATED" else C_RED
                print(f"{display_name:<{max_name_len}} {status_color}{run['status']:<20}{C_RESET} {run['details']}")

        # --- Determine result code based on findings from individual runs ---
        unique_run_statuses = {run['status'] for run in all_runs_data}

        # Rule 1: If any run is corrupted (multiple errors in one), it's a migration.
        if "RUN_CORRUPTED" in unique_run_statuses:
            audit_result_code = AUDIT_NEEDS_MIGRATION
        else:
            # Rule 2: If there are multiple *types* of critical single errors across
            # different runs, it's also a migration (indicates systemic issue).
            critical_error_types = {"INVALID_NAME", "CONFIG_ISSUE", "QUERY_ISSUE", "RESPONSE_ISSUE"}
            found_critical_types = unique_run_statuses.intersection(critical_error_types)

            if len(found_critical_types) > 1:
                audit_result_code = AUDIT_NEEDS_MIGRATION
            elif len(found_critical_types) == 1:
                # Only one type of critical error exists, which is safe to repair.
                audit_result_code = AUDIT_NEEDS_REPAIR
            elif "ANALYSIS_ISSUE" in unique_run_statuses:
                # No critical errors, but analysis issues exist.
                audit_result_code = AUDIT_NEEDS_REPROCESS
            else:
                # No critical or analysis errors found in any run.
                audit_result_code = AUDIT_ALL_VALID

        # --- Now check for experiment-level summary files ---
        exp_complete, exp_details = _verify_experiment_level_files(Path(target_dir))

        # --- Downgrade status if replications are valid but experiment is not finalized ---
        if audit_result_code == AUDIT_ALL_VALID and not exp_complete:
            # This state means the replications are fine, but the final aggregation step
            # is missing. This requires a targeted aggregation, not a full reprocess.
            audit_result_code = AUDIT_NEEDS_AGGREGATION

        # --- Determine final messages and colors based on the combined state ---
        exp_status_str_base = "COMPLETE" if exp_complete else "INCOMPLETE"
        exp_status_suffix = ""
        
        if exp_complete:
            exp_status_color = C_GREEN
            if audit_result_code == AUDIT_NEEDS_REPROCESS:
                exp_status_color = C_YELLOW
                exp_status_suffix = " (Outdated)"
        elif audit_result_code == AUDIT_NEEDS_REPROCESS or audit_result_code == AUDIT_NEEDS_AGGREGATION:
            # Covers cases that need an update or just finalization.
            exp_status_color = C_YELLOW
        else:
            # Covers repair needed or other critical errors.
            exp_status_color = C_RED

        # Determine the final audit message and recommendation
        if audit_result_code == AUDIT_NEEDS_MIGRATION:
            audit_message = "Audit Result: Experiment needs MIGRATION."
            audit_recommendation = "Recommendation: Proceed with migration to create an upgraded copy."
            audit_color = C_RED
        elif audit_result_code == AUDIT_NEEDS_REPAIR:
            audit_message = "Audit Result: Experiment needs REPAIR."
            audit_recommendation = "Recommendation: Run `repair_experiment.ps1` to fix the experiment."
            audit_color = C_RED
        elif audit_result_code == AUDIT_NEEDS_REPROCESS:
            audit_message = "Audit Result: Experiment needs UPDATE."
            audit_recommendation = "Recommendation: Run `repair_experiment.ps1` to update the experiment."
            audit_color = C_RED
        elif audit_result_code == AUDIT_NEEDS_AGGREGATION:
            audit_message = "Audit Result: Experiment needs FINALIZATION."
            audit_recommendation = "Recommendation: Run `repair_experiment.ps1` to finalize the experiment."
            audit_color = C_YELLOW # This was already correct, but confirming it.
        elif audit_result_code == AUDIT_ALL_VALID:
            audit_message = "Audit Result: PASSED. Experiment is complete and valid."
            audit_recommendation = "Recommendation: No further action is required."
            audit_color = C_GREEN

        if print_report:
            if total_expected_trials > 0:
                completeness = (total_valid_responses / total_expected_trials) * 100 if total_expected_trials > 0 else 0
                relative_path = os.path.relpath(target_dir, PROJECT_ROOT)
                print(f"\n{C_CYAN}--- Overall Summary ---{C_RESET}")
                print(f"Experiment Directory: {relative_path}")
                print(f"Replication Status:")
                print(f"  - {'Total Runs Verified:':<32}{len(run_dirs)}")

                runs_complete_color = C_GREEN if total_complete_runs == len(run_dirs) else C_RED
                print(f"  - {'Total Runs Complete (Pipeline):':<32}{runs_complete_color}{total_complete_runs}/{len(run_dirs)}{C_RESET}")

                # Determine color for LLM response rate based on thresholds
                if completeness >= 80:
                    responses_color = C_GREEN
                elif completeness >= 50:
                    responses_color = C_YELLOW
                else:
                    responses_color = C_RED
                print(f"  - {'Total Valid LLM Responses:':<32}{responses_color}{total_valid_responses}/{total_expected_trials} ({completeness:.2f}%){C_RESET}")

                print(f"Experiment Aggregation Status: {exp_status_color}{exp_status_str_base}{exp_status_suffix}{C_RESET}")

                if not exp_complete:
                    for detail in exp_details:
                        print(f"  - {exp_status_color}{detail}{C_RESET}")

            # --- Print Final Banner ---
            banner_char = "#"
            total_width = 80
            line = audit_color + (banner_char * total_width) + C_RESET
            
            padding_width = total_width - len("###" * 2) - 2
            msg_line = f"### {audit_message.center(padding_width)} ###"

            print(f"\n{line}")
            print(f"{audit_color}{msg_line}{C_RESET}")
            
            # The recommendation line is suppressed in non-interactive mode.
            if not non_interactive:
                rec_line = f"### {audit_recommendation.center(padding_width)} ###"
                print(f"{audit_color}{rec_line}{C_RESET}")
            
            print(f"{line}")
            print() # Add final blank line

    # Final summary banner has been removed for a cleaner UI.

    # Always return the code. The main() function is responsible for exiting.
    return audit_result_code

def _run_replication_worker(rep_num, orchestrator_script, target_dir, notes, quiet, bias_script):
    """Worker function to execute one full replication using the orchestrator."""
    try:
        # Step 1: Run the main orchestrator for the replication
        cmd_orch = [sys.executable, orchestrator_script, "--replication_num", str(rep_num), "--base_output_dir", target_dir]
        if notes: cmd_orch.extend(["--notes", notes])
        if quiet: cmd_orch.append("--quiet")
        subprocess.run(cmd_orch, check=True, capture_output=True, text=True)
        
        # Step 2: Run bias analysis
        # Find the newly created directory to pass to the bias script
        run_dir_pattern = os.path.join(target_dir, f"run_*_rep-{rep_num:02d}_*")
        run_dirs = glob.glob(run_dir_pattern)
        if not run_dirs:
            return rep_num, False, f"Could not find run directory for rep {rep_num} after orchestration."
        
        run_dir = run_dirs[0]
        k_val = get_config_value(APP_CONFIG, 'Study', 'group_size', value_type=int, fallback_key='k_per_query', fallback=10)
        cmd_bias = [sys.executable, bias_script, run_dir, "--k_value", str(k_val)]
        if not quiet: cmd_bias.append("--verbose")
        subprocess.run(cmd_bias, check=True, capture_output=True, text=True)
        
        return rep_num, True, None
    except subprocess.CalledProcessError as e:
        error_details = f"Replication {rep_num} worker failed.\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
        return rep_num, False, error_details
    except Exception as e:
        return rep_num, False, f"An unexpected error occurred in replication worker {rep_num}: {e}"

def _run_new_mode(target_dir, start_rep, end_rep, notes, verbose, orchestrator_script, colors):
    """Executes 'NEW' mode by calling the orchestrator for each replication."""
    C_CYAN, C_YELLOW, C_RESET = colors['cyan'], colors['yellow'], colors['reset']

    run_dirs = glob.glob(os.path.join(target_dir, 'run_*_rep-*'))
    completed_reps = {int(re.search(r'_rep-(\d+)_', os.path.basename(d)).group(1))
                      for d in run_dirs if re.search(r'_rep-(\d+)_', os.path.basename(d))}
                      
    reps_to_run = [r for r in range(start_rep, end_rep + 1) if r not in completed_reps]
    if not reps_to_run:
        print("All required replications already exist. Nothing to do in NEW mode.")
        return True

    print(f"Will create {len(reps_to_run)} new replication(s), from {min(reps_to_run)} to {max(reps_to_run)}.")
    batch_start_time = time.time()
    
    for i, rep_num in enumerate(reps_to_run):
        header_text = f" RUNNING REPLICATION {rep_num} ({i + 1} of {len(reps_to_run)} in this batch) "
        print(f"\n{C_CYAN}{'='*80}{C_RESET}")
        print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
        print(f"{C_CYAN}{'='*80}{C_RESET}")
        
        cmd_orch = [sys.executable, orchestrator_script, "--replication_num", str(rep_num), "--base_output_dir", target_dir]
        if notes: cmd_orch.extend(["--notes", notes])
        if verbose: cmd_orch.append("--verbose")
        
        try:
            # Use Popen to stream stdout in real-time while capturing stderr.
            proc = subprocess.Popen(cmd_orch, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding='utf-8', errors='replace')
            
            # Stream and print stdout line by line as it comes in.
            for line in proc.stdout:
                print(line, end='', flush=True)

            # Wait for the process to complete and get the final return code and any stderr output.
            proc.wait()
            stderr_output = proc.stderr.read()

            if proc.returncode != 0:
                # If the process failed, manually raise a CalledProcessError with the captured stderr.
                raise subprocess.CalledProcessError(proc.returncode, proc.args, stderr=stderr_output)

        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Orchestrator for replication {rep_num} failed or was interrupted.")
            if isinstance(e, subprocess.CalledProcessError):
                # Print the captured stderr from the failed orchestrator process.
                # This will contain the full traceback from the underlying script.
                if e.stderr:
                    print(e.stderr, file=sys.stderr)
            if isinstance(e, KeyboardInterrupt):
                # If interrupted, exit the manager immediately.
                sys.exit(1)
            # For any failure, immediately stop the batch.
            return False

        elapsed = time.time() - batch_start_time
        avg_time = elapsed / (i + 1)
        remaining_reps = len(reps_to_run) - (i + 1)
        time_remaining = remaining_reps * avg_time
        eta = datetime.datetime.now() + datetime.timedelta(seconds=time_remaining)
        print(f"\n{C_YELLOW}Time Elapsed: {str(datetime.timedelta(seconds=int(elapsed)))} | Time Remaining: {str(datetime.timedelta(seconds=int(time_remaining)))} | ETA: {eta.strftime('%H:%M:%S')}{C_RESET}")

    return True

# This '_session_worker' function is no longer needed here and has been moved into orchestrate_replication.py's logic.

def _run_repair_mode(runs_to_repair, orchestrator_script_path, quiet, colors):
    """Delegates repair work to the orchestrator for each failed run."""
    C_YELLOW = colors['yellow']
    C_RESET = colors['reset']
    print(f"{C_YELLOW}--- Entering REPAIR Mode: Fixing {len(runs_to_repair)} run(s) with missing responses ---{C_RESET}")

    for run_info in runs_to_repair:
        run_dir = run_info["dir"]
        failed_indices = run_info.get("failed_indices", [])
        if not failed_indices:
            continue

        print(f"\n--- Repairing {len(failed_indices)} session(s) in: {os.path.basename(run_dir)} ---")
        
        # Call the orchestrator in --reprocess mode and pass the specific indices to fix.
        # The orchestrator is now responsible for the parallel execution.
        cmd = [
            sys.executable, orchestrator_script_path,
            "--reprocess",
            "--run_output_dir", run_dir,
            "--indices"
        ] + [str(i) for i in failed_indices]
        
        if quiet:
            cmd.append("--quiet")

        try:
            # The orchestrator will now handle its own progress display.
            subprocess.run(cmd, check=True)
        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Repair failed for {os.path.basename(run_dir)}.")
            if isinstance(e, KeyboardInterrupt): sys.exit(AUDIT_ABORTED_BY_USER)
            return False # A single failure halts the entire repair operation.
            
    return True

def _run_full_replication_repair(runs_to_repair, orchestrator_script, quiet, colors):
    """Deletes and fully regenerates runs with critical issues (e.g., missing queries, config issues)."""
def _run_config_repair(runs_to_repair, restore_config_script, colors):
    """Repairs missing or malformed config.ini.archived files by restoring them from reports."""
    C_CYAN, C_YELLOW, C_RESET = colors['cyan'], colors['yellow'], colors['reset']
    print(f"{C_YELLOW}--- Entering CONFIG REPAIR Mode: Restoring config for {len(runs_to_repair)} run(s) ---{C_RESET}")
    
    for run_info in runs_to_repair:
        run_dir_path = run_info["dir"]
        print(f"\n- Restoring config for {os.path.basename(run_dir_path)}...")
        try:
            cmd = [sys.executable, restore_config_script, run_dir_path]
            # Capture output unless there's an error, to keep the log clean.
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"  {C_CYAN}Success.{C_RESET}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to restore config for {os.path.basename(run_dir_path)}.")
            logging.error(f"Stderr:\n{e.stderr}")
            return False # Halt on failure
    return True

def _run_full_replication_repair(runs_to_repair, orchestrator_script, quiet, colors):
    """Deletes and fully regenerates runs with critical issues (e.g., missing queries, config issues)."""
    C_YELLOW = colors['yellow']
    C_RED = colors['red']
    C_RESET = colors['reset']
    print(f"{C_YELLOW}--- Entering FULL REPLICATION REPAIR Mode: Deleting and regenerating {len(runs_to_repair)} run(s) with critical issues ---{C_RESET}")

    for i, run_info in enumerate(runs_to_repair):
        run_dir_path_str = run_info["dir"]
        run_dir_path = Path(run_dir_path_str)
        run_basename = os.path.basename(run_dir_path_str)
        
        # Initialize capture_output_flag here to ensure it's always defined.
        capture_output_flag = False 

        header_text = f" REGENERATING REPLICATION {run_basename} ({i+1}/{len(runs_to_repair)}) "
        print(f"\n{C_CYAN}{'='*80}{C_RESET}")
        print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
        print(f"{C_CYAN}{'='*80}{C_RESET}")

        # Step 1: Extract replication number from directory name
        rep_num_match = re.search(r'_rep-(\d+)_', run_basename)
        if not rep_num_match:
            logging.error(f"Could not extract replication number from '{run_basename}'. Skipping repair for this run.")
            continue # Skip to the next run

        rep_num = int(rep_num_match.group(1))
        
        # Step 2: Delete the corrupted run directory
        try:
            print(f"Deleting corrupted directory: {run_dir_path_str}")
            shutil.rmtree(run_dir_path_str)
        except OSError as e:
            logging.error(f"Failed to delete directory {run_dir_path_str}: {e}")
            continue # Skip to the next run
            
        # Step 3: Regenerate the run from scratch using its replication number
        base_output_dir = os.path.dirname(run_dir_path_str)
        cmd_orch = [sys.executable, orchestrator_script, "--replication_num", str(rep_num), "--base_output_dir", base_output_dir]
        
        # Configure output capture based on the 'quiet' flag.
        if quiet:
            cmd_orch.append("--quiet")
            capture_output_flag = True # Capture output if quiet mode is active
        else:
            cmd_orch.append("--verbose") # Pass verbose flag to sub-script if not quiet
            capture_output_flag = False # Let output stream directly to console
        
        try:
            # Execute orchestrate_replication.py. 
            # If not capturing, output streams directly to console (fixing spinner).
            result = subprocess.run(cmd_orch, check=True, capture_output=capture_output_flag, text=capture_output_flag)
            
            # Log captured output if in quiet mode
            if capture_output_flag:
                if result.stdout:
                    logging.info(f"Orchestrate Replication STDOUT for {run_basename}:\n{result.stdout}")
                if result.stderr:
                    logging.error(f"Orchestrate Replication STDERR for {run_basename}:\n{result.stderr}")

            # The orchestrator is responsible for the full lifecycle, including bias analysis.
            # No further steps are needed here.

        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Full replication repair failed for {os.path.basename(run_dir)}.")
            if isinstance(e, KeyboardInterrupt): sys.exit(AUDIT_ABORTED_BY_USER)
            return False # Indicate failure
    return True

def _run_migrate_mode(target_dir, patch_script, orchestrator_script, colors, verbose=False):
    """
    Executes a one-time migration process for a legacy experiment directory.
    This mode is destructive and will delete old artifacts.
    """
    C_GREEN = colors['green']
    C_YELLOW = colors['yellow']
    C_RESET = colors['reset']
    relative_path = os.path.relpath(target_dir, PROJECT_ROOT)
    print(f"{C_YELLOW}--- Entering MIGRATE Mode: Upgrading experiment at: ---{C_RESET}")
    print(f"{C_YELLOW}{relative_path}{C_RESET}")
    run_dirs = sorted([p for p in target_dir.glob("run_*") if p.is_dir()])

    # Sub-step 1: Clean Artifacts (Run this first to remove corrupt files)
    print("\n- Cleaning old summary files and analysis artifacts...")
    try:
        files_to_delete = ["final_summary_results.csv", "batch_run_log.csv", "EXPERIMENT_results.csv"]
        for file in files_to_delete:
            file_path = target_dir / file
            if file_path.exists():
                print(f"  - Deleting old '{file_path.name}'")
                file_path.unlink()

        for run_dir in run_dirs:
            for corrupted_file in run_dir.glob("*.txt.corrupted"):
                corrupted_file.unlink()
            analysis_inputs_path = run_dir / "analysis_inputs"
            if analysis_inputs_path.is_dir():
                shutil.rmtree(analysis_inputs_path)
        print("  - Cleaning complete.")
    except Exception as e:
        logging.error(f"Failed to clean artifacts: {e}")
        return False

    # Sub-step 2: Patch Configs
    print("\n- Patching legacy configuration files...")
    try:
        subprocess.run([sys.executable, patch_script, str(target_dir)], check=True, capture_output=True, text=True)
        print("  - Patching complete.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to patch configs. Stderr:\n{e.stderr}")
        return False

    # Sub-step 3: Reprocess Each Replication
    print(f"\n- Reprocessing {len(run_dirs)} individual runs to generate modern reports...")
    try:
        for run_dir in tqdm(run_dirs, desc="Reprocessing Runs", ncols=80):
            cmd = [sys.executable, orchestrator_script, "--reprocess", "--run_output_dir", str(run_dir)]
            if not verbose: cmd.append("--quiet")
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"Failed to reprocess {run_dir.name}. Stderr:\n{result.stderr}")
                return False
        print("  - Reprocessing complete.")
    except Exception as e:
        logging.error(f"An unexpected error occurred during reprocessing: {e}")
        return False

    print(f"\n{C_GREEN}--- Migration pre-processing complete. ---{C_RESET}")
    print("The manager will now proceed with final checks to finalize the migration.")
    return True

def _handle_experiment_state(state_overall_status, payload_details, final_output_dir, end_rep, args, script_paths, colors, loop_info, run_flags):
    """
    Handles the logic for a single cycle of the main verification loop for an existing experiment.
    
    This function audits the experiment, determines the required action (repair, reprocess, etc.),
    prompts the user if necessary, and executes the action.

    Returns:
        tuple: (action_taken, success, force_reprocess_once, should_break)
    """
    # Unpack parameters for readability
    C_CYAN, C_GREEN, C_YELLOW, C_RED, C_RESET = colors.values()
    orchestrator_script = script_paths['orchestrator']
    compile_experiment_script = script_paths['compile_experiment']
    log_manager_script = script_paths['log_manager']
    loop_count, max_loops = loop_info
    is_migration_run = run_flags['is_migration_run']
    force_reprocess_once = run_flags['force_reprocess_once']

    # Default return values
    action_taken = False
    success = True
    should_break = False

    # In interactive mode (the default), print a verification header and the full audit.
    # In non-interactive mode (for automatic repairs), get the audit code silently.
    should_print_report = not args.non_interactive
    if should_print_report and not is_migration_run:
        line_separator = "#" * 80
        print(f"\n{C_CYAN}{line_separator}{C_RESET}")
        verification_header = _format_header(f"VERIFICATION CYCLE {loop_count}/{max_loops}")
        print(f"{C_CYAN}{verification_header}{C_RESET}")
        print(f"{C_CYAN}{line_separator}{C_RESET}")
    
    # Always run the audit logic, but only print the report if not in non-interactive mode.
    # The header is suppressed if the report body is suppressed. The quiet_mode flag
    # is set for migrations to suppress the main audit banner during internal verification.
    audit_result_code = _run_verify_only_mode(
        Path(final_output_dir), end_rep, colors,
        suppress_exit=True,
        print_report=should_print_report,
        is_verify_only_cli=False,
        non_interactive=(args.non_interactive or is_migration_run),
        quiet_mode=is_migration_run
    )

    if audit_result_code == AUDIT_NEEDS_MIGRATION:
        print(f"\n{C_RED}Halting due to MIGRATION required status.{C_RESET}")
        sys.exit(AUDIT_NEEDS_MIGRATION)

    elif audit_result_code == AUDIT_NEEDS_REPAIR:
        config_repairs = [d for d in payload_details if d.get("repair_type") == "config_repair"]
        full_replication_repairs = [d for d in payload_details if d.get("repair_type") == "full_replication_repair"]
        session_repairs = [d for d in payload_details if d.get("repair_type") == "session_repair"]
        
        # In non-interactive mode, just proceed. Otherwise, prompt the user.
        if args.non_interactive or _prompt_for_confirmation("The experiment requires repair. Do you wish to proceed? (Y/N): "):
            if args.non_interactive:
                # The PowerShell wrapper now handles the "Proceeding" message.
                pass
            
            # Execute repairs in order of severity
            if config_repairs:
                success = _run_config_repair(config_repairs, script_paths['restore_config'], colors)
            if success and full_replication_repairs:
                success = _run_full_replication_repair(full_replication_repairs, orchestrator_script, not args.verbose, colors)
            if success and session_repairs:
                success = _run_repair_mode(session_repairs, orchestrator_script, not args.verbose, colors)
            action_taken = True
        else:
            print(f"\n{C_RED}Repair aborted by user. Exiting.{C_RESET}")
            sys.exit(AUDIT_ABORTED_BY_USER)

    elif audit_result_code == AUDIT_NEEDS_REPROCESS or force_reprocess_once:
        if force_reprocess_once and not payload_details:
            print(f"\n{C_YELLOW}Forcing reprocess on a VALIDATED experiment. All runs will be updated.{C_RESET}")
            all_run_dirs = sorted([p for p in Path(final_output_dir).glob("run_*") if p.is_dir()])
            payload_details = [{"dir": str(run_dir)} for run_dir in all_run_dirs]
        proceed = False
        if not (is_migration_run or force_reprocess_once):
            if args.non_interactive or _prompt_for_confirmation("\nDo you wish to proceed? (Y/N): "):
                if args.non_interactive:
                    print(f"\n{C_YELLOW}Automatically proceeding with update in non-interactive mode.{C_RESET}")
                proceed = True
        else:
            print(f"\n{C_YELLOW}Automatically proceeding with update as part of migration or a forced reprocess run.{C_RESET}")
            proceed = True
        if force_reprocess_once: force_reprocess_once = False
        if proceed:
            success = _run_reprocess_mode(payload_details, args.notes, not args.verbose, orchestrator_script, compile_experiment_script, final_output_dir, log_manager_script, colors)
            action_taken = True
        else:
            print(f"\n{C_RED}Update aborted by user. Exiting.{C_RESET}")
            sys.exit(AUDIT_ABORTED_BY_USER)
    
    elif audit_result_code == AUDIT_NEEDS_AGGREGATION:
        # This state is expected when replications are valid but the experiment isn't finalized.
        # The correct action is to break the loop and let the finalization step run.
        print(f"{C_GREEN}--- All replications are valid. Proceeding to finalization. ---{C_RESET}")
        should_break = True
    
    elif audit_result_code == AUDIT_ALL_VALID:
        print(f"{C_GREEN}--- Experiment is COMPLETE. Proceeding to finalization. ---{C_RESET}")
        should_break = True

    else:
            print(f"{C_RED}--- Unhandled state or inconsistent audit result detected: OverallStatus={state_overall_status}, AuditCode={audit_result_code}. Halting. ---{C_RESET}")
            sys.exit(1)
            
    return action_taken, success, force_reprocess_once, should_break

def _run_finalization(final_output_dir, script_paths, colors):
    """Compiles all results and finalizes logs for a complete experiment."""
    C_CYAN, _, _, _, C_RESET = colors.values()

    finalization_message = "ALL TASKS COMPLETE. BEGINNING FINALIZATION."
    print(f"\n{C_CYAN}{'#' * 80}{C_RESET}")
    print(f"{C_CYAN}{_format_header(finalization_message)}{C_RESET}")
    print(f"{C_CYAN}{'#' * 80}{C_RESET}")
    
    try:
        log_file_path = os.path.join(final_output_dir, get_config_value(APP_CONFIG, 'Filenames', 'batch_run_log', fallback='batch_run_log.csv'))
        log_message = "Rebuilding batch log..." if os.path.exists(log_file_path) else "Building batch log..."
        
        print(f"\n--- {log_message} ---")
        subprocess.run([sys.executable, script_paths['log_manager'], "rebuild", final_output_dir], check=True, capture_output=True)
        
        print("--- Compiling final experiment summary... ---")
        subprocess.run([sys.executable, script_paths['compile_experiment'], final_output_dir], check=True, capture_output=True)
        
        print("--- Finalizing batch log with summary... ---")
        subprocess.run([sys.executable, script_paths['log_manager'], "finalize", final_output_dir], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        # Provide more context on subprocess failures
        logging.error("A child process failed during the finalization stage.")
        # Use os.path.basename to keep the command clean and readable
        command_str = " ".join([os.path.basename(arg) if i == 1 else arg for i, arg in enumerate(e.cmd)])
        logging.error(f"Command: {command_str}")
        if e.stderr:
            logging.error(f"Stderr:\n{e.stderr}")
        if e.stdout:
            logging.error(f"Stdout:\n{e.stdout}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred during finalization: {e}")
        sys.exit(1)

def _run_reprocess_mode(runs_to_reprocess, notes, quiet, orchestrator_script, compile_script, target_dir, log_manager_script, colors):
    """Executes 'REPROCESS' mode to fix corrupted analysis files."""
    C_CYAN = colors['cyan']
    C_YELLOW = colors['yellow']
    C_RESET = colors['reset']
    print(f"{C_YELLOW}--- Entering REPROCESS Mode: Fixing {len(runs_to_reprocess)} run(s) with corrupt analysis ---{C_RESET}")

    for i, run_info in enumerate(runs_to_reprocess):
        run_dir = run_info["dir"]
        header_text = f" RE-PROCESSING {os.path.basename(run_dir)} ({i+1}/{len(runs_to_reprocess)}) "
        print(f"\n{C_CYAN}{'='*80}{C_RESET}")
        print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
        print(f"{C_CYAN}{'='*80}{C_RESET}")

        cmd_orch = [sys.executable, orchestrator_script, "--reprocess", "--run_output_dir", run_dir]
        if quiet: cmd_orch.append("--quiet")
        if notes: cmd_orch.extend(["--notes", notes])

        try:
            # The orchestrator is now responsible for the entire reprocessing lifecycle,
            # including calling the bias analysis script.
            subprocess.run(cmd_orch, check=True)
        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Reprocessing failed for {os.path.basename(run_dir)}.")
            if isinstance(e, KeyboardInterrupt): sys.exit(1)
            return False

    # The main loop will handle the final aggregation.
    print(f"\n{C_CYAN}--- All replications reprocessed successfully. ---{C_RESET}")
    return True

def _setup_environment_and_paths():
    """Parses args, sets up colors, paths, and the experiment directory."""
    parser = argparse.ArgumentParser(description="State-machine controller for running experiments.")
    parser.add_argument('target_dir', nargs='?', default=None,
                        help="Optional. The target directory for the experiment. If not provided, a unique directory will be created.")
    parser.add_argument('--start-rep', type=int, default=1, help="First replication number for new runs.")
    parser.add_argument('--end-rep', type=int, default=None, help="Last replication number for new runs.")
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose per-replication status updates.')
    parser.add_argument('--notes', type=str, help='Optional notes for the reports.')
    parser.add_argument('--max-loops', type=int, default=10, help="Safety limit for state-machine loops.")
    parser.add_argument('--verify-only', action='store_true', help="Run in read-only diagnostic mode and print a detailed completeness report.")
    parser.add_argument('--migrate', action='store_true', help="Run a one-time migration workflow for a legacy experiment directory.")
    parser.add_argument('--reprocess', action='store_true', help="Force reprocessing of all runs in an experiment, then finalize.")
    parser.add_argument('--force-color', action='store_true', help=argparse.SUPPRESS) # Hidden from user help
    args = parser.parse_args()

    # --- Color setup ---
    use_color = sys.stdout.isatty() or args.force_color
    C_CYAN, C_GREEN, C_YELLOW, C_RED, C_RESET = ('', '', '', '', '')
    if use_color:
        C_CYAN = '\033[96m'
        C_GREEN = '\033[92m'
        C_YELLOW = '\033[93m'
        C_RED = '\033[91m'
        C_RESET = '\033[0m'
    colors = { 'cyan': C_CYAN, 'green': C_GREEN, 'yellow': C_YELLOW, 'red': C_RED, 'reset': C_RESET }

    # --- Script path setup ---
    script_paths = {
        'orchestrator': os.path.join(PROJECT_ROOT, "src", "orchestrate_replication.py"),
        'compile_experiment': os.path.join(PROJECT_ROOT, "src", 'compile_experiment_results.py'),
        'log_manager': os.path.join(PROJECT_ROOT, "src", 'replication_log_manager.py'),
        'patch': os.path.join(PROJECT_ROOT, "src", "patch_old_experiment.py"),
        'restore_config': os.path.join(PROJECT_ROOT, "src", "restore_config.py")
    }

    # --- Directory setup ---
    if args.target_dir:
        final_output_dir = os.path.abspath(args.target_dir)
        if not os.path.exists(final_output_dir):
            if args.verify_only or args.reprocess or args.migrate:
                print(f"\n{C_RED}Directory not found:{C_RESET}\n{final_output_dir}")
                sys.exit(1)
            os.makedirs(final_output_dir)
            print(f"\nCreated specified target directory:\n{final_output_dir}")
    else:
        if args.verify_only or args.reprocess or args.migrate:
            print(f"\n{C_RED}Error: --verify_only, --reprocess, and --migrate flags require a target directory.{C_RESET}")
            sys.exit(1)
        # Pass the individual color vars for now to avoid breaking _create_new_experiment_directory's signature
        final_output_dir = _create_new_experiment_directory(C_CYAN, C_RESET)

    # --- Config value setup ---
    config_num_reps = get_config_value(APP_CONFIG, 'Study', 'num_replications', value_type=int, fallback=30)
    end_rep = args.end_rep if args.end_rep is not None else config_num_reps

    return args, final_output_dir, script_paths, colors, end_rep

def main():
    """
    Main entry point for the experiment manager script.

    Orchestrates the entire experiment lifecycle by:
    1. Setting up the environment, paths, and arguments.
    2. Running the main state-machine loop to create, repair, or update the experiment.
    3. Finalizing the experiment by compiling results and logs.
    """
    parser = argparse.ArgumentParser(description="State-machine controller for running experiments.")
    parser.add_argument('target_dir', nargs='?', default=None,
                        help="Optional. The target directory for the experiment. If not provided, a unique directory will be created.")
    parser.add_argument('--start-rep', type=int, default=1, help="First replication number for new runs.")
    parser.add_argument('--end-rep', type=int, default=None, help="Last replication number for new runs.")
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose per-replication status updates.')
    parser.add_argument('--notes', type=str, help='Optional notes for the reports.')
    parser.add_argument('--max-loops', type=int, default=10, help="Safety limit for state-machine loops.")
    parser.add_argument('--verify-only', action='store_true', help="Run in read-only diagnostic mode and print a detailed completeness report.")
    parser.add_argument('--migrate', action='store_true', help="Run a one-time migration workflow for a legacy experiment directory.")
    parser.add_argument('--reprocess', action='store_true', help="Force reprocessing of all runs in an experiment, then finalize.")
    parser.add_argument('--force-color', action='store_true', help=argparse.SUPPRESS) # Hidden from user help
    parser.add_argument('--non-interactive', action='store_true', help="Run in non-interactive mode, suppressing user prompts for confirmation.")
    parser.add_argument('--quiet', action='store_true', help="Suppress all non-essential output from the audit. Used for scripting.")
    args = parser.parse_args()

    # Define color constants based on TTY status or the --force-color flag
    use_color = sys.stdout.isatty() or args.force_color
    if use_color:
        global C_CYAN, C_GREEN, C_YELLOW, C_RED, C_RESET
        C_CYAN = '\033[96m'
        C_GREEN = '\033[92m'
        C_YELLOW = '\033[93m'
        C_RED = '\033[91m'
        C_RESET = '\033[0m'

    # --- Script Paths ---
    # --- Bundle script paths and colors for cleaner function calls ---
    script_paths = {
        'orchestrator': os.path.join(PROJECT_ROOT, "src", "orchestrate_replication.py"),
        'compile_experiment': os.path.join(PROJECT_ROOT, "src", 'compile_experiment_results.py'),
        'log_manager': os.path.join(PROJECT_ROOT, "src", 'replication_log_manager.py'),
        'patch': os.path.join(PROJECT_ROOT, "src", "patch_old_experiment.py"),
        'restore_config': os.path.join(PROJECT_ROOT, "src", "restore_config.py")
    }
    colors = {
        'cyan': C_CYAN, 'green': C_GREEN, 'yellow': C_YELLOW, 'red': C_RED, 'reset': C_RESET
    }

    try:
        if args.target_dir:
            final_output_dir = os.path.abspath(args.target_dir)
            if not os.path.exists(final_output_dir):
                # Cannot verify, reprocess, or migrate a non-existent directory.
                if args.verify_only or args.reprocess or args.migrate:
                    print(f"\n{C_RED}Directory not found:{C_RESET}\n{final_output_dir}")
                    sys.exit(1)
                # If a specific target is given but doesn't exist, create it.
                os.makedirs(final_output_dir)
                relative_path = os.path.relpath(final_output_dir, PROJECT_ROOT)
                print(f"\nCreated specified target directory:\n{relative_path}")
        else:
            # If no target is given, we are explicitly in "new experiment" mode.
            # This mode is incompatible with flags that operate on existing data.
            if args.verify_only or args.reprocess or args.migrate:
                print(f"\n{C_RED}Error: --verify_only, --reprocess, and --migrate flags require a target directory.{C_RESET}")
                sys.exit(1)
            final_output_dir = _create_new_experiment_directory(colors)

        config_num_reps = get_config_value(APP_CONFIG, 'Study', 'num_replications', value_type=int, fallback=30)
        end_rep = args.end_rep if args.end_rep is not None else config_num_reps

        if args.verify_only:
            # When --verify-only is called from the CLI, print the report unless --quiet is also passed.
            should_print = not args.quiet
            exit_code = _run_verify_only_mode(
                Path(final_output_dir), end_rep, colors,
                suppress_exit=True,
                print_report=should_print,
                is_verify_only_cli=True,
                non_interactive=args.non_interactive,
                quiet_mode=args.quiet
            )
            sys.exit(exit_code)

        if args.migrate:
            if not _run_migrate_mode(Path(final_output_dir), script_paths['patch'], script_paths['orchestrator'], colors, args.verbose):
                print(f"{C_RED}--- Migration pre-processing failed. Please review logs. ---{C_RESET}")
                sys.exit(1)

        is_migration_run = args.migrate
        force_reprocess_once = args.reprocess

        loop_count = 0
        while loop_count < args.max_loops:
            loop_count += 1

            state_overall_status, payload_details, _ = _get_experiment_state(Path(final_output_dir), end_rep, verbose=False)
            
            action_taken = False
            success = True

            if state_overall_status == "NEW_NEEDED":
                success = _run_new_mode(final_output_dir, args.start_rep, end_rep, args.notes, args.verbose, script_paths['orchestrator'], colors)
                action_taken = True
            else:
                run_flags = {
                    'is_migration_run': is_migration_run,
                    'force_reprocess_once': force_reprocess_once
                }
                loop_info = (loop_count, args.max_loops)

                action_taken, success, force_reprocess_once, should_break = _handle_experiment_state(
                    state_overall_status, payload_details, final_output_dir, end_rep, args,
                    script_paths, colors, loop_info, run_flags
                )

                if should_break:
                    break

            if not success:
                print(f"{C_RED}--- A step failed. Halting experiment manager. Please review logs. ---{C_RESET}")
                sys.exit(1)
            
            if action_taken and success:
                # After a successful action, we assume the state is now valid and break the loop
                # to proceed directly to finalization. This prevents a redundant audit report.
                break


        if loop_count >= args.max_loops:
            print(f"{C_RED}--- Max loop count reached. Halting to prevent infinite loop. ---{C_RESET}")
            sys.exit(1)

        _run_finalization(final_output_dir, script_paths, colors)

        relative_path = os.path.relpath(final_output_dir, PROJECT_ROOT)
        print(f"\n{C_GREEN}Experiment run finished successfully for:{C_RESET}")
        print(f"{C_GREEN}{relative_path}{C_RESET}")
        print()

    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}--- Operation interrupted by user (Ctrl+C). Exiting gracefully. ---{C_RESET}", file=sys.stderr)
        sys.exit(AUDIT_ABORTED_BY_USER)

if __name__ == "__main__":
    main()

# === End of src/experiment_manager.py ===

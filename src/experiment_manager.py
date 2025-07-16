#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
State-Machine Controller for Experiments.

This script is the high-level, intelligent controller for managing an entire
experiment. It operates as a state machine, continuously verifying the
experiment's status and automatically taking the correct action until the
experiment is fully complete and all data is consistent.

This self-healing design makes the experiment pipeline resilient to
interruptions. Its core is a `Verify -> Act` loop, but it can also be
invoked with explicit flags for specific, one-time actions.

Modes of Operation:
-   **Default (State Machine)**: Verifies the experiment's state and automatically
    runs the appropriate action (`NEW`, `REPAIR`, `REPROCESS`) until completion.
-   **`--reprocess`**: Forces a full reprocessing of all analysis artifacts for
    an existing experiment.
-   **`--migrate`**: Runs a one-time migration workflow to upgrade a legacy
    experiment directory to the modern format.
-   **`--verify-only`**: Performs a read-only audit and prints a detailed
    completeness report without making changes. It checks for:
    -   **Configuration Integrity**: Verifies that `config.ini.archived` exists,
        is valid, and contains all required keys.
    -   **Replication File Completeness**: Ensures the correct number of core
        replication files exist (queries, responses, manifests, mappings,
        and the `REPLICATION_results.csv` summary).
    -   **Index Consistency**: Confirms a one-to-one match between query and
        response file indices (e.g., `query_001.txt` -> `response_001.txt`).
    -   **Analysis Data Validity**: Checks that analysis files contain the
        correct number of entries, matching the `n_valid_responses` metric
        from the final report.
    -   **Report Completeness**: Validates the final report's JSON block,
        ensuring all required top-level and nested metrics are present.
    -   **Experiment Finalization**: Verifies that top-level summary files
        (`EXPERIMENT_results.csv`, `batch_run_log.csv`) exist and that the
        log is marked as complete.

Usage:
# Start a brand new experiment in a default, timestamped directory:
python src/experiment_manager.py

# Run, repair, or resume an existing experiment to completion:
python src/experiment_manager.py path/to/experiment_dir

# Force a full reprocessing of an existing experiment:
python src/experiment_manager.py --reprocess path/to/experiment_dir

# Migrate a legacy experiment (after it has been copied to a new location):
python src/experiment_manager.py --migrate path/to/migrated_copy_dir

# Audit an experiment without making changes:
python src/experiment_manager.py --verify-only path/to/experiment_dir
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

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError as e:
    print(f"FATAL: Could not import config_loader.py. Error: {e}", file=sys.stderr)
    sys.exit(1)

# This will be set based on command-line args later in the script
_FORCE_COLOR = False

# ANSI color constants, will be defined in main() after arg parsing
C_CYAN, C_GREEN, C_YELLOW, C_RED, C_RESET = '', '', '', '', ''

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
    "analysis_dir":  {"path": "analysis_inputs"},
    "scores_file":   {"path": "analysis_inputs/all_scores.txt"},
    "mappings_file": {"path": "analysis_inputs/all_mappings.txt"},
    "replication_report": {"pattern": r"replication_report_\d{4}-\d{2}-\d{2}.*\.txt"},
}

REPORT_REQUIRED_METRICS = {
    "mean_mrr", "mean_top_1_acc", "mwu_stouffer_z", "mean_effect_size_r",
    "top1_pred_bias_std", "n_valid_responses"
}

REPORT_REQUIRED_NESTED_DICTS = {"positional_bias_metrics"}

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
        cfg.read(cfg_path, encoding="utf-8")
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

    # Check for required nested dictionaries (e.g., from bias analysis)
    for key in REPORT_REQUIRED_NESTED_DICTS:
        if not isinstance(j.get(key), dict):
            return f"REPORT_MISSING_NESTED_DICT: {key}"

    return "VALID"

def _verify_single_run_completeness(run_path: Path) -> tuple[str, list[str]]:
    status_details = []

    # 1. name validity
    name_match = re.match(r"run_.*_sbj-(\d+)_trl-(\d+)$", run_path.name)
    if not name_match:
        status_details = [f"{run_path.name} != run_*_sbj-NN_trl-NNN"]
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
    stat_r = _check_file_set(run_path, FILE_MANIFEST["response_files"], expected_responses)
    if stat_r != "VALID":
        status_details.append(stat_r)
    else:
        # If counts are OK, perform a deeper check for index consistency
        query_indices = _get_file_indices(run_path, FILE_MANIFEST["query_files"])
        response_indices = _get_file_indices(run_path, FILE_MANIFEST["response_files"])
        if query_indices != response_indices:
            status_details.append("QUERY_RESPONSE_INDEX_MISMATCH")
        else:
            status_details.append("responses OK")

    # 6. analysis files
    if (run_path / FILE_MANIFEST["analysis_dir"]["path"]).exists():
        # The true number of expected entries in analysis files is not the
        # count of response files (some may be invalid), but the
        # 'n_valid_responses' metric stored in the replication report's JSON.
        expected_entries = None
        try:
            latest_report = sorted(run_path.glob("replication_report_*.txt"))[-1]
            text = latest_report.read_text(encoding="utf-8")
            start = text.index("<<<METRICS_JSON_START>>>")
            end = text.index("<<<METRICS_JSON_END>>>")
            j = json.loads(text[start + len("<<<METRICS_JSON_START>>>"):end])
            expected_entries = j.get("n_valid_responses")
        except (IndexError, ValueError, KeyError):
            # This will be caught by the report check later.
            # We set a placeholder to allow the analysis check to proceed.
            expected_entries = -1 # An impossible value to ensure failure

        if expected_entries is not None and expected_entries >= 0:
            stat_a = _check_analysis_files(run_path, expected_entries, k_expected)
            if stat_a != "VALID":
                status_details.append(stat_a)
            else:
                status_details.append("analysis OK")
        else:
            # This branch handles cases where the report is missing or lacks the key.
            status_details.append("ANALYSIS_SKIPPED_BAD_REPORT")
    else:
        status_details.append("ANALYSIS_FILES_MISSING")

    # 7. report
    stat_rep = _check_report(run_path)
    if stat_rep != "VALID":
        status_details.append(stat_rep)
    else:
        status_details.append("report OK")

    # 8. replication-level summary file
    if not (run_path / "REPLICATION_results.csv").exists():
        status_details.append("REPLICATION_RESULTS_MISSING")

    # roll up
    if all(d.endswith(" OK") for d in status_details):
        return "VALIDATED", status_details
    if any("INVALID_NAME" in d for d in status_details):
        return "INVALID_NAME", status_details
    if any("CONFIG" in d for d in status_details):
        return "CONFIG_ISSUE", status_details
    if any("RESPONSE" in d and "INCOMPLETE" not in d for d in status_details):
        return "RESPONSE_ISSUE", status_details  # Missing/too-many takes precedence over incomplete
    if any("QUERY" in d or "ANALYSIS" in d or "REPORT" in d for d in status_details):
        return "ANALYSIS_ISSUE", status_details
    if any("INCOMPLETE" in d for d in status_details):
        return "ANALYSIS_ISSUE", status_details
    return "UNKNOWN", status_details

def _get_experiment_state(target_dir: Path, verbose=False) -> str:
    """High-level state machine driver."""
    cfg = ConfigLoader(target_dir / "config.ini")
    expected_reps = cfg.getint("Study", "num_replications")

    run_dirs = [p for p in target_dir.glob("run_*") if p.is_dir()]
    granular = {p.name: _verify_single_run_completeness(p) for p in run_dirs}
    fails = {n: (s, d) for n, (s, d) in granular.items() if s != "VALIDATED"}

    fatal = [n for n, (s, _) in fails.items() if s in {"INVALID_NAME", "CONFIG_ISSUE", "UNKNOWN"}]
    if fatal:
        return "FATAL_ISSUE"

    if (len(run_dirs) - len(fails)) < expected_reps:
        return "NEW_NEEDED"

    response_issue = [n for n, (s, _) in fails.items() if s == "RESPONSE_ISSUE"]
    if response_issue:
        return "REPAIR_NEEDED"

    reprocess_issues = {s for s, _ in fails.values()} - {"RESPONSE_ISSUE"}
    if reprocess_issues:
        return "REPROCESS_NEEDED"

    return "COMPLETE"

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

def _run_verify_only_mode(target_dir, expected_reps):
    """
    Runs a read-only verification and prints a detailed summary table.
    This function contains the logic from the old verify_experiment_completeness.py.
    """
    print(f"\n--- Verifying Data Completeness in: {target_dir} ---")
    run_dirs = sorted([p for p in glob.glob(os.path.join(target_dir, 'run_*')) if os.path.isdir(p)])

    if not run_dirs:
        print("No 'run_*' directories found. Nothing to verify.")
        return True

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
            total_expected_trials += int(re.match(r".*_trl-(\d+)$", run_dir.name).group(1))
            
            # Actual valid responses comes from the JSON report, the single source of truth
            n_valid_in_run = 0
            latest_report = sorted(run_dir.glob("replication_report_*.txt"))[-1]
            text = latest_report.read_text(encoding="utf-8")
            start = text.index("<<<METRICS_JSON_START>>>")
            end = text.index("<<<METRICS_JSON_END>>>")
            j = json.loads(text[start + len("<<<METRICS_JSON_START>>>"):end])
            n_valid_in_run = j.get("n_valid_responses", 0)
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

    # Set a max width for the directory name column to keep the table compact
    MAX_NAME_WIDTH = 65
    max_name_len = min(max(len(run['name']) for run in all_runs_data), MAX_NAME_WIDTH) if all_runs_data else 20

    print(f"\n{'Run Directory':<{max_name_len}} {'Status':<20} {'Details'}")
    print(f"{'-'*max_name_len} {'-'*20} {'-'*45}")
    for run in all_runs_data:
        display_name = run['name']
        if len(display_name) > max_name_len:
            display_name = display_name[:max_name_len - 3] + "..."

        status_color = C_GREEN if run['status'] == "VALIDATED" else C_RED
        print(f"{display_name:<{max_name_len}} {status_color}{run['status']:<20}{C_RESET} {run['details']}")

    # Check for experiment-level summary files
    exp_complete, exp_details = _verify_experiment_level_files(Path(target_dir))
    exp_status_str = f"{C_GREEN}COMPLETE{C_RESET}" if exp_complete else f"{C_RED}INCOMPLETE{C_RESET}"
    
    # Only show summary if there are valid runs to report on
    if total_expected_trials > 0:
        completeness = (total_valid_responses / total_expected_trials) * 100
        print("\n--- Overall Summary ---")
        print(f"Replication Status:")
        print(f"  - Total Runs Verified:          {len(run_dirs)}")
        print(f"  - Total Runs Complete (Pipeline): {total_complete_runs}/{len(run_dirs)}")
        print(f"  - Total Valid LLM Responses:      {total_valid_responses}/{total_expected_trials} ({completeness:.2f}%)")
        print(f"Experiment Finalization Status: {exp_status_str}")
        if not exp_complete:
            for detail in exp_details:
                print(f"  - {C_RED}{detail}{C_RESET}")

    return True  # Indicates the mode ran successfully

def _run_new_mode(target_dir, start_rep, end_rep, notes, quiet, orchestrator_script, bias_script):
    """Executes the 'NEW' mode to create missing replications."""
    print(f"{C_CYAN}--- Entering NEW Mode: Creating missing replications ---{C_RESET}")
    
    completed_reps = {int(re.search(r'_rep-(\d+)_', os.path.basename(d)).group(1))
                      for d in glob.glob(os.path.join(target_dir, 'run_*_rep-*'))
                      if re.search(r'_rep-(\d+)_', os.path.basename(d))}
                      
    reps_to_run = [r for r in range(start_rep, end_rep + 1) if r not in completed_reps]
    if not reps_to_run:
        print("All replications exist. Nothing to do in NEW mode.")
        return True

    print(f"Will create {len(reps_to_run)} new replication(s).")
    batch_start_time = time.time()
    
    for i, rep_num in enumerate(reps_to_run):
        header_text = f" RUNNING REPLICATION {rep_num} of {end_rep} "
        print("\n" + "="*80)
        print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
        print("="*80)
        
        cmd_orch = [sys.executable, orchestrator_script, "--replication_num", str(rep_num), "--base_output_dir", target_dir]
        if notes: cmd_orch.extend(["--notes", notes])
        if quiet: cmd_orch.append("--quiet")
        
        try:
            subprocess.run(cmd_orch, check=True)
            
            # Run bias analysis
            search_pattern = os.path.join(target_dir, f'run_*_rep-{rep_num:03d}_*')
            found_dirs = [d for d in glob.glob(search_pattern) if os.path.isdir(d)]
            if len(found_dirs) == 1:
                run_dir = found_dirs[0]
                k_val = get_config_value(APP_CONFIG, 'Study', 'group_size', value_type=int, fallback_key='k_per_query', fallback=10)
                cmd_bias = [sys.executable, bias_script, run_dir, "--k_value", str(k_val)]
                if not quiet: cmd_bias.append("--verbose")
                subprocess.run(cmd_bias, check=True)
            else:
                logging.warning(f"Could not find unique run directory for rep {rep_num} to run bias analysis.")

        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Replication {rep_num} failed or was interrupted.")
            if isinstance(e, KeyboardInterrupt): sys.exit(1)
            return False # Indicate failure

        elapsed = time.time() - batch_start_time
        avg_time = elapsed / (i + 1)
        remaining_reps = len(reps_to_run) - (i + 1)
        eta = datetime.datetime.now() + datetime.timedelta(seconds=remaining_reps * avg_time)
        print(f"{C_GREEN}Time Elapsed: {str(datetime.timedelta(seconds=int(elapsed)))} | ETA: {eta.strftime('%H:%M:%S')}{C_RESET}")

    return True

def _repair_worker(run_dir, sessions_script_path, index, quiet):
    """Worker function to retry a single failed session."""
    cmd = [sys.executable, sessions_script_path, "--run_output_dir", run_dir, "--indices", str(index), "--force-rerun"]
    if quiet: cmd.append("--quiet")
    
    try:
        # Run quietly, capture output to prevent jumbled logs
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        return index, True, None
    except subprocess.CalledProcessError as e:
        error_log = f"REPAIR FAILED for index {index} in {os.path.basename(run_dir)}\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
        return index, False, error_log

def _run_repair_mode(runs_to_repair, sessions_script_path, quiet, max_workers):
    """Executes the 'REPAIR' mode to fix missing API responses."""
    print(f"{C_YELLOW}--- Entering REPAIR Mode: Fixing {len(runs_to_repair)} run(s) with missing responses ---{C_RESET}")
    
    all_tasks = []
    for run_info in runs_to_repair:
        for index in run_info.get("failed_indices", []):
            all_tasks.append((run_info["dir"], index))
            
    if not all_tasks:
        print("No specific failed indices found to repair.")
        return True

    print(f"Attempting to repair {len(all_tasks)} failed API calls across all runs.")
    successful_repairs = 0
    failed_repairs = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        task_func = partial(_repair_worker, sessions_script_path=sessions_script_path, quiet=quiet)
        future_to_task = {executor.submit(task_func, run_dir=task[0], index=task[1]): task for task in all_tasks}

        for future in tqdm(as_completed(future_to_task), total=len(all_tasks), desc="Repairing Sessions"):
            index, success, error_log = future.result()
            if success:
                successful_repairs += 1
            else:
                failed_repairs += 1
                logging.error(error_log)
    
    print(f"Repair complete: {successful_repairs} successful, {failed_repairs} failed.")
    return failed_repairs == 0

def _run_migrate_mode(target_dir, patch_script, rebuild_script, verbose=False):
    """
    Executes a one-time migration process for a legacy experiment directory.
    This mode is destructive and will delete old artifacts.
    """
    print(f"{C_YELLOW}--- Entering MIGRATE Mode: Upgrading experiment at: {target_dir} ---{C_RESET}")

    # Step 1: Patch Configs
    print("\n[1/3: Patch Configs] Running patch_old_experiment.py...")
    try:
        subprocess.run([sys.executable, patch_script, target_dir], check=True, capture_output=True, text=True)
        print("Step 1 completed successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to patch configs. Stderr:\n{e.stderr}")
        return False

    # Step 2: Rebuild Reports
    print("\n[2/3: Rebuild Reports] Running rebuild_reports.py...")
    try:
        cmd = [sys.executable, rebuild_script, target_dir]
        if verbose:
            cmd.append("--verbose")
        # Do not capture output, so the progress bar from the child script is visible.
        subprocess.run(cmd, check=True, text=True)
        print("Step 2 completed successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to rebuild reports. Stderr:\n{e.stderr}")
        return False

    # Step 3: Clean Artifacts
    print("\n[3/3: Clean Artifacts] Deleting old and temporary files...")
    try:
        # Delete top-level summary files that will be regenerated
        files_to_delete = ["final_summary_results.csv", "batch_run_log.csv", "EXPERIMENT_results.csv"]
        for file in files_to_delete:
            file_path = os.path.join(target_dir, file)
            if os.path.exists(file_path):
                print(f" - Deleting old '{file}'")
                os.remove(file_path)

        # Delete artifacts from all run_* subdirectories
        run_dirs = glob.glob(os.path.join(target_dir, "run_*"))
        for run_dir in run_dirs:
            if not os.path.isdir(run_dir): continue
            
            # Delete corrupted report backups
            for corrupted_file in glob.glob(os.path.join(run_dir, "*.txt.corrupted")):
                os.remove(corrupted_file)
            
            # Delete old analysis_inputs directory
            analysis_inputs_path = os.path.join(run_dir, "analysis_inputs")
            if os.path.isdir(analysis_inputs_path):
                shutil.rmtree(analysis_inputs_path)
        print("Step 3 completed successfully.")
    except Exception as e:
        logging.error(f"Failed to clean artifacts: {e}")
        return False
    
    print(f"\n{C_GREEN}--- Migration pre-processing complete. ---{C_RESET}")
    print("The manager will now proceed with reprocessing to finalize the migration.")
    return True

def _run_reprocess_mode(runs_to_reprocess, notes, quiet, orchestrator_script, bias_script):
    """Executes 'REPROCESS' mode to fix corrupted analysis files."""
    print(f"{C_YELLOW}--- Entering REPROCESS Mode: Fixing {len(runs_to_reprocess)} run(s) with corrupt analysis ---{C_RESET}")

    for i, run_info in enumerate(runs_to_reprocess):
        run_dir = run_info["dir"]
        header_text = f" RE-PROCESSING {os.path.basename(run_dir)} ({i+1}/{len(runs_to_reprocess)}) "
        print("\n" + "="*80)
        print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
        print("="*80)
        
        cmd_orch = [sys.executable, orchestrator_script, "--reprocess", "--run_output_dir", run_dir]
        if quiet: cmd_orch.append("--quiet")
        if notes: cmd_orch.extend(["--notes", notes])

        try:
            subprocess.run(cmd_orch, check=True)
            
            # Run bias analysis
            config_path = os.path.join(run_dir, 'config.ini.archived')
            if os.path.exists(config_path):
                config = configparser.ConfigParser()
                config.read(config_path)
                k_value = config.getint('Study', 'group_size', fallback=config.getint('Study', 'k_per_query', fallback=0))
                if k_value > 0:
                    cmd_bias = [sys.executable, bias_script, run_dir, "--k_value", str(k_value)]
                    if not quiet: cmd_bias.append("--verbose")
                    subprocess.run(cmd_bias, check=True)
            else:
                logging.warning(f"No archived config in {os.path.basename(run_dir)}, cannot run bias analysis.")

        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Reprocessing failed for {os.path.basename(run_dir)}.")
            if isinstance(e, KeyboardInterrupt): sys.exit(1)
            return False
            
    return True

def main():
    parser = argparse.ArgumentParser(description="State-machine controller for running experiments.")
    parser.add_argument('target_dir', nargs='?', default=None,
                        help="Optional. The target directory for the experiment. If not provided, a unique directory will be created.")
    parser.add_argument('--start-rep', type=int, default=1, help="First replication number for new runs.")
    parser.add_argument('--end-rep', type=int, default=None, help="Last replication number for new runs.")
    parser.add_argument('--max-workers', type=int, default=10, help="Max parallel workers for repair mode.")
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose per-replication status updates.')
    parser.add_argument('--notes', type=str, help='Optional notes for the reports.')
    parser.add_argument('--max-loops', type=int, default=10, help="Safety limit for state-machine loops.")
    parser.add_argument('--verify-only', action='store_true', help="Run in read-only diagnostic mode and print a detailed completeness report.")
    parser.add_argument('--migrate', action='store_true', help="Run a one-time migration workflow for a legacy experiment directory.")
    parser.add_argument('--reprocess', action='store_true', help="Force reprocessing of all runs in an experiment, then finalize.")
    parser.add_argument('--force-color', action='store_true', help=argparse.SUPPRESS) # Hidden from user help
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
    orchestrator_script = os.path.join(current_dir, "orchestrate_replication.py")
    sessions_script = os.path.join(current_dir, "run_llm_sessions.py")
    log_manager_script = os.path.join(current_dir, "replication_log_manager.py")
    compile_script = os.path.join(current_dir, "experiment_aggregator.py")
    bias_analysis_script = os.path.join(current_dir, "run_bias_analysis.py")
    patch_script = os.path.join(current_dir, "patch_old_experiment.py")
    rebuild_script = os.path.join(current_dir, "rebuild_reports.py")

    try:
        if args.target_dir:
            final_output_dir = os.path.abspath(args.target_dir)
        else:
            # Create a default directory based on config.ini
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            base_output = get_config_value(APP_CONFIG, 'General', 'base_output_dir', fallback='output')
            new_exp_subdir = get_config_value(APP_CONFIG, 'General', 'new_experiments_subdir', fallback='new_experiments')
            exp_prefix = get_config_value(APP_CONFIG, 'General', 'experiment_dir_prefix', fallback='experiment_')
            base_path = os.path.join(PROJECT_ROOT, base_output, new_exp_subdir)
            final_output_dir = os.path.join(base_path, f"{exp_prefix}{timestamp}")
            print(f"{C_CYAN}No target directory specified. Creating default: {final_output_dir}{C_RESET}")

        if not os.path.exists(final_output_dir):
            # If in verify-only mode and the dir doesn't exist, just say so and exit.
            if args.verify_only:
                print(f"Directory not found: {final_output_dir}")
                sys.exit(1)
            os.makedirs(final_output_dir)
            print(f"Created target directory: {final_output_dir}")

        config_num_reps = get_config_value(APP_CONFIG, 'Study', 'num_replications', value_type=int, fallback=30)
        end_rep = args.end_rep if args.end_rep is not None else config_num_reps

        # --- Run verify-only mode and exit if specified ---
        if args.verify_only:
            _run_verify_only_mode(final_output_dir, end_rep)
            sys.exit(0)

        # --- Run migrate mode if specified. This is a pre-step to the main loop. ---
        if args.migrate:
            if not _run_migrate_mode(final_output_dir, patch_script, rebuild_script, args.verbose):
                print(f"{C_RED}--- Migration failed. Please review logs. ---{C_RESET}")
                sys.exit(1)

        # The --reprocess flag acts as a one-time override for the state machine.
        force_reprocess_once = args.reprocess

        # --- Main State-Machine Loop ---
        loop_count = 0
        while loop_count < args.max_loops:
            loop_count += 1
            print("\n" + "="*80)
            print(f"{C_CYAN}### VERIFICATION CYCLE {loop_count}/{args.max_loops} ###{C_RESET}")

            # If the reprocess flag is set, force the state for the first loop iteration.
            if force_reprocess_once:
                print(f"{C_YELLOW}Forced reprocessing flag is active. Overriding state detection.{C_RESET}")
                all_run_dirs = sorted([p for p in glob.glob(os.path.join(final_output_dir, 'run_*')) if os.path.isdir(p)])
                state = "REPROCESS_NEEDED"
                details = [{"dir": d} for d in all_run_dirs]
                force_reprocess_once = False  # Ensure it only runs once
            else:
                state, details = _get_experiment_state(final_output_dir, end_rep, args.verbose)
            
            print(f"Current Experiment State: {C_GREEN}{state}{C_RESET}")

            success = False
            if state == "NEW_NEEDED":
                success = _run_new_mode(final_output_dir, args.start_rep, end_rep, args.notes, not args.verbose, orchestrator_script, bias_analysis_script)
            elif state == "REPAIR_NEEDED":
                success = _run_repair_mode(details, sessions_script, not args.verbose, args.max_workers)
            elif state == "REPROCESS_NEEDED":
                success = _run_reprocess_mode(details, args.notes, not args.verbose, orchestrator_script, bias_analysis_script)
            elif state == "COMPLETE":
                print(f"{C_GREEN}--- Experiment is COMPLETE. Proceeding to finalization. ---{C_RESET}")
                break
            else:
                print(f"{C_RED}--- Unhandled or inconsistent state detected: {state}. Halting. ---{C_RESET}")
                print(f"Details: {details}")
                sys.exit(1)

            if not success:
                print(f"{C_RED}--- A step failed. Halting experiment manager. Please review logs. ---{C_RESET}")
                sys.exit(1)

        if loop_count >= args.max_loops:
            print(f"{C_RED}--- Max loop count reached. Halting to prevent infinite loop. ---{C_RESET}")
            sys.exit(1)

        # --- Finalization Stage ---
        print("\n" + "="*80)
        print("### ALL TASKS COMPLETE. BEGINNING FINALIZATION. ###")
        print("="*80)
        
        # Rebuild log, compile results, finalize log
        try:
            log_file_path = os.path.join(final_output_dir, get_config_value(APP_CONFIG, 'Filenames', 'batch_run_log', fallback='batch_run_log.csv'))
            log_message = "Rebuilding batch log..." if os.path.exists(log_file_path) else "Building batch log..."
            
            print(f"\n--- {log_message} ---")
            subprocess.run([sys.executable, log_manager_script, "rebuild", final_output_dir], check=True, capture_output=True)
            
            print("\n--- Compiling final statistical summary... ---")
            subprocess.run([sys.executable, compile_script, final_output_dir, "--mode", "hierarchical"], check=True, capture_output=True)
            print("\n--- Finalizing batch log with summary... ---")
            subprocess.run([sys.executable, log_manager_script, "finalize", final_output_dir], check=True, capture_output=True)
        except Exception as e:
            logging.error(f"An error occurred during finalization: {e}")
            sys.exit(1)

        print(f"\n{C_GREEN}--- Experiment Run Finished Successfully ---{C_RESET}")

    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}--- Operation interrupted by user (Ctrl+C). Exiting gracefully. ---{C_RESET}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/experiment_manager.py ===
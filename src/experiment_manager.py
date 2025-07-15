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
    completeness report without making changes.

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
import re
import shutil
import configparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial

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

C_CYAN = '\033[96m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_RESET = '\033[0m'

# --- Verification Helper Functions ---

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

def _verify_single_run_completeness(run_dir, verbose=False):
    """Audits a single run_* directory and returns its state."""
    run_name = os.path.basename(run_dir)
    if verbose:
        print(f"[MANAGER_DEBUG] Verifying: {run_name}")

    m_match = re.search(r"trl-(\d+)", run_name)
    k_match = re.search(r"sbj-(\d+)", run_name)

    if not m_match or not k_match:
        if verbose:
            print(f"[MANAGER_DEBUG]   - Determined Status: {C_RED}INVALID_NAME{C_RESET}")
        return {"status": "INVALID_NAME", "details": "Name must contain trl-NNN and sbj-NN."}

    expected_trials = int(m_match.group(1))
    k = int(k_match.group(1))

    # File counts
    # Use a robust method for counting to ensure only valid trial queries are included.
    query_files = glob.glob(os.path.join(run_dir, "session_queries", "llm_query_*.txt"))
    num_queries = len([f for f in query_files if re.search(r'_(\d{3})\.txt', f)])
    
    # Also make the response count more specific to avoid counting .error files etc.
    response_files = glob.glob(os.path.join(run_dir, "session_responses", "llm_response_*.txt"))
    num_responses = len([f for f in response_files if re.fullmatch(r'llm_response_\d{3}\.txt', os.path.basename(f))])

    analysis_path = os.path.join(run_dir, "analysis_inputs")
    num_matrices = _count_matrices_in_file(os.path.join(analysis_path, "all_scores.txt"), k)
    num_mappings = _count_lines_in_file(os.path.join(analysis_path, "all_mappings.txt"), skip_header=True)

    if verbose:
        print(f"[MANAGER_DEBUG]   - Expected Trials: {expected_trials}")
        print(f"[MANAGER_DEBUG]   - Queries Found:   {num_queries}")
        print(f"[MANAGER_DEBUG]   - Responses Found: {num_responses}")
        print(f"[MANAGER_DEBUG]   - Matrices Found:  {num_matrices}")
        print(f"[MANAGER_DEBUG]   - Mappings Found:  {num_mappings}")

    # Determine state
    state = {
        "dir": run_dir,
        "expected": expected_trials,
        "queries": num_queries,
        "responses": num_responses,
        "matrices": num_matrices,
        "mappings": num_mappings,
        "status": "UNKNOWN"
    }

    if num_queries == 0:
        state["status"] = "NEW"
    elif num_queries < expected_trials:
        state["status"] = "INCOMPLETE_QUERIES" # Should be treated as NEW
    elif num_responses < num_queries:
        state["status"] = "REPAIR_NEEDED"
        failed_indices = []
        
        # Robustly find all valid query indices from filenames
        query_indices = set()
        for f in glob.glob(os.path.join(run_dir, "session_queries", "llm_query_*.txt")):
            match = re.search(r'_(\d{3})\.txt', f)
            if match:
                query_indices.add(int(match.group(1)))

        for index in query_indices:
            if not os.path.exists(os.path.join(run_dir, "session_responses", f"llm_response_{index:03d}.txt")):
                failed_indices.append(index)
        state["failed_indices"] = failed_indices
    elif num_responses == num_queries:
        analysis_file_exists = os.path.exists(os.path.join(analysis_path, "all_scores.txt"))
        # A run is COMPLETE only if the analysis file exists AND the counts inside are correct.
        if analysis_file_exists and num_matrices == num_queries and num_mappings == num_queries:
            state["status"] = "COMPLETE"
        # A run needs REPROCESSING if responses are all there, but analysis is missing or incomplete.
        elif not analysis_file_exists or num_matrices < num_queries or num_mappings < num_queries:
            state["status"] = "REPROCESS_NEEDED"
        # Any other case (e.g., more matrices than queries) is an INCONSISTENT state.
        else:
            state["status"] = "INCONSISTENT"
    else:
        state["status"] = "INCONSISTENT" # e.g. more responses than queries
    
    if verbose:
        status_color = C_GREEN if state['status'] == 'COMPLETE' else C_YELLOW
        print(f"[MANAGER_DEBUG]   - Determined Status: {status_color}{state['status']}{C_RESET}")

    return state

def _get_experiment_state(target_dir, expected_reps, verbose=False):
    """Aggregates verification of all runs to determine overall experiment state."""
    if verbose:
        print(f"{C_YELLOW}[MANAGER_DEBUG] Running verification...{C_RESET}")
        
    run_dirs = sorted([p for p in glob.glob(os.path.join(target_dir, 'run_*')) if os.path.isdir(p)])
    
    if not run_dirs or len(run_dirs) < expected_reps:
        return "NEW_NEEDED", {"missing_reps": expected_reps - len(run_dirs)}

    states = {"REPAIR_NEEDED": [], "REPROCESS_NEEDED": [], "COMPLETE": [], "INCONSISTENT": []}
    for run_dir in run_dirs:
        verification = _verify_single_run_completeness(run_dir, verbose)
        status = verification["status"]
        if status in states:
            states[status].append(verification)
    
    if states["INCONSISTENT"]:
        return "INCONSISTENT", states["INCONSISTENT"]
    if states["REPAIR_NEEDED"]:
        return "REPAIR_NEEDED", states["REPAIR_NEEDED"]
    if states["REPROCESS_NEEDED"]:
        return "REPROCESS_NEEDED", states["REPROCESS_NEEDED"]
    if len(states["COMPLETE"]) == expected_reps:
        return "COMPLETE", None
    
    return "UNKNOWN", states # Fallback

# --- Mode Execution Functions ---

def _run_verify_only_mode(target_dir, expected_reps):
    """
    Runs a read-only verification and prints a detailed summary table.
    This function contains the logic from the old verify_experiment_completeness.py.
    """
    print(f"\n--- Verifying Data Completeness in: {target_dir} ---")
    run_dirs = sorted([p for p in glob.glob(os.path.join(target_dir, 'run_*')) if os.path.isdir(p)])
    
    if not run_dirs:
        print("No 'run_*' directories found. Nothing to verify.")
        return

    all_runs_data = []
    total_expected_trials = 0
    total_valid_responses = 0
    total_complete_runs = 0

    for run_dir in run_dirs:
        verification = _verify_single_run_completeness(run_dir)
        status = verification.get("status", "ERROR")
        details = ""
        is_complete = (status == "COMPLETE")
        
        valid_responses = verification.get('matrices', 0)
        expected_trials = verification.get('expected', 0)

        if is_complete:
            details = f"Parsed {valid_responses}/{expected_trials} trials"
            total_complete_runs += 1
        elif status == "INVALID_NAME":
            details = "Invalid directory name"
        else:
            q = verification.get('queries', 0)
            r = verification.get('responses', 0)
            parts = []
            if q < expected_trials: parts.append(f"Queries:{q}/{expected_trials}")
            if r < q: parts.append(f"Responses:{r}/{q}")
            if not os.path.exists(os.path.join(run_dir, "analysis_inputs", "all_scores.txt")):
                parts.append("Analysis not run")
            details = ", ".join(parts)
        
        total_expected_trials += expected_trials
        total_valid_responses += valid_responses
        all_runs_data.append({"name": os.path.basename(run_dir), "status": status, "details": details})

    max_name_len = max(len(run['name']) for run in all_runs_data) if all_runs_data else 20
    print(f"\n{'Run Directory':<{max_name_len}} {'Status':<20} {'Details'}")
    print(f"{'-'*max_name_len} {'-'*20} {'-'*30}")
    for run in all_runs_data:
        status_color = C_GREEN if run['status'] == "COMPLETE" else C_RED
        print(f"{run['name']:<{max_name_len}} {status_color}{run['status']:<20}{C_RESET} {run['details']}")

    if total_expected_trials > 0:
        completeness = (total_valid_responses / total_expected_trials) * 100
        print("\n--- Overall Summary ---")
        print(f"Total Runs Verified: {len(run_dirs)}")
        print(f"Total Runs Complete (Pipeline): {total_complete_runs}/{len(run_dirs)}")
        print(f"Total Valid LLM Responses:      {total_valid_responses}/{total_expected_trials} ({completeness:.2f}%)")
    
    return True # Indicates the mode ran successfully

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

def _run_migrate_mode(target_dir, patch_script, rebuild_script):
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
        subprocess.run([sys.executable, rebuild_script, target_dir], check=True, capture_output=True, text=True)
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
    args = parser.parse_args()

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
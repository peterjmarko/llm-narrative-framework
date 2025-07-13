#!/usr/bin/env python3
import subprocess
import sys
import os
import glob
import re

# ANSI color codes
C_GREEN = '\033[92m'
C_RED = '\033[91m'
C_CYAN = '\033[96m'
C_RESET = '\033[0m'

def _clean_parallel_coverage_files(is_start):
    """Finds and deletes only parallel .coverage.* files, leaving .coverage intact."""
    if is_start:
        print("--- Cleaning up old parallel coverage data... ---", flush=True)
    else:
        print("\n--- Cleaning up post-run parallel coverage data... ---", flush=True)
        
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # This glob pattern specifically targets files with a dot after '.coverage'
    parallel_files = glob.glob(os.path.join(project_root, '.coverage.*'))
    
    if not parallel_files:
        print("No parallel coverage data found to clean.")
        return

    try:
        for f in parallel_files:
            os.remove(f)
        print(f"Successfully removed {len(parallel_files)} parallel file(s).")
    except OSError as e:
        print(f"Error removing coverage files: {e}", file=sys.stderr)

def run_pytest(args):
    """Runs the Python pytest suite and captures results."""
    print("\n" + "="*62, flush=True)
    print("--- Running Python Unit Tests (pytest) ---")
    print("="*62, flush=True)
    
    cmd = [sys.executable, "-m", "pytest", "-v"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    passed, failed = 0, 0
    summary_line = result.stdout.strip().split('\n')[-1]
    
    failed_match = re.search(r"(\d+)\s+failed", summary_line)
    passed_match = re.search(r"(\d+)\s+passed", summary_line)
    
    if failed_match: failed = int(failed_match.group(1))
    if passed_match: passed = int(passed_match.group(1))
            
    total = passed + failed
    
    if result.returncode == 0:
        print("\n--- Pytest Suite: PASS ---")
    else:
        print("\n--- Pytest Suite: FAIL ---", file=sys.stderr)
        
    return passed, failed, total

def run_pwsh_tests():
    """Runs the PowerShell test suite and extracts results."""
    print("\n" + "="*62, flush=True)
    print("--- Running PowerShell Script Tests ---")
    print("="*62, flush=True)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ps_script_path = os.path.join(script_dir, 'run_all_ps_tests.ps1')
    
    result = subprocess.run(["pwsh", "-File", ps_script_path], capture_output=True, text=True, encoding='utf-8')
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    passed, failed, total = 0, 0, 0
    match = re.search(r"OVERALL TOTALS\s+(\d+)\s+(\d+)\s+(\d+)", result.stdout)
    if match:
        passed = int(match.group(1))
        failed = int(match.group(2))
        total = int(match.group(3))

    if result.returncode == 0:
        print("\n--- PowerShell Tests: PASS ---")
    else:
        print("\n--- PowerShell Tests: FAIL ---", file=sys.stderr)
        
    return passed, failed, total

def main():
    """Orchestrates the entire test suite."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    _clean_parallel_coverage_files(is_start=True)
    
    cli_args = sys.argv[1:]
    
    py_passed, py_failed, py_total = run_pytest(cli_args)
    ps_passed, ps_failed, ps_total = run_pwsh_tests()
    
    py_status_str = f"{C_GREEN}PASS{C_RESET}" if py_failed == 0 else f"{C_RED}FAIL{C_RESET}"
    ps_status_str = f"{C_GREEN}PASS{C_RESET}" if ps_failed == 0 else f"{C_RED}FAIL{C_RESET}"

    summary_title = " OVERALL TEST SUMMARY "
    border = "#" * 62
    
    print("\n" + C_CYAN + border + C_RESET)
    print(C_CYAN + "###" + summary_title.center(56) + "###" + C_RESET)
    print(C_CYAN + border + C_RESET + "\n")

    header = f"{'Test Suite':<25} {'Status':<15} {'Passed':>8} {'Failed':>8} {'Total':>8}"
    print(header)
    print("-" * len(header))
    print(f"{'Python Tests':<25} {py_status_str:<15} {py_passed:>8} {py_failed:>8} {py_total:>8}")
    print(f"{'PowerShell Tests':<25} {ps_status_str:<15} {ps_passed:>8} {ps_failed:>8} {ps_total:>8}")
    print("-" * len(header))
    total_passed = py_passed + ps_passed
    total_failed = py_failed + ps_failed
    total_tests = py_total + ps_total
    print(f"{'OVERALL TOTALS':<25} {'':<15} {total_passed:>8} {total_failed:>8} {total_tests:>8}\n")

    _clean_parallel_coverage_files(is_start=False)

    if total_failed == 0:
        print(f"{C_GREEN}All tests passed successfully!{C_RESET}")
        sys.exit(0)
    else:
        print(f"{C_RED}One or more test suites failed.{C_RESET}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
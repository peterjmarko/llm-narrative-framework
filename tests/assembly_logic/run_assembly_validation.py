#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
# Copyright (C) 2025 Peter J. Marko
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
# Filename: tests/assembly_logic/run_assembly_validation.py

"""
Wrapper script for running the assembly validation test with clear output.
"""

import subprocess
import sys
from pathlib import Path
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

def center_text(text, width=80):
    """Center text within the specified width."""
    return text.center(width)

def main():
    print()
    print(f"{Fore.MAGENTA}{'=' * 80}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{center_text('PERSONALITY ASSEMBLY ALGORITHM VALIDATION')}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{'=' * 80}{Style.RESET_ALL}")
    print()
    print("This test validates that the personality assembly algorithm produces")
    print("output identical to the ground truth data from Solar Fire.")
    print("It compares the generated personalities_db.txt against the reference")
    print("file to ensure bit-for-bit identical results.")
    print()
    
    # Get the project root directory
    project_root = Path(__file__).resolve().parents[2]
    
    # Run the pytest command with output suppressed
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "tests/algorithm_validation/test_profile_generation_algorithm.py",
        "-q"  # Quiet mode to minimize pytest output
    ], cwd=project_root, capture_output=True, text=True)
    
    print()
    if result.returncode == 0:
        print(f"{Fore.GREEN}{'=' * 80}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{center_text('✅ VALIDATION PASSED')}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{center_text('The personality assembly algorithm is working correctly.')}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'=' * 80}{Style.RESET_ALL}")
        print()
    else:
        print(f"{Fore.RED}{'=' * 80}{Style.RESET_ALL}")
        print(f"{Fore.RED}{center_text('❌ VALIDATION FAILED')}{Style.RESET_ALL}")
        print(f"{Fore.RED}{center_text('The generated output does not match the ground truth data.')}{Style.RESET_ALL}")
        print(f"{Fore.RED}{'=' * 80}{Style.RESET_ALL}")
        print()
        # Show pytest output if test failed
        if result.stdout:
            print("Pytest output:")
            print(result.stdout)
        if result.stderr:
            print("Pytest errors:")
            print(result.stderr)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())

# === End of tests/assembly_logic/run_assembly_validation.py ===

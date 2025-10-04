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
# Filename: scripts/workflows/assembly_logic/test_assembly_setup_with_pause.py

"""
Interactive assembly logic setup script that pauses for manual Solar Fire processing.

This script runs the first 3 steps of the assembly logic validation workflow,
then pauses to allow the user to perform manual processing in Solar Fire,
and finally continues with the remaining steps after user confirmation.
"""

import subprocess
import sys
import os
from pathlib import Path
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)


def run_script(script_path):
    """Run a Python script and return the result."""
    # Get relative path from project root
    project_root = Path(__file__).resolve().parents[3]
    rel_path = script_path.relative_to(project_root)
    
    print(f"\n{Fore.MAGENTA}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}Running: {rel_path.as_posix()}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{'='*80}{Style.RESET_ALL}")
    
    try:
        result = subprocess.run([sys.executable, script_path], check=True)
        print(f"✅ {rel_path.as_posix()} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n{Fore.RED}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.RED}ERROR: Script failed with exit code {e.returncode}{Style.RESET_ALL}")
        print(f"{Fore.RED}Script:{Style.RESET_ALL}")
        print(f"{Fore.RED}{rel_path.as_posix()}{Style.RESET_ALL}")
        print(f"{Fore.RED}{'='*80}{Style.RESET_ALL}\n")
        return False
    except FileNotFoundError:
        print(f"\n{Fore.RED}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.RED}ERROR: Script not found{Style.RESET_ALL}")
        print(f"{Fore.RED}Script:{Style.RESET_ALL}")
        print(f"{Fore.RED}{rel_path.as_posix()}{Style.RESET_ALL}")
        print(f"{Fore.RED}{'='*80}{Style.RESET_ALL}\n")
        return False


def get_user_confirmation():
    """Get user confirmation that manual step is complete."""
    print(f"\n{Fore.RED}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.RED}{'=========='}                    {Fore.RED}MANUAL STEP REQUIRED{Fore.RED}                    {'=========='}{Style.RESET_ALL}")
    print(f"{Fore.RED}{'='*80}{Style.RESET_ALL}")
    print(f"""
Please execute the following manual procedure:

1. Open Solar Fire software.
2. Import the file created in step 3 above:
   'temp_assembly_logic_validation/data/assembly_import_file.csv'.
3. Calculate all imported charts.
4. Export all chart data as 'assembly_logic_validation_data.csv' to the following directory:
   'temp_assembly_logic_validation/data/foundational_assets/'.

See the 'Importing to and Exporting from Solar Fire' section of the Replication Guide for detailed instructions.

{Fore.YELLOW}This step is critical for generating the ground truth data needed for validation.{Style.RESET_ALL}
""")
    
    while True:
        response = input(f"\nHave you completed the manual Solar Fire processing? (Y/N): ").lower().strip()
        if response in ['y', 'yes']:
            print("\n✅ Continuing with remaining steps...")
            return True
        elif response in ['n', 'no']:
            print(f"\n{Fore.YELLOW}⏸️  Pausing. Please complete the manual step and then run this script again.{Style.RESET_ALL}")
            print("You can also run the remaining steps individually using:")
            print("  pdm run test-assembly-step4")
            print("  pdm run test-assembly-step5")
            return False
        else:
            print("Please enter 'Y' or 'N'")


def main():
    """Main execution function."""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    
    # Define the scripts to run in order
    scripts = [
        "1_generate_coverage_map.py",
        "2_select_assembly_logic_subjects.py", 
        "3_prepare_assembly_logic_import.py"
    ]
    
    # Run the first 3 steps
    print("\nStarting assembly logic setup (automated steps)...")
    
    for script in scripts:
        script_path = script_dir / script
        if not run_script(script_path):
            print(f"\n{Fore.RED}❌ Setup failed at {script}. Please fix the issue and try again.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}💡 Tip: Make sure you've completed all previous steps before continuing.{Style.RESET_ALL}\n")
            sys.exit(1)
    
    # Get user confirmation for manual step
    if not get_user_confirmation():
        print(f"\n{Fore.YELLOW}Setup paused. Run this script again after completing the manual step.{Style.RESET_ALL}")
        print()
        sys.exit(0)
    
    # Run the remaining steps
    remaining_scripts = [
        "4_extract_assembly_logic_text.py",
        "5_validate_assembly_logic_subjects.py"
    ]
    
    print("\nContinuing with remaining steps...")
    
    for script in remaining_scripts:
        script_path = script_dir / script
        if not run_script(script_path):
            print(f"\n{Fore.RED}❌ Setup failed at {script}. Please fix the issue and try again.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}💡 Tip: Make sure you've completed the manual Solar Fire processing step correctly.{Style.RESET_ALL}\n")
            sys.exit(1)
    
    print(f"\n{Fore.GREEN}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}🎉 Assembly logic setup completed successfully!{Style.RESET_ALL}")
    print(f"{Fore.GREEN}You can now run the validation test with: pdm run test-assembly{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*80}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()

# === End of scripts/workflows/assembly_logic/test_assembly_setup_with_pause.py ===

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
# Filename: src/print_config_value.py

"""
Command-Line Utility to Print a Single Value from config.ini.

This script is designed to be called from shell scripts (e.g., PowerShell)
to retrieve a specific configuration value. It prints the requested value
to standard output, allowing the calling script to capture it.
"""

import argparse
import configparser
import os
import sys

def main():
    """Reads a single value from the project's config.ini and prints it."""
    parser = argparse.ArgumentParser(description="Get a single value from config.ini.")
    parser.add_argument("section", type=str, help="The section in the INI file (e.g., 'LLM').")
    parser.add_argument("key", type=str, help="The key in the section (e.g., 'model_name').")
    args = parser.parse_args()

    try:
        # This script is in src/, so the project root is its parent directory.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        config_path = os.path.join(project_root, 'config.ini')

        if not os.path.exists(config_path):
            # Print to stderr so it doesn't pollute stdout for the calling script
            print(f"ERROR: config.ini not found at {config_path}", file=sys.stderr)
            sys.exit(1)

        config = configparser.ConfigParser()
        config.read(config_path)

        value = config.get(args.section, args.key)
        print(value)

    except (configparser.NoSectionError, configparser.NoOptionError):
        # If the section or key doesn't exist, print nothing and exit cleanly.
        # This is a safe default for the calling script.
        pass
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

# End of src/print_config_value.py ===
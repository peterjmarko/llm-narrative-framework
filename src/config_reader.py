#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/config_reader.py

"""
Command-line helper to read a specific value from the project's config.ini file.
It uses the existing config_loader module to ensure consistent configuration access.
"""

import argparse
import sys
from config_loader import APP_CONFIG, get_config_value

def main():
    """
    Parses command-line arguments for a section and key, retrieves the value
    from the global APP_CONFIG, and prints it to standard output.
    """
    parser = argparse.ArgumentParser(
        description="Read a specific value from config.ini and print it.",
        epilog="Example: python src/config_reader.py LLM model_name"
    )
    parser.add_argument("section", help="The section in the config file (e.g., 'LLM').")
    parser.add_argument("key", help="The key within the section (e.g., 'model_name').")
    args = parser.parse_args()

    # Use the pre-loaded APP_CONFIG and helper function from config_loader
    value = get_config_value(APP_CONFIG, args.section, args.key, fallback="")

    # Print the value to stdout so the calling shell script can capture it.
    # Exit with an error code if the value is empty, which indicates not found.
    if value:
        print(value, end="")
        sys.exit(0)
    else:
        # Print nothing to stderr or stdout, just exit with a non-zero status
        # to indicate that the key was not found or had no value.
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/config_reader.py ===
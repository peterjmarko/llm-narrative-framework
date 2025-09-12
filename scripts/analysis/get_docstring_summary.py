#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
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
# Filename: scripts/analysis/get_docstring_summary.py

"""Extracts the summary from a Python script's module-level docstring."""

import argparse
import ast
import textwrap


def get_docstring_summary(file_path):
    """
    Parses a Python file to find the module-level docstring and returns its
    first paragraph as a cleaned-up summary.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        
        tree = ast.parse(source)
        docstring = ast.get_docstring(tree)

        if not docstring:
            return ""

        # Clean up the docstring: remove leading/trailing whitespace and dedent.
        cleaned_docstring = textwrap.dedent(docstring).strip()
        
        # The summary consists of the first one or two paragraphs.
        paragraphs = cleaned_docstring.split('\n\n')
        summary = " ".join(paragraphs[:2])
        
        # Normalize internal whitespace to single spaces.
        return " ".join(summary.replace('\n', ' ').split())
        
    except (IOError, SyntaxError):
        # Fail gracefully if file can't be read or parsed.
        return ""


def main():
    """Main function to parse arguments and print the docstring summary."""
    parser = argparse.ArgumentParser(description="Extract the summary from a Python script's docstring.")
    parser.add_argument("file_path", help="The path to the Python script.")
    args = parser.parse_args()
    
    summary = get_docstring_summary(args.file_path)
    if summary:
        print(summary)


if __name__ == "__main__":
    main()

# === End of scripts/analysis/get_docstring_summary.py ===


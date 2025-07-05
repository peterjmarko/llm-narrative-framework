#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/build_docs.py

import os
import re
import subprocess
import sys

def main():
    """
    Builds the final README.md and README.rtf from the template.
    This script is intended to be run as a pre-commit hook.
    """
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        template_path = os.path.join(project_root, 'README.template.md')
        md_output_path = os.path.join(project_root, 'README.md')
        rtf_output_path = os.path.join(project_root, 'README.rtf')
        
        print(f"Reading template from: {template_path}")
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
            
        # --- Part 1: Build README.md ---
        placeholders = re.findall(r'\{\{(.*?)\}\}', template_content)
        final_md_content = template_content
        
        if placeholders:
            for placeholder in placeholders:
                file_to_inject_path = os.path.join(project_root, placeholder)
                if os.path.exists(file_to_inject_path):
                    with open(file_to_inject_path, 'r', encoding='utf-8') as f_diag:
                        diagram_content = f_diag.read()
                    final_md_content = final_md_content.replace(f'{{{{{placeholder}}}}}', diagram_content, 1)
                else:
                    print(f"    - WARNING: Placeholder file not found at: {file_to_inject_path}")

        print(f"Writing final Markdown to: {md_output_path}")
        with open(md_output_path, 'w', encoding='utf-8') as f_out:
            f_out.write(final_md_content)
            
        print("README.md has been successfully built!")

        # --- Part 2: Convert all target markdown files to RTF ---
        print("\n--- Starting RTF Conversion ---")
        try:
            import pypandoc

            # List of markdown files in the project root to convert to RTF
            files_to_convert = ['README.md', 'CONTRIBUTING.md']

            for md_filename in files_to_convert:
                source_md_path = os.path.join(project_root, md_filename)
                output_rtf_path = os.path.join(project_root, md_filename.replace('.md', '.rtf'))

                if not os.path.exists(source_md_path):
                    print(f"WARNING: Source file '{source_md_path}' not found. Skipping RTF conversion for this file.")
                    continue
                
                print(f"Attempting to convert '{md_filename}' to RTF...")
                pypandoc.convert_file(
                    source_md_path,
                    'rtf',
                    outputfile=output_rtf_path
                )
                print(f"Successfully built '{os.path.basename(output_rtf_path)}'!")

        except ImportError:
            print("\n--- DEPENDENCY ERROR ---")
            print("The 'pypandoc' package is not installed.")
            print("Please run 'pdm install -G dev' to install development dependencies.")
            print("Skipping all RTF generation.")
        except OSError:
            # pypandoc raises an OSError if the pandoc executable is not found.
            print("\n--- PANDOC NOT FOUND ---")
            print("The 'pandoc' command was not found on your system.")
            print("Please install Pandoc from https://pandoc.org/installing.html and ensure it's in your system's PATH.")
            print("Skipping all RTF generation.")

    except Exception as e:
        print(f"\nAn unexpected error occurred during the build process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/build_docs.py ===
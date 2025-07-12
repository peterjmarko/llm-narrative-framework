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
# Filename: src/build_docs.py

import os
import re
import subprocess
import sys
import argparse
import time

# ANSI color codes for better terminal output
class Colors:
    RED = '\033[91m'      # Bright Red
    GREEN = '\033[92m'    # Bright Green
    YELLOW = '\033[93m'   # Yellow
    CYAN = '\033[96m'     # Bright Cyan
    RESET = '\033[0m'     # Resets the color to default
    BOLD = '\033[1m'      # Bold text


def render_mermaid_diagram(source_path, output_path, project_root, scale='1.8'):
    """Renders a .md file to a .png using the local mmdc CLI."""
    mmdc_executable = os.path.join(project_root, 'node_modules', '.bin', 'mmdc')
    if sys.platform == "win32":
        mmdc_executable += ".cmd"

    filename = os.path.basename(source_path)
    if not os.path.exists(mmdc_executable):
        print(f"    - {Colors.RED}ERROR: Local Mermaid CLI not found. Did you run 'npm install'?{Colors.RESET}")
        return False
    
    print(f"    - Rendering Mermaid diagram: {Colors.CYAN}{filename}{Colors.RESET}")
    try:
        config_path = os.path.join(project_root, 'docs', 'mermaid-config.json')
        puppeteer_config_path = os.path.join(project_root, 'docs', 'puppeteer-config.json')

        subprocess.run(
            [mmdc_executable, '-i', source_path, '-o', output_path, '-c', config_path, '-p', puppeteer_config_path, '--scale', str(scale)],
            check=True, capture_output=True, text=True, encoding='utf-8'
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"    - {Colors.RED}ERROR: mmdc command failed for {Colors.CYAN}{filename}{Colors.RESET}.")
        if e.stderr: print(f"{Colors.YELLOW}      STDERR from mmdc:\n---\n{e.stderr.strip()}\n---{Colors.RESET}")
        return False

def render_text_diagram(source_path, output_path, project_root, font_size=36):
    """Renders a .txt file to a .png using Pillow with a specified font size."""
    filename = os.path.basename(source_path)
    print(f"    - Rendering Text diagram: {Colors.CYAN}{filename}{Colors.RESET} with font size {font_size}...")
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print(f"    - {Colors.RED}ERROR: 'Pillow' is not installed in the PDM environment.{Colors.RESET}")
        return False

    padding, line_spacing = 20, 4
    # The font_size is now passed in as an argument.

    font_paths = ["Consolas", "cour.ttf", "Courier New", "Menlo", "DejaVu Sans Mono"]
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except IOError:
            continue
    if not font: font = ImageFont.load_default()

    with open(source_path, 'r', encoding='utf-8') as f: lines = f.read().splitlines()
    if not lines: return False
    
    bbox = font.getbbox("M")
    char_width, char_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    img_width = int(max(len(line) for line in lines) * char_width) + (padding * 2)
    img_height = int(len(lines) * (char_height + line_spacing)) + (padding * 2)

    image = Image.new("RGBA", (img_width, img_height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    y = padding
    for line in lines:
        draw.text((padding, y), line, font=font, fill=(0, 0, 0, 255))
        y += char_height + line_spacing
    
    image.save(output_path, "PNG")
    return True

def build_readme_content(project_root):
    """
    Builds the full DOCUMENTATION.md content by processing the template,
    injecting diagram placeholders and including other files.
    """
    template_path = os.path.join(project_root, 'docs/DOCUMENTATION.template.md')
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # --- Process diagram placeholders ---
    # {{diagram:path/to/diagram.mmd}}
    # Locate this function inside the build_readme_content function
    def replace_diagram_placeholder(match):
        diagram_source_rel_path = match.group(1).strip()
        attributes_str = match.group(2)

        pandoc_attributes = ""
        if attributes_str:
            # Pass through width/etc but remove our custom scale attribute
            cleaned_attrs = re.sub(r'scale=([\d\.]+)', '', attributes_str)
            cleaned_attrs = re.sub(r'\|\s*\|', '|', cleaned_attrs).strip(' |')
            if cleaned_attrs:
                pandoc_attributes = f"{{{cleaned_attrs}}}"
        
        base_name = os.path.splitext(os.path.basename(diagram_source_rel_path))[0]
        # Use a forward-slash path, which markdown prefers
        image_rel_path = f"docs/images/{base_name}.png"
        
        # This is the key: a simple, captionless Markdown image.
        # Our Lua filter will find and center this.
        return f"![]({image_rel_path}){pandoc_attributes}"

    
    # Updated regex to capture the optional attribute part after a pipe |
    content = re.sub(r'\{\{diagram:(.*?)(?:\|(.*?))?\}\}', replace_diagram_placeholder, content)

    # --- Process include placeholders ---
    # {{include:path/to/file.txt}}
    def replace_include_placeholder(match):
        include_rel_path = match.group(1)
        include_abs_path = os.path.join(project_root, include_rel_path)
        try:
            with open(include_abs_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return f"ERROR: Included file not found at '{include_rel_path}'"
            
    content = re.sub(r'\{\{include:(.*?)\}\}', replace_include_placeholder, content)

    return content


def render_all_diagrams(project_root):
    """Renders all diagrams found in the template, returning True on success."""
    template_path = os.path.join(project_root, 'docs/DOCUMENTATION.template.md')
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"\n{Colors.BOLD}{Colors.CYAN}--- Processing Diagrams ---{Colors.RESET}")
    images_dir = os.path.join(project_root, 'docs', 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    all_diagrams_ok = True
    for placeholder in re.finditer(r'\{\{diagram:(.*?)(?:\|(.*?))?\}\}', content):
        diagram_source_rel_path = placeholder.group(1).strip()
        base_name = os.path.splitext(os.path.basename(diagram_source_rel_path))[0]
        image_rel_path = os.path.join('docs', 'images', f"{base_name}.png")
        
        attributes_str = placeholder.group(2) or ""
        
        if diagram_source_rel_path.endswith('.mmd'):
            scale_match = re.search(r'scale=([\d\.]+)', attributes_str)
            scale = scale_match.group(1) if scale_match else '1.8' # default in function
            
            if not render_mermaid_diagram(
                os.path.join(project_root, diagram_source_rel_path), 
                os.path.join(project_root, image_rel_path), 
                project_root, 
                scale=scale
            ):
                all_diagrams_ok = False
        elif diagram_source_rel_path.endswith('.txt'):
            font_size = 22 if 'replication_report_format' in diagram_source_rel_path else 20 if 'analysis_log_format' in diagram_source_rel_path else 36
            if not render_text_diagram(os.path.join(project_root, diagram_source_rel_path), os.path.join(project_root, image_rel_path), project_root, font_size=font_size):
                all_diagrams_ok = False
    
    if not all_diagrams_ok:
        print(f"\n{Colors.RED}{Colors.BOLD}--- BUILD FAILED: One or more diagrams could not be rendered. ---{Colors.RESET}")
    
    return all_diagrams_ok

def convert_to_docx(pypandoc, source_md_path, output_docx_path, project_root):
    """
    Converts a single markdown file to DOCX, with specific error handling
    for file-in-use permission errors and missing pandoc installations.
    """
    source_filename = os.path.basename(source_md_path)
    output_filename = os.path.basename(output_docx_path)

    print(f"    - Converting '{Colors.CYAN}{source_filename}{Colors.RESET}' to DOCX...")
    
    permission_error_printed = False
    while True:
        try:
            extra_args = ['--standalone', '--resource-path', project_root]
            pypandoc.convert_file(
                source_md_path, 'docx',
                outputfile=output_docx_path,
                extra_args=extra_args
            )
            
            if permission_error_printed:
                # Add a newline for cleaner output after the waiting message
                print(f"      {Colors.GREEN}File unlocked. Resuming...{Colors.RESET}")
            
            print(f"      {Colors.GREEN}Successfully built '{Colors.CYAN}{output_filename}{Colors.GREEN}'!{Colors.RESET}")
            return True

        except RuntimeError as e:
            if "permission denied" in str(e).lower():
                if not permission_error_printed:
                    print(f"      {Colors.YELLOW}[WAITING] Could not write to '{output_filename}'.")
                    print(f"      The file is likely open in another program (e.g., Microsoft Word).")
                    print(f"      Please close the file. The script will retry automatically... (Ctrl+C to cancel){Colors.RESET}")
                    permission_error_printed = True
                time.sleep(2)  # Wait for 2 seconds before retrying
                continue
            else:
                print(f"\n{Colors.RED}[ERROR] An unexpected error occurred with Pandoc.{Colors.RESET}")
                raise e
        
        except FileNotFoundError:
            print(f"{Colors.RED}\n[ERROR] `pandoc` command not found.")
            print("Please ensure Pandoc is installed and accessible in your system's PATH.")
            print(f"See: https://pandoc.org/installing.html{Colors.RESET}")
            return False
            
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Build cancelled by user.{Colors.RESET}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Builds project documentation from templates.")
    parser.add_argument('--check', action='store_true', help="Check if docs are up-to-date without modifying files.")
    args = parser.parse_args()
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    readme_path = os.path.join(project_root, 'docs/DOCUMENTATION.md')

    expected_readme_content = build_readme_content(project_root)

    if args.check:
        print(f"{Colors.BOLD}{Colors.CYAN}--- Checking if DOCUMENTATION.md is up-to-date... ---{Colors.RESET}")
        try:
            with open(readme_path, 'r', encoding='utf-8') as f:
                current_readme_content = f.read()
        except FileNotFoundError:
            current_readme_content = ""

        if current_readme_content != expected_readme_content:
            print(f"{Colors.RED}ERROR: DOCUMENTATION.md is out of date. Please run 'pdm run build-docs' and commit the changes.{Colors.RESET}")
            sys.exit(1)
        else:
            print(f"{Colors.GREEN}SUCCESS: DOCUMENTATION.md is up-to-date.{Colors.RESET}")
            sys.exit(0)

    # --- Full Build Mode ---
    if not render_all_diagrams(project_root):
        sys.exit(1)

    print(f"\n{Colors.BOLD}{Colors.CYAN}--- Building Final Markdown ---{Colors.RESET}")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(expected_readme_content)
    print(f"{Colors.GREEN}Successfully built DOCUMENTATION.md!{Colors.RESET}")

    print(f"\n{Colors.BOLD}{Colors.CYAN}--- Starting DOCX Conversion ---{Colors.RESET}")
    try:
        import pypandoc
        
        readme_md = os.path.join(project_root, 'docs/DOCUMENTATION.md')
        readme_docx = os.path.join(project_root, 'docs/DOCUMENTATION.docx')
        if not convert_to_docx(pypandoc, readme_md, readme_docx, project_root):
            sys.exit(1)
        
        contrib_md = os.path.join(project_root, 'docs/CONTRIBUTING.md')
        if os.path.exists(contrib_md):
            contrib_docx = os.path.join(project_root, 'docs/CONTRIBUTING.docx')
            if not convert_to_docx(pypandoc, contrib_md, contrib_docx, project_root):
                sys.exit(1)
        
        print(f"\n{Colors.GREEN}{Colors.BOLD}All documents built successfully.{Colors.RESET}")

    except ImportError:
        print(f"{Colors.YELLOW}--- DEPENDENCY WARNING: 'pypandoc' not found. Skipping DOCX generation. ---{Colors.RESET}")

if __name__ == "__main__":
    main()

# === End of src/build_docs.py ===

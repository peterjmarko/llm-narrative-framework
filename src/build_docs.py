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

"""
Builds all project documentation from source templates and diagrams.

This script is the central engine for generating the project's documentation.
It takes `docs/DOCUMENTATION.template.md` as its primary input, processes
custom placeholders, renders diagrams, and outputs the final `DOCUMENTATION.md`
and `.docx` files.

Key Features:
-   **Template Processing**: Parses `{{diagram:...}}` and `{{include:...}}`
    placeholders within the template file.

-   **Diagram Rendering**:
    -   Renders Mermaid (`.mmd`) diagrams to PNG using the local `mmdc` CLI.
    -   Renders text-based (`.txt`) diagrams to PNG using the Pillow library.

-   **Intelligent Caching**: Skips rendering diagrams if the output image file
    is newer than the source diagram file, speeding up subsequent builds.

-   **Force Re-render**: Accepts a `--force-render` flag to override the cache
    and regenerate all diagrams.

-   **Dual-Syntax Generation**: To ensure compatibility with different renderers,
    it generates two versions of the documentation content in memory:
    1.  For `.md` viewers (GitHub, VS Code): Uses HTML `<img>` tags for
        universal compatibility with attributes like `width`.
    2.  For `.docx` conversion: Uses Pandoc-native `![](){...}` attribute
        syntax for correct image sizing in the final document.

-   **Resilient DOCX Conversion**: When converting to `.docx` via Pandoc, it
    includes a retry loop that waits for locked files (e.g., open in Word)
    to be closed instead of failing immediately.

Usage:
    # Standard build (uses cache)
    pdm run build-docs

    # Force a full rebuild of all diagrams
    pdm run build-docs --force-render
"""

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

def check_diagrams_are_up_to_date(project_root):
    """
    Performs a read-only check to see if diagram images are up-to-date.
    Returns True if all diagrams are current, False otherwise.
    """
    template_path = os.path.join(project_root, 'docs/DOCUMENTATION.template.md')
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"{Colors.RED}ERROR: Template file not found at {template_path}{Colors.RESET}")
        return False

    all_up_to_date = True
    for placeholder in re.finditer(r'\{\{diagram:(.*?)(?:\|(.*?))?\}\}', content):
        diagram_source_rel_path = placeholder.group(1).strip()
        base_name = os.path.splitext(os.path.basename(diagram_source_rel_path))[0]
        image_rel_path = os.path.join('docs', 'images', f"{base_name}.png")
        
        source_abs_path = os.path.join(project_root, diagram_source_rel_path)
        image_abs_path = os.path.join(project_root, image_rel_path)

        if not os.path.exists(image_abs_path):
            print(f"    - {Colors.RED}MISSING:{Colors.RESET} {image_rel_path} (source: {diagram_source_rel_path})")
            all_up_to_date = False
            continue

        try:
            source_mtime = os.path.getmtime(source_abs_path)
            image_mtime = os.path.getmtime(image_abs_path)
            if source_mtime > image_mtime:
                print(f"    - {Colors.RED}OUTDATED:{Colors.RESET} {image_rel_path} (source: {diagram_source_rel_path})")
                all_up_to_date = False
        except FileNotFoundError:
             print(f"    - {Colors.YELLOW}WARNING: Source file not found for check: {diagram_source_rel_path}.{Colors.RESET}")
             all_up_to_date = False
    
    return all_up_to_date

def build_readme_content(project_root, flavor='viewer'):
    """
    Builds the full DOCUMENTATION.md content by processing the template,
    injecting diagram placeholders and including other files.
    """
    template_path = os.path.join(project_root, 'docs/DOCUMENTATION.template.md')
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # --- Process diagram placeholders ---
    # {{diagram:path/to/diagram.mmd}}
    def replace_diagram_placeholder(match, flavor='viewer'):
        diagram_source_rel_path = match.group(1).strip()
        attributes_str = match.group(2) or ""

        # Path must be relative to DOCUMENTATION.md, which is in the docs/ dir
        base_name = os.path.splitext(os.path.basename(diagram_source_rel_path))[0]
        image_rel_path = f"images/{base_name}.png"
        
        # Parse attributes like 'width=110%' into a dictionary
        attr_dict = {}
        if attributes_str:
            pairs = [p.strip() for p in attributes_str.split('|')]
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    attr_dict[key.strip().lower()] = value.strip()

        if flavor == 'pandoc':
            # For DOCX: Generate Pandoc-style attributes string, e.g., {width="110%"}
            pandoc_attr_parts = [f'{k}="{v}"' for k, v in attr_dict.items() if k != 'scale']
            pandoc_attributes = "{" + " ".join(pandoc_attr_parts) + "}" if pandoc_attr_parts else ""
            # Pandoc syntax does not use a space before the attributes
            return f"![]({image_rel_path}){pandoc_attributes}"
        else: # 'viewer' flavor
            # For MD viewers: Generate a standard HTML <img> tag, which works everywhere.
            html_attrs_parts = [f'{k}="{v}"' for k, v in attr_dict.items() if k != 'scale']
            html_attrs = " ".join(html_attrs_parts)
            # Center the image using a div container
            return f'<div align="center">\n  <img src="{image_rel_path}" {html_attrs.strip()}>\n</div>'

    
    # Updated regex to capture the optional attribute part after a pipe |
    # Use a lambda to pass the 'flavor' parameter to the placeholder function
    content = re.sub(r'\{\{diagram:(.*?)(?:\|(.*?))?\}\}', 
                     lambda m: replace_diagram_placeholder(m, flavor=flavor), 
                     content)

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


def render_all_diagrams(project_root, force_render=False):
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
        
        source_abs_path = os.path.join(project_root, diagram_source_rel_path)
        image_abs_path = os.path.join(project_root, image_rel_path)
        
        should_render = False
        if force_render:
            should_render = True
        elif not os.path.exists(image_abs_path):
            should_render = True
        else:
            try:
                source_mtime = os.path.getmtime(source_abs_path)
                image_mtime = os.path.getmtime(image_abs_path)
                if source_mtime > image_mtime:
                    should_render = True
                else:
                    print(f"    - Skipping {Colors.CYAN}{os.path.basename(diagram_source_rel_path)}{Colors.RESET} (up-to-date)")
            except FileNotFoundError:
                print(f"    - {Colors.YELLOW}WARNING: Source file not found for comparison: {diagram_source_rel_path}. Will attempt to render.{Colors.RESET}")
                should_render = True

        if should_render:
            attributes_str = placeholder.group(2) or ""
            if diagram_source_rel_path.endswith('.mmd'):
                scale_match = re.search(r'scale=([\d\.]+)', attributes_str)
                scale = scale_match.group(1) if scale_match else '1.8'
                if not render_mermaid_diagram(source_abs_path, image_abs_path, project_root, scale=scale):
                    all_diagrams_ok = False
            elif diagram_source_rel_path.endswith('.txt'):
                font_size = 22 if 'replication_report_format' in diagram_source_rel_path else 20 if 'analysis_log_format' in diagram_source_rel_path else 36
                if not render_text_diagram(source_abs_path, image_abs_path, project_root, font_size=font_size):
                    all_diagrams_ok = False

    if not all_diagrams_ok:
        print(f"\n{Colors.RED}{Colors.BOLD}--- BUILD FAILED: One or more diagrams could not be rendered. ---{Colors.RESET}")
    
    return all_diagrams_ok

def convert_to_docx(pypandoc, output_docx_path, project_root, source_md_path=None, source_md_content=None):
    """
    Converts a markdown source (from file OR string) to DOCX, with robust error handling.
    """
    if not source_md_path and not source_md_content:
        print(f"{Colors.RED}ERROR: convert_to_docx requires either a source_md_path or source_md_content.{Colors.RESET}")
        return False

    # Determine a logical filename for logging messages
    logical_source_name = os.path.basename(source_md_path) if source_md_path else os.path.basename(output_docx_path).replace('.docx', '.md')
    output_filename = os.path.basename(output_docx_path)
    
    # Base the resource path on the *output* file's location. This is more reliable.
    if 'docs' in os.path.normpath(output_docx_path):
        resource_path = os.path.join(project_root, 'docs')
    else:
        resource_path = project_root

    print(f"    - Converting '{Colors.CYAN}{logical_source_name}{Colors.RESET}' to DOCX...")
    
    permission_error_printed = False
    while True:
        try:
            extra_args = ['--standalone', '--resource-path', resource_path]
            
            # Use the correct pypandoc function based on the provided source
            if source_md_content:
                pypandoc.convert_text(
                    source_md_content, 'docx', format='md',
                    outputfile=output_docx_path,
                    extra_args=extra_args
                )
            else: # source_md_path must exist
                pypandoc.convert_file(
                    source_md_path, 'docx',
                    outputfile=output_docx_path,
                    extra_args=extra_args
                )
            
            if permission_error_printed:
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
                time.sleep(2)
                continue
            else:
                print(f"\n{Colors.RED}[ERROR] An unexpected error occurred with Pandoc.{Colors.RESET}")
                raise e
        
        except FileNotFoundError:
            print(f"{Colors.RED}\n[ERROR] `pandoc` command not found. See: https://pandoc.org/installing.html{Colors.RESET}")
            return False
            
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Build cancelled by user.{Colors.RESET}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Builds project documentation from templates.")
    parser.add_argument('--check', action='store_true', help="Check if docs are up-to-date without modifying files.")
    parser.add_argument('--force-render', action='store_true', help="Force re-rendering of all diagrams, ignoring timestamps.")
    args = parser.parse_args()
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    if args.check:
        print(f"{Colors.BOLD}{Colors.CYAN}--- Checking if documentation is up-to-date... ---{Colors.RESET}")
        
        diagrams_ok = check_diagrams_are_up_to_date(project_root)
        
        readme_path = os.path.join(project_root, 'docs/DOCUMENTATION.md')
        expected_viewer_content = build_readme_content(project_root, flavor='viewer')
        try:
            with open(readme_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
        except FileNotFoundError:
            print(f"    - {Colors.RED}MISSING:{Colors.RESET} docs/DOCUMENTATION.md")
            diagrams_ok = False # Missing doc file is a failure state
            current_content = ""

        content_ok = (current_content == expected_viewer_content)
        if not content_ok and os.path.exists(readme_path):
            print(f"    - {Colors.RED}OUTDATED:{Colors.RESET} docs/DOCUMENTATION.md content does not match template.")

        if diagrams_ok and content_ok:
            print(f"{Colors.GREEN}Documentation is up-to-date.{Colors.RESET}")
            sys.exit(0)
        else:
            print(f"\n{Colors.RED}Documentation is out of date. Please run 'pdm run build-docs' and commit the changes.{Colors.RESET}")
            sys.exit(1)

    # --- Build Mode (if not --check) ---
    if not render_all_diagrams(project_root, force_render=args.force_render):
        sys.exit(1)

    print(f"\n{Colors.BOLD}{Colors.CYAN}--- Building Markdown for Viewers ---{Colors.RESET}")
    viewer_content = build_readme_content(project_root, flavor='viewer')
    readme_path = os.path.join(project_root, 'docs/DOCUMENTATION.md')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(viewer_content)
    print(f"{Colors.GREEN}Successfully built DOCUMENTATION.md!{Colors.RESET}")

    print(f"\n{Colors.BOLD}{Colors.CYAN}--- Building Content for DOCX Conversion ---{Colors.RESET}")
    try:
        import pypandoc
        pandoc_content = build_readme_content(project_root, flavor='pandoc')
        
        readme_docx = os.path.join(project_root, 'docs/DOCUMENTATION.docx')
        if not convert_to_docx(pypandoc, readme_docx, project_root, source_md_content=pandoc_content):
            sys.exit(1)
        
        contrib_md_path = os.path.join(project_root, 'docs/CONTRIBUTING.md')
        if os.path.exists(contrib_md_path):
            contrib_docx_path = os.path.join(project_root, 'docs/CONTRIBUTING.docx')
            if not convert_to_docx(pypandoc, contrib_docx_path, project_root, source_md_path=contrib_md_path):
                sys.exit(1)
        
        print(f"\n{Colors.GREEN}{Colors.BOLD}All documents built successfully.{Colors.RESET}")

    except ImportError:
        print(f"{Colors.YELLOW}--- DEPENDENCY WARNING: 'pypandoc' not found. Skipping DOCX generation. ---{Colors.RESET}")

if __name__ == "__main__":
    main()

# === End of src/build_docs.py ===

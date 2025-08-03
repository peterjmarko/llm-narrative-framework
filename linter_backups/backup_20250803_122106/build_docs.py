#!/usr/bin/env python3
#-*- coding: utf-8 -*-
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

-   **Pre-commit Hook Integration**: Includes a `--check` mode that performs a
    read-only verification to ensure documentation is up-to-date without
    modifying files, ideal for CI/CD pipelines.

-   **Dual-Syntax Generation**: To ensure compatibility with different renderers,
    it generates two versions of the documentation content in memory:
    1.  For `.md` viewers (GitHub, VS Code): Uses HTML `<img>` tags for
        universal compatibility with attributes like `width`.
    2.  For `.docx` conversion: Uses Pandoc-native `![](){...}` attribute
        syntax for correct image sizing in the final document.

-   **Resilient DOCX Conversion**: When converting to `.docx` via Pandoc, it
    includes a retry loop that waits for locked files (e.g., open in Word)
    to be closed instead of failing immediately.

-   **DOCX Post-Processing**: Calls a helper script (`docx_postprocessor.py`)
    to reliably insert page breaks into the final `.docx` files, overcoming
    Pandoc rendering inconsistencies.

Usage:
    # Standard build (uses cache)
    pdm run build-docs

    # Force a full rebuild of all diagrams
    pdm run build-docs --force-render
"""

import os
import re
import shutil
import subprocess
import sys
import argparse
import time

# Add the script's own directory ('src') to the Python path.
# This ensures that sibling modules (like docx_postprocessor) can be imported
# when this script is run from the project root.
# Add the script's directory to the Python path to ensure local imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import docx_postprocessor # Import for post-processing DOCX files

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

    font = None
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

def process_markdown_content(content, project_root, flavor='viewer'):
    """
    Processes a string of markdown content, replacing custom placeholders for
    diagrams, figures, includes, and page breaks.
    """
    # --- Helper for diagram-related paths ---
    def _get_diagram_paths(diagram_source_rel_path):
        base_name = os.path.splitext(os.path.basename(diagram_source_rel_path))[0]
        viewer_image_path = f"images/{base_name}.png"
        pandoc_image_path = f"images/{base_name}.png" # For Pandoc's native image syntax (relative to docs/)
        return viewer_image_path, pandoc_image_path

    # --- Function to render a single diagram's Markdown or return raw path/attrs ---
    # This will be called both by the main re.sub for {{diagram:}} and internally by {{grouped_figure:}}
    def _render_single_diagram(diagram_source_rel_path, attributes_str, current_flavor, raw_pandoc_info_only=False):
        viewer_image_path, pandoc_image_path = _get_diagram_paths(diagram_source_rel_path)

        attr_dict = {}
        if attributes_str:
            pairs = [p.strip() for p in attributes_str.split('|')]
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    attr_dict[key.strip().lower()] = value.strip()

        pandoc_attr_parts = [f'{k}="{v}"' for k, v in attr_dict.items() if k != 'scale']
        pandoc_attributes_string = "{" + " ".join(pandoc_attr_parts) + "}" if pandoc_attr_parts else ""

        if raw_pandoc_info_only:
            # For internal use by grouped_figure, return path and attribute string
            return pandoc_image_path, pandoc_attributes_string

        if current_flavor == 'pandoc':
            return f"![]({pandoc_image_path}){pandoc_attributes_string}"
        else: # 'viewer' flavor
            html_attrs_parts = [f'{k}="{v}"' for k, v in attr_dict.items() if k != 'scale']
            html_attrs = " ".join(html_attrs_parts)
            return f'<div align="center">\n  <img src="{viewer_image_path}" {html_attrs.strip()}>\n</div>'

    # --- Process {{grouped_figure:...}} placeholders FIRST ---
    # {{grouped_figure:diagram_path|attr1=val1|caption=Caption Text}}
    def replace_grouped_figure_placeholder(match):
        current_flavor = flavor # Use the outer 'flavor'
        full_spec = match.group(1).strip()
        
        # Split by the first ' | caption=' to separate diagram_info from actual caption
        diagram_info_part, *caption_part_list = re.split(r'\s*\|\s*caption=', full_spec, 1)

        # Parse diagram info and attributes
        diagram_parts = [p.strip() for p in diagram_info_part.split('|')]
        diagram_source_rel_path = diagram_parts[0]
        
        attr_dict = {}
        for part in diagram_parts[1:]:
            if '=' in part:
                key, value = part.split('=', 1)
                attr_dict[key.strip().lower()] = value.strip()
        
        caption_text = caption_part_list[0] if caption_part_list else ""

        # Render the nested diagram using the helper function to get raw path and attributes.
        diagram_specific_attrs = '|'.join([f'{k}={v}' for k, v in attr_dict.items() if k not in ['caption']])
        
        # Call _render_single_diagram with the new flag to get path and attributes string, not full ![]()
        diagram_image_path, diagram_attributes_string = _render_single_diagram(diagram_source_rel_path, diagram_specific_attrs, current_flavor='pandoc', raw_pandoc_info_only=True)

        if current_flavor == 'pandoc':
            # For DOCX, combine caption (markdown) and image into Pandoc's native figure syntax.
            # The URL part of the outer figure is the image path, followed by attributes for the figure.
            return f"![{caption_text}]({diagram_image_path}){diagram_attributes_string}"
        else: # viewer flavor
            # For MD viewers, render as an HTML block for center alignment and clarity.
            html_attrs_parts = [f'{k}="{v}"' for k, v in attr_dict.items() if k not in ['scale', 'caption']]
            html_attrs = " ".join(html_attrs_parts)
            
            clean_caption = re.sub(r'^\s*#+\s*', '', caption_text, flags=re.MULTILINE)
            viewer_image_path, _ = _get_diagram_paths(diagram_source_rel_path)

            return f'<div align="center">\n  <p>{clean_caption}</p>\n  <img src="{viewer_image_path}" {html_attrs.strip()}>\n</div>'

    # Process grouped_figure FIRST to ensure its internal diagram is handled before main diagram re.sub
    content = re.sub(r'\{\{grouped_figure:(.*?)\}\}', 
                     replace_grouped_figure_placeholder, 
                     content, flags=re.DOTALL) # Ensure DOTALL is here

    # --- Process standalone {{diagram:...}} placeholders ---
    # These will only be processed if they are NOT inside a {{grouped_figure}}
    def replace_standalone_diagram_placeholder(match):
        return _render_single_diagram(match.group(1), match.group(2) or "", flavor)

    content = re.sub(r'\{\{diagram:(.*?)(?:\|(.*?))?\}\}', 
                     replace_standalone_diagram_placeholder, 
                     content)

    # --- Process {{include:...}} placeholders ---
    def replace_include_placeholder(match):
        include_rel_path = match.group(1)
        include_abs_path = os.path.join(project_root, include_rel_path)
        try:
            with open(include_abs_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return f"ERROR: Included file not found at '{include_rel_path}'"
            
    content = re.sub(r'\{\{include:(.*?)\}\}', replace_include_placeholder, content)

    # --- Process {{pagebreak}} placeholders ---
    # This generates a unique marker that can be found and replaced by a post-processor.
    def replace_pagebreak_placeholder(match):
        if flavor == 'pandoc':
            return '\n---PAGEBREAK---\n' # Unique marker for post-processing
        else:
            return ''

    content = re.sub(r'\{\{pagebreak\}\}', replace_pagebreak_placeholder, content)

    return content

def build_readme_content(project_root, flavor='viewer'):
    """
    Builds the full DOCUMENTATION.md content by processing the template.
    This is a convenience wrapper around process_markdown_content.
    """
    template_path = os.path.join(project_root, 'docs/DOCUMENTATION.template.md')
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return process_markdown_content(content, project_root, flavor)

def render_all_diagrams(project_root, force_render=False, template_files=None):
    """
    Scans all specified template files for diagram placeholders, then renders
    or copies them as needed. Returns True on success.
    """
    if template_files is None:
        template_files = ['docs/DOCUMENTATION.template.md']

    print(f"\n{Colors.BOLD}{Colors.CYAN}--- Processing Diagrams ---{Colors.RESET}")
    
    content_to_scan = ""
    for file_rel_path in template_files:
        try:
            with open(os.path.join(project_root, file_rel_path), 'r', encoding='utf-8') as f:
                content_to_scan += f.read() + "\n"
        except FileNotFoundError:
            print(f"    - {Colors.YELLOW}WARNING: Template file for diagram scan not found: {file_rel_path}{Colors.RESET}")

    content = content_to_scan
    images_dir = os.path.join(project_root, 'docs', 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    diagrams_to_render = set() # Store (source_path, attributes_str) tuples to avoid duplicates

    # Find standalone {{diagram:...}} placeholders
    for placeholder in re.finditer(r'\{\{diagram:(.*?)(?:\|(.*?))?\}\}', content):
        diagram_source_rel_path = placeholder.group(1).strip()
        attributes_str = placeholder.group(2) or ""
        diagrams_to_render.add((diagram_source_rel_path, attributes_str))

    # Find diagrams inside {{grouped_figure:...}} placeholders
    # Need to parse the full spec to extract the diagram_source_rel_path and its attributes
    for placeholder in re.finditer(r'\{\{grouped_figure:(.*?)\}\}', content, flags=re.DOTALL):
        full_spec = placeholder.group(1).strip()
        
        # This parsing logic reuses the attribute extraction from build_readme_content
        diagram_info_part, *caption_part_list = re.split(r'\s*\|\s*caption=', full_spec, 1)
        diagram_parts = [p.strip() for p in diagram_info_part.split('|')]
        diagram_source_rel_path = diagram_parts[0]
        
        # Reconstruct attributes string from diagram_parts[1:] for rendering purposes
        attr_dict = {}
        for part in diagram_parts[1:]:
            if '=' in part:
                key, value = part.split('=', 1)
                attr_dict[key.strip().lower()] = value.strip()
        reconstructed_attributes_str = '|'.join([f'{k}={v}' for k,v in attr_dict.items()])

        diagrams_to_render.add((diagram_source_rel_path, reconstructed_attributes_str))
        
    all_diagrams_ok = True
    for diagram_source_rel_path, attributes_str in diagrams_to_render:
        base_name = os.path.splitext(os.path.basename(diagram_source_rel_path))[0]
        image_abs_path = os.path.join(project_root, 'docs', 'images', f"{base_name}.png")
        source_abs_path = os.path.join(project_root, diagram_source_rel_path)
        
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
                # If source is missing, we must render or it'll fail later.
                should_render = True 

        if should_render:
            if diagram_source_rel_path.endswith('.mmd'):
                scale_match = re.search(r'scale=([\d\.]+)', attributes_str)
                scale = scale_match.group(1) if scale_match else '1.8'
                if not render_mermaid_diagram(source_abs_path, image_abs_path, project_root, scale=scale):
                    all_diagrams_ok = False
            elif diagram_source_rel_path.endswith('.txt'):
                font_size = 22 if 'replication_report_format' in diagram_source_rel_path else 20 if 'analysis_log_format' in diagram_source_rel_path else 36
                if not render_text_diagram(source_abs_path, image_abs_path, project_root, font_size=font_size):
                    all_diagrams_ok = False
            elif diagram_source_rel_path.endswith(('.png', '.jpg', '.jpeg')):
                print(f"    - Copying pre-generated image: {Colors.CYAN}{os.path.basename(diagram_source_rel_path)}{Colors.RESET}")
                try:
                    shutil.copy2(source_abs_path, image_abs_path) # copy2 preserves metadata like mtime
                except FileNotFoundError:
                    print(f"    - {Colors.RED}ERROR: Source image not found at {source_abs_path}{Colors.RESET}")
                    all_diagrams_ok = False
                except Exception as e:
                    print(f"    - {Colors.RED}ERROR: Failed to copy {os.path.basename(diagram_source_rel_path)}: {e}{Colors.RESET}")
                    all_diagrams_ok = False
            else:
                print(f"    - {Colors.YELLOW}WARNING: Unknown diagram type for {Colors.CYAN}{os.path.basename(diagram_source_rel_path)}{Colors.RESET}. Skipping processing.{Colors.RESET}")
    
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

    logical_source_name = os.path.basename(source_md_path) if source_md_path else os.path.basename(output_docx_path).replace('.docx', '.md')
    output_filename = os.path.basename(output_docx_path)
    
    resource_path = os.path.dirname(source_md_path) if source_md_path else os.path.join(project_root, 'docs')

    print(f"    - Converting '{Colors.CYAN}{logical_source_name}{Colors.RESET}' to DOCX...")
    
    permission_error_printed = False
    while True:
        try:
            pandoc_args_base = [
                '--standalone',
                '--resource-path', resource_path,
            ]
            reference_docx_path = os.path.join(project_root, 'docs', 'custom_reference.docx')
            if os.path.exists(reference_docx_path):
                pandoc_args_base.append(f'--reference-doc={reference_docx_path}')

            input_format_with_extensions = 'markdown+latex_macros+raw_attribute'
            final_pandoc_extra_args = ['-f', input_format_with_extensions] + pandoc_args_base
            
            if source_md_content:
                pypandoc.convert_text(
                    source_md_content, 'docx', format='markdown',
                    outputfile=output_docx_path,
                    extra_args=final_pandoc_extra_args
                )
            else:
                pypandoc.convert_file(
                    source_md_path, 'docx', format='markdown',
                    outputfile=output_docx_path,
                    extra_args=final_pandoc_extra_args
                )
            
            if permission_error_printed:
                print(f"      {Colors.GREEN}File unlocked. Resuming...{Colors.RESET}")
            
            print(f"      {Colors.GREEN}Successfully built '{Colors.CYAN}{output_filename}{Colors.GREEN}'!{Colors.RESET}")

            # --- POST-PROCESSING: Insert Page Breaks ---
            try:
                docx_postprocessor.insert_page_breaks_by_marker(output_docx_path, '---PAGEBREAK---')
            except NameError:
                # This will catch if the initial import of docx_postprocessor failed
                print(f"      {Colors.YELLOW}WARNING: docx_postprocessor module not found. Skipping page break insertion.{Colors.RESET}")
            except Exception as e:
                print(f"      {Colors.RED}ERROR during post-processing: {e}{Colors.RESET}")
            # --- END POST-PROCESSING ---

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
            diagrams_ok = False
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

    # Define which files have placeholders that might contain diagrams
    files_with_diagrams = [
        'docs/DOCUMENTATION.template.md',
        'docs/article_main_text.md'
    ]
    if not render_all_diagrams(project_root, force_render=args.force_render, template_files=files_with_diagrams):
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
        
        # --- 1. Convert the main documentation (from in-memory content) ---
        readme_docx_path = os.path.join(project_root, 'docs/DOCUMENTATION.docx')
        if not convert_to_docx(pypandoc, readme_docx_path, project_root, source_md_content=pandoc_content):
            sys.exit(1)
        
        # --- 2. Convert other markdown files, processing placeholders where needed ---
        files_to_convert = {
            "CONTRIBUTING.md": False,
            "CHANGELOG.md": False,
            "LICENSE.md": False,
            "project_scope_report.md": False,
            "docs/article_main_text.md": True,                  # This file may contain placeholders
            "docs/article_supplementary_material.md": True,     # This file may contain placeholders
            "docs/article_cover_letter.md": True                # This file may contain placeholders
        }
        
        for rel_path, process_placeholders in files_to_convert.items():
            source_path = os.path.join(project_root, rel_path)
            if os.path.exists(source_path):
                base_filename = os.path.basename(rel_path)
                output_filename = os.path.splitext(base_filename)[0] + ".docx"
                output_path = os.path.join(project_root, 'docs', output_filename)
                
                content_to_convert = None
                path_to_convert = source_path

                if process_placeholders:
                    with open(source_path, 'r', encoding='utf-8') as f:
                        raw_content = f.read()
                    # Process its content to handle placeholders
                    content_to_convert = process_markdown_content(raw_content, project_root, flavor='pandoc')
                    path_to_convert = None # Ensure we use content, not path

                if not convert_to_docx(pypandoc, output_path, project_root, 
                                       source_md_path=path_to_convert, 
                                       source_md_content=content_to_convert):
                    sys.exit(1)
        
        print(f"\n{Colors.GREEN}{Colors.BOLD}All documents built successfully.{Colors.RESET}")

    except ImportError:
        print(f"{Colors.YELLOW}--- DEPENDENCY WARNING: 'pypandoc' not found. Skipping DOCX generation. ---{Colors.RESET}")

if __name__ == "__main__":
    main()

# === End of src/build_docs.py ===

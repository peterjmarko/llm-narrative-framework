#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/build_docs.py

import os
import re
import subprocess
import sys
import argparse

# ANSI color codes for better terminal output
class Colors:
    RED = '\033[91m'      # Bright Red
    YELLOW = '\033[93m'   # Yellow
    RESET = '\033[0m'     # Resets the color to default


def render_mermaid_diagram(source_path, output_path, project_root):
    """Renders a .md file to a .png using the local mmdc CLI."""
    # Construct the correct path to the executable based on the OS
    mmdc_executable = os.path.join(project_root, 'node_modules', '.bin', 'mmdc')
    if sys.platform == "win32":
        mmdc_executable += ".cmd"  # Use the .cmd script on Windows

    if not os.path.exists(mmdc_executable):
        print("    - ERROR: Local Mermaid CLI not found. Did you run 'npm install'?")
        return False
    
    print(f"    - Rendering Mermaid diagram: {os.path.basename(source_path)}")
    try:
        config_path = os.path.join(project_root, 'docs', 'mermaid-config.json')
        puppeteer_config_path = os.path.join(project_root, 'docs', 'puppeteer-config.json')

        # Use the platform-specific executable path
        # Use the --scale flag for more reliable scaling. 0.8 = 80% of original size.
        result = subprocess.run(
                            [mmdc_executable, '-i', source_path, '-o', output_path, '-c', config_path, '-p', puppeteer_config_path, '--scale', '2'],
            check=True, capture_output=True, text=True, encoding='utf-8'
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"    - ERROR: mmdc command failed for {os.path.basename(source_path)}.")
        if e.stderr: print(f"      STDERR from mmdc:\n---\n{e.stderr.strip()}\n---")
        return False

def render_text_diagram(source_path, output_path, project_root, font_size=36):
    """Renders a .txt file to a .png using Pillow with a specified font size."""
    print(f"    - Rendering Text diagram: {os.path.basename(source_path)} with font size {font_size}...")
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("    - ERROR: 'Pillow' is not installed in the PDM environment.")
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
    """Generates the final README.md content as a string without writing to disk."""
    template_path = os.path.join(project_root, 'README.template.md')
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # This loop just replaces placeholders, it doesn't render diagrams yet.
    for placeholder in re.finditer(r'\{\{diagram:(.*?)\}\}', content):
        diagram_source_rel_path = placeholder.group(1)
        base_name = os.path.splitext(os.path.basename(diagram_source_rel_path))[0]
        image_rel_path = os.path.join('docs', 'images', f"{base_name}.png").replace("\\", "/")
        image_tag = f"![ ]({image_rel_path}){{width=100%}}"
        content = content.replace(placeholder.group(0), image_tag, 1)
    
    return content

def render_all_diagrams(project_root):
    """Renders all diagrams found in the template, returning True on success."""
    template_path = os.path.join(project_root, 'README.template.md')
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print("\n--- Processing Diagrams ---")
    images_dir = os.path.join(project_root, 'docs', 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    all_diagrams_ok = True
    for placeholder in re.finditer(r'\{\{diagram:(.*?)\}\}', content):
        diagram_source_rel_path = placeholder.group(1)
        base_name = os.path.splitext(os.path.basename(diagram_source_rel_path))[0]
        image_rel_path = os.path.join('docs', 'images', f"{base_name}.png")
        
        # Smart Dispatcher Logic
        if diagram_source_rel_path.endswith('.mmd'):
            if not render_mermaid_diagram(os.path.join(project_root, diagram_source_rel_path), os.path.join(project_root, image_rel_path), project_root):
                all_diagrams_ok = False
        elif diagram_source_rel_path.endswith('.txt'):
            font_size = 22 if 'replication_report_format' in diagram_source_rel_path else 20 if 'analysis_log_format' in diagram_source_rel_path else 36
            if not render_text_diagram(os.path.join(project_root, diagram_source_rel_path), os.path.join(project_root, image_rel_path), project_root, font_size=font_size):
                all_diagrams_ok = False
    
    if not all_diagrams_ok:
        print("\n--- BUILD FAILED: One or more diagrams could not be rendered. ---")
    
    return all_diagrams_ok

def convert_to_docx(pypandoc, source_md_path, output_docx_path, project_root):
    """
    Converts a single markdown file to DOCX, with specific error handling
    for file-in-use permission errors and missing pandoc installations.
    """
    print(f"    - Converting '{os.path.basename(source_md_path)}' to DOCX...")
    try:
        pypandoc.convert_file(
            source_md_path, 'docx',
            outputfile=output_docx_path,
            extra_args=['--standalone', '--resource-path', project_root]
        )
        print(f"    - Successfully built '{os.path.basename(output_docx_path)}'!")
        return True
    except RuntimeError as e:
        # Check for the specific "permission denied" error from pandoc
        if "permission denied" in str(e).lower():
            print(f"{Colors.RED}\n[ERROR] Could not write to '{os.path.basename(output_docx_path)}'.")
            print("The file is likely open in another program (e.g., Microsoft Word).")
            print(f"Please close the file and run the script again.{Colors.RESET}")
            return False
        else:
            # For any other pandoc error, raise it so we see the full details
            print(f"\n{Colors.RED}[ERROR] An unexpected error occurred with Pandoc.{Colors.RESET}")
            raise e
    except FileNotFoundError:
        print(f"{Colors.RED}\n[ERROR] `pandoc` command not found.")
        print("Please ensure Pandoc is installed and accessible in your system's PATH.")
        print(f"See: https://pandoc.org/installing.html{Colors.RESET}")
        return False



def main():
    parser = argparse.ArgumentParser(description="Builds project documentation from templates.")
    parser.add_argument('--check', action='store_true', help="Check if docs are up-to-date without modifying files.")
    args = parser.parse_args()
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    readme_path = os.path.join(project_root, 'README.md')

    # Generate the expected content in memory
    expected_readme_content = build_readme_content(project_root)

    if args.check:
        print("--- Checking if README.md is up-to-date... ---")
        try:
            with open(readme_path, 'r', encoding='utf-8') as f:
                current_readme_content = f.read()
        except FileNotFoundError:
            current_readme_content = ""

        if current_readme_content != expected_readme_content:
            print("ERROR: README.md is out of date. Please run 'python -m pdm run build-docs' and commit the changes.")
            sys.exit(1)
        else:
            print("SUCCESS: README.md is up-to-date.")
            sys.exit(0)

    # --- Full Build Mode (if --check is not specified) ---
    if not render_all_diagrams(project_root):
        sys.exit(1)

    print("\n--- Building Final Markdown ---")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(expected_readme_content)
    print("Successfully built README.md!")

    print("\n--- Starting DOCX Conversion ---")
    try:
        import pypandoc
        
        # Convert README.md
        readme_md = os.path.join(project_root, 'README.md')
        readme_docx = os.path.join(project_root, 'README.docx')
        if not convert_to_docx(pypandoc, readme_md, readme_docx, project_root):
            sys.exit(1) # Exit if conversion fails
        
        # Convert CONTRIBUTING.md if it exists
        contrib_md = os.path.join(project_root, 'CONTRIBUTING.md')
        if os.path.exists(contrib_md):
            contrib_docx = os.path.join(project_root, 'CONTRIBUTING.docx')
            if not convert_to_docx(pypandoc, contrib_md, contrib_docx, project_root):
                sys.exit(1) # Exit if conversion fails
        
        print("\nAll documents built successfully.")

    except ImportError:
        print(f"--- {Colors.YELLOW}DEPENDENCY WARNING:{Colors.RESET} 'pypandoc' not found. Skipping DOCX generation.")

if __name__ == "__main__":
    main()

# === End of src/build_docs.py ===
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/build_docs.py

import os
import re
import subprocess
import sys

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

def render_text_diagram(source_path, output_path, project_root):
    """Renders a .txt file to a .png using Pillow."""
    print(f"    - Rendering Text diagram: {os.path.basename(source_path)}...")
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("    - ERROR: 'Pillow' is not installed in the PDM environment.")
        return False

    padding, line_spacing = 20, 4
    # Render at a large size for high quality
    font_size = 32
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

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(project_root, 'README.template.md')
    with open(template_path, 'r', encoding='utf-8') as f: final_md_content = f.read()

    print("\n--- Processing Diagrams ---")
    images_dir = os.path.join(project_root, 'docs', 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    all_diagrams_ok = True
    for placeholder in re.finditer(r'\{\{diagram:(.*?)\}\}', final_md_content):
        diagram_source_rel_path = placeholder.group(1)
        base_name = os.path.splitext(os.path.basename(diagram_source_rel_path))[0]
        image_rel_path = os.path.join('docs', 'images', f"{base_name}.png").replace("\\", "/")
        
        renderer = render_mermaid_diagram if diagram_source_rel_path.endswith('.mmd') else render_text_diagram
        
        if not renderer(os.path.join(project_root, diagram_source_rel_path), os.path.join(project_root, image_rel_path), project_root):
            all_diagrams_ok = False # Mark failure but continue processing others
            
        alt_text = base_name.replace('_', ' ').title()
        # Add a Pandoc attribute to scale the image width. DOCX handles this correctly.
        image_tag = f"![ ]({image_rel_path}){{width=100%}}"
        final_md_content = final_md_content.replace(placeholder.group(0), image_tag, 1)

    if not all_diagrams_ok:
        print("\n--- BUILD FAILED: One or more diagrams could not be rendered. ---")
        sys.exit(1) # This forces the pre-commit hook to fail correctly

    print("\n--- Building Final Markdown ---")
    with open(os.path.join(project_root, 'README.md'), 'w', encoding='utf-8') as f: f.write(final_md_content)
    print("Successfully built README.md!")

    print("\n--- Starting DOCX Conversion ---")
    try:
        import pypandoc
        for md_filename in ['README.md', 'CONTRIBUTING.md']:
            source_md_path = os.path.join(project_root, md_filename)
            if os.path.exists(source_md_path):
                output_docx_path = os.path.join(project_root, md_filename.replace('.md', '.docx'))
                pypandoc.convert_file(
                    source_md_path, 'docx',
                    outputfile=output_docx_path,
                    extra_args=['--standalone', '--resource-path', project_root]
                )
                print(f"Successfully built '{os.path.basename(output_docx_path)}'!")
    except ImportError:
        print("--- DEPENDENCY ERROR: 'pypandoc' not found. Skipping DOCX generation.")

if __name__ == "__main__":
    main()

# === End of src/build_docs.py ===
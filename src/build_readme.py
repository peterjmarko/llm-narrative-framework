# Filename: src/build_readme.py

import os
import re

def main():
    """
    Builds the final README.md from a template and diagram artifact files.
    """
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        template_path = os.path.join(project_root, 'README.template.md')
        output_path = os.path.join(project_root, 'README.md')
        print(f"Reading template from: {template_path}")
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
            
        # Find all placeholders like {{path/to/file.mmd}}
        placeholders = re.findall(r'\{\{(.*?)\}\}', template_content)
        
        if not placeholders:
            print("Warning: No placeholders found in template. Writing as-is.")
            final_content = template_content
        else:
            print(f"Found {len(placeholders)} placeholders to replace.")
            final_content = template_content
            for placeholder in placeholders:
                # Construct path relative to the project root
                file_to_inject_path = os.path.join(project_root, placeholder)
                
                # Add extra logging to see the exact path being checked
                print(f"  - Attempting to inject placeholder: {placeholder}")
                print(f"    - Checking for file at absolute path: {os.path.abspath(file_to_inject_path)}")
                
                if os.path.exists(file_to_inject_path):
                    print(f"    - SUCCESS: File found. Injecting content.")
                    # FIX: Use the correct variable name 'file_to_inject_path'
                    with open(file_to_inject_path, 'r', encoding='utf-8') as f_diag:
                        diagram_content = f_diag.read()
                    
                    # Replace the placeholder {{...}} with the diagram file's content
                    final_content = final_content.replace(f'{{{{{placeholder}}}}}', diagram_content, 1)
                else:
                    print(f"    - ERROR: File not found at the path above.")
        
        print(f"Writing final output to: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f_out:
            f_out.write(final_content)
            
        print("\nREADME.md has been successfully built!")

    except FileNotFoundError as e:
        print(f"\nERROR: A required file was not found: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
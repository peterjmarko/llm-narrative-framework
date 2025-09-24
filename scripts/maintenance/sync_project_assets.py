#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
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
# Filename: scripts/maintenance/sync_project_assets.py

"""
Project Asset Sync Script

Copies key project assets from their various directories into a single
staging folder for easy upload to Claude's project repository.

This script identifies stable reference assets vs. development files
and organizes them appropriately for the Claude project workflow.
"""

import os
import shutil
from pathlib import Path
import argparse
import configparser
from datetime import datetime


class ProjectSyncer:
    def __init__(self, project_root: Path, staging_dir: Path = None):
        self.project_root = Path(project_root)
        self.staging_dir = staging_dir or self.project_root / "output/project_staging"
        self.changes_dir = self.staging_dir / "changed_files"
        self.previous_staging = {}  # Initialize the missing attribute
        
        # Define asset categories based on your framework structure
        self.stable_assets = {
            "./": [
                "README.template.md",
                "DEVELOPERS_GUIDE.template.md", 
                "config.ini",
                "pyproject.toml",
                ".gitignore",
                "new_experiment.ps1",
                "audit_experiment.ps1",
                "fix_experiment.ps1", 
                "audit_study.ps1",
                "compile_study.ps1",
                "prepare_data.ps1"
            ],
            
            "docs/": [
                "DATA_PREPARATION_DATA_DICTIONARY.template.md",
                "EXPERIMENT_LIFECYCLE_DATA_DICTIONARY.template.md",
                "FRAMEWORK_MANUAL.template.md",
                "TESTING_GUIDE.template.md", 
                "LIFECYCLE_GUIDE.template.md",
                "article_main_text.template.md",
                "REPLICATION_GUIDE.template.md",
                "PROJECT_ROADMAP.md"
            ],
            
            "data/": [
                "base_query.txt"
            ],
            
            "data/foundational_assets/": [
                "point_weights.csv",
                "balance_thresholds.csv",
                "country_codes.csv",
                "sf_delineations_library.txt"
            ],
            
            "src/": [
                "config_loader.py"
            ],
            
            "src/utils/": [
                "file_utils.py"
            ],
            
            "scripts/analysis/": [
                "analyze_cutoff_parameters.py",
                "get_docstring_summary.py"
            ],
            
            "scripts/maintenance/": [
                "clean_project.py",
                "generate_scope_report.py",
                "list_project_files.py",
                "sync_project_assets.py"
            ],
            
            "scripts/build/": [
                "build_docs.py"
            ],
            
            "output/project_reports/": [
                "project_scope_report.md"
            ]
        }

        self.development_assets = {
            "src/": [
                # Core experiment lifecycle (actively developed)
                "experiment_manager.py",
                "replication_manager.py",
                "experiment_auditor.py",
                "analyze_study_results.py",
                "compile_study_results.py",
                "compile_experiment_results.py",
                "compile_replication_results.py",
                
                # Data preparation pipeline
                "fetch_adb_data.py",
                "find_wikipedia_links.py", 
                "validate_wikipedia_pages.py",
                "select_eligible_candidates.py",
                "generate_eminence_scores.py",
                "generate_ocean_scores.py",
                "select_final_candidates.py",
                "create_subject_db.py",
                "generate_personalities_db.py",
                "neutralize_delineations.py",
                "prepare_sf_import.py",
                
                # LLM interaction and processing
                "llm_prompter.py",
                "build_llm_queries.py",
                "process_llm_responses.py",
                "analyze_llm_performance.py",
                "run_bias_analysis.py",
                
                # Report generation
                "generate_replication_report.py",
                "manage_experiment_log.py"
            ]
        }

    def create_staging_structure(self):
        """Create the staging directory structure."""
        # Store previous staging contents for comparison if it exists
        self.previous_staging = {}
        if self.staging_dir.exists():
            self.store_previous_staging_state()
        
        # Create staging directory if it doesn't exist
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories if they don't exist
        (self.staging_dir / "stable").mkdir(exist_ok=True)
        (self.staging_dir / "development").mkdir(exist_ok=True)
        (self.staging_dir / "config").mkdir(exist_ok=True)
        
        # Clear only the changed_files directory
        if self.changes_dir.exists():
            shutil.rmtree(self.changes_dir)
        self.changes_dir.mkdir()

    def store_previous_staging_state(self):
        """Store checksums of existing staging files for change detection."""
        import hashlib
        
        for subdir in ["stable", "development", "config"]:
            subdir_path = self.staging_dir / subdir
            if subdir_path.exists():
                for file_path in subdir_path.rglob("*"):
                    if file_path.is_file():
                        try:
                            with open(file_path, 'rb') as f:
                                content_hash = hashlib.md5(f.read()).hexdigest()
                            relative_path = file_path.relative_to(self.staging_dir)
                            self.previous_staging[str(relative_path)] = content_hash
                        except (OSError, IOError):
                            # Skip files that can't be read
                            pass

    def detect_changes_before_copy(self):
        """Detect which files would change by comparing source files to staging."""
        import hashlib
        
        changed_files = []
        
        # Check stable files
        for source_dir, files in self.stable_assets.items():
            for file_name in files:
                source_path = self.project_root / source_dir / file_name
                if not source_path.exists():
                    continue
                
                # Calculate destination name
                if source_dir != "./":
                    safe_dir = source_dir.replace("/", "_").replace("\\", "_").rstrip("_")
                    dest_name = f"{safe_dir}_{file_name}"
                else:
                    dest_name = file_name
                
                relative_path = f"stable/{dest_name}".replace("/", "\\")
                
                # Calculate source file hash
                try:
                    with open(source_path, 'rb') as f:
                        source_hash = hashlib.md5(f.read()).hexdigest()
                    
                    # Check if file is new or changed
                    if relative_path not in self.previous_staging or self.previous_staging[relative_path] != source_hash:
                        changed_files.append((source_path, dest_name))
                except (OSError, IOError):
                    pass
        
        # Check development files
        for source_dir, files in self.development_assets.items():
            for file_name in files:
                source_path = self.project_root / source_dir / file_name
                if not source_path.exists():
                    continue
                
                # Calculate destination name
                if source_dir != "./":
                    safe_dir = source_dir.replace("/", "_").replace("\\", "_").rstrip("_")
                    dest_name = f"{safe_dir}_{file_name}"
                else:
                    dest_name = file_name
                
                relative_path = f"development/{dest_name}".replace("/", "\\")
                
                # Calculate source file hash
                try:
                    with open(source_path, 'rb') as f:
                        source_hash = hashlib.md5(f.read()).hexdigest()
                    
                    # Check if file is new or changed
                    if relative_path not in self.previous_staging or self.previous_staging[relative_path] != source_hash:
                        changed_files.append((source_path, dest_name))
                except (OSError, IOError):
                    pass
        
        # Note: Config files are excluded from change detection since they're generated fresh each time
        
        return changed_files

    def detect_changes(self, stable_copied, dev_copied):
        """Detect which files have changed compared to previous staging."""
        import hashlib
        
        changed_files = []
        
        # Check stable files
        for file_info in stable_copied:
            dest_name = file_info.split(" -> ")[1] if " -> " in file_info else file_info
            current_file = self.staging_dir / "stable" / dest_name
            relative_path = f"stable/{dest_name}"
            
            if current_file.exists():
                try:
                    with open(current_file, 'rb') as f:
                        current_hash = hashlib.md5(f.read()).hexdigest()
                    
                    # Check if file is new or changed
                    if relative_path not in self.previous_staging or self.previous_staging[relative_path] != current_hash:
                        changed_files.append((current_file, dest_name))
                except (OSError, IOError):
                    pass
        
        # Check development files
        for file_info in dev_copied:
            dest_name = file_info.split(" -> ")[1] if " -> " in file_info else file_info
            current_file = self.staging_dir / "development" / dest_name
            relative_path = f"development/{dest_name}"
            
            if current_file.exists():
                try:
                    with open(current_file, 'rb') as f:
                        current_hash = hashlib.md5(f.read()).hexdigest()
                    
                    # Check if file is new or changed
                    if relative_path not in self.previous_staging or self.previous_staging[relative_path] != current_hash:
                        changed_files.append((current_file, dest_name))
                except (OSError, IOError):
                    pass
        
        # Check config files
        config_dir = self.staging_dir / "config"
        if config_dir.exists():
            for file_path in config_dir.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(self.staging_dir)
                    try:
                        with open(file_path, 'rb') as f:
                            current_hash = hashlib.md5(f.read()).hexdigest()
                        
                        # Check if file is new or changed
                        if str(relative_path) not in self.previous_staging or self.previous_staging[str(relative_path)] != current_hash:
                            changed_files.append((file_path, file_path.name))
                    except (OSError, IOError):
                        pass
        
        return changed_files

    def copy_changed_files(self, changed_files):
        """Copy changed files to the changes subdirectory."""
        if not changed_files:
            return
        
        for source_file, dest_name in changed_files:
            dest_path = self.changes_dir / dest_name
            shutil.copy2(source_file, dest_path)

    def copy_assets(self, asset_dict: dict, target_subdir: str):
        """Copy assets from the asset dictionary to target subdirectory."""
        target_dir = self.staging_dir / target_subdir
        copied_files = []
        missing_files = []
        
        for source_dir, files in asset_dict.items():
            for file_name in files:
                source_path = self.project_root / source_dir / file_name
                
                if source_path.exists():
                    # Create flat structure in staging - prefix with source dir if needed
                    if source_dir != "./":
                        safe_dir = source_dir.replace("/", "_").replace("\\", "_").rstrip("_")
                        dest_name = f"{safe_dir}_{file_name}"
                    else:
                        dest_name = file_name
                    
                    dest_path = target_dir / dest_name
                    shutil.copy2(source_path, dest_path)
                    copied_files.append(f"{source_dir}{file_name} -> {dest_name}")
                else:
                    missing_files.append(f"{source_dir}{file_name}")
        
        return copied_files, missing_files

    def generate_manifest(self, stable_copied, stable_missing, dev_copied, dev_missing, changed_files):
        """Generate a manifest file describing what was copied."""
        manifest_path = self.staging_dir / "SYNC_MANIFEST.md"
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            f.write(f"# Project Asset Sync Manifest\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Project Root:** {self.project_root.absolute()}\n\n")
            
            if changed_files:
                f.write("## 🔄 Changed Files (priority uploads)\n\n")
                f.write("These files have changed since the last sync and should be uploaded first:\n\n")
                for _, dest_name in changed_files:
                    f.write(f"- {dest_name}\n")
                f.write(f"\n**Location:** `changed_files/` folder\n")
                f.write(f"**Count:** {len(changed_files)} files\n\n")
            else:
                f.write("## 🔄 Changed Files\n\n")
                f.write("No files have changed since the last sync.\n\n")
            
            f.write("## Stable Assets (for Claude project repository)\n\n")
            f.write("These files should be uploaded to the Claude project repository for persistent access across sessions:\n\n")
            for file_info in stable_copied:
                f.write(f"- {file_info}\n")
            
            if stable_missing:
                f.write("\n### Missing Stable Assets:\n")
                for missing in stable_missing:
                    f.write(f"- ❌ {missing}\n")
            
            f.write("\n## Development Assets (for session-specific uploads)\n\n")
            f.write("These files should be uploaded to individual chat sessions as needed:\n\n")
            for file_info in dev_copied:
                f.write(f"- {file_info}\n")
            
            if dev_missing:
                f.write("\n### Missing Development Assets:\n")
                for missing in dev_missing:
                    f.write(f"- ❌ {missing}\n")
            
            f.write("\n## Usage Notes\n\n")
            f.write("1. **Upload changed_files/ contents first** for immediate updates\n")
            f.write("2. **Upload stable/ contents to Claude project repository** for persistent access\n")
            f.write("3. **Upload development/ files to individual sessions** as needed\n")
            f.write("4. **Re-run this script** after major changes to sync latest versions\n")

    def create_config_snapshot(self):
        """Create a snapshot of current configuration for reference."""
        config_dir = self.staging_dir / "config"
        
        # Copy main config if it exists
        main_config = self.project_root / "config.ini"
        if main_config.exists():
            shutil.copy2(main_config, config_dir / "config.ini")
        
        # Create a simple environment info file
        env_info = config_dir / "environment_info.txt"
        with open(env_info, 'w') as f:
            f.write(f"Project Root: {self.project_root.absolute()}\n")
            f.write(f"Sync Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Python Version: {os.sys.version}\n")
            f.write(f"Platform: {os.name}\n")

    def sync(self):
        """Execute the full sync process."""
        print()
        print(f"Syncing project assets from: {self.project_root}")
        print(f"Staging directory: {self.staging_dir}")
        
        # Create directory structure
        self.create_staging_structure()
        
        # Detect changes BEFORE copying new files
        print("\nDetecting changes...")
        changed_files = self.detect_changes_before_copy()
        
        # Debug output
        print(f"  Previous staging contains {len(self.previous_staging)} files")
        if len(self.previous_staging) > 0:
            print(f"  Sample previous files: {list(self.previous_staging.keys())[:3]}")
        
        if changed_files:
            print(f"  Found {len(changed_files)} changed files:")
            for _, dest_name in changed_files[:5]:  # Show first 5
                print(f"    - {dest_name}")
            if len(changed_files) > 5:
                print(f"    ... and {len(changed_files) - 5} more")
        else:
            print("  No changed files detected")
        
        # Copy stable assets
        print("Copying stable assets...")
        stable_copied, stable_missing = self.copy_assets(self.stable_assets, "stable")
        
        # Copy development assets  
        print("Copying development assets...")
        dev_copied, dev_missing = self.copy_assets(self.development_assets, "development")
        
        # Create config snapshot
        print("Creating configuration snapshot...")
        self.create_config_snapshot()
        
        # Copy changed files to separate folder
        self.copy_changed_files(changed_files)
        
        # Generate manifest
        print("Generating manifest...")
        self.generate_manifest(stable_copied, stable_missing, dev_copied, dev_missing, changed_files)
        
        # Summary
        print(f"\n✅ Sync complete!")
        print(f"📁 Staging directory: {self.staging_dir}")
        print(f"📋 Stable assets: {len(stable_copied)} copied, {len(stable_missing)} missing")
        print(f"🔧 Development assets: {len(dev_copied)} copied, {len(dev_missing)} missing")
        print(f"🔄 Changed files: {len(changed_files)} identified")
        print(f"📄 See SYNC_MANIFEST.md for details")
        
        if changed_files:
            print(f"\n📤 Priority upload: {len(changed_files)} changed files in changed_files/ folder")
        
        if stable_missing or dev_missing:
            print(f"\n⚠️  Some files were missing - check manifest for details")
        
        print()


def main():
    parser = argparse.ArgumentParser(description="Sync project assets for Claude project repository")
    parser.add_argument("--project-root", type=str, default=".", 
                       help="Root directory of your project (default: current directory)")
    parser.add_argument("--staging-dir", type=str, 
                       help="Directory to stage files for upload (default: project_root/claude_staging)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be copied without actually copying")
    
    args = parser.parse_args()
    
    project_root = Path(args.project_root).resolve()
    staging_dir = Path(args.staging_dir).resolve() if args.staging_dir else None
    
    if not project_root.exists():
        print(f"❌ Project root not found: {project_root}")
        return 1
    
    syncer = ProjectSyncer(project_root, staging_dir)
    
    if args.dry_run:
        print("🔍 DRY RUN - No files will be copied")
        print(f"Would sync from: {project_root}")
        print(f"Would stage to: {syncer.staging_dir}")
        
        # Show what would be copied
        print("\nStable assets that would be copied:")
        for source_dir, files in syncer.stable_assets.items():
            for file_name in files:
                source_path = project_root / source_dir / file_name
                status = "✓" if source_path.exists() else "✗"
                print(f"  {status} {source_dir}{file_name}")
        
        print("\nDevelopment assets that would be copied:")
        dev_missing_count = 0
        for source_dir, files in syncer.development_assets.items():
            for file_name in files:
                source_path = project_root / source_dir / file_name
                status = "✓" if source_path.exists() else "✗"
                if not source_path.exists():
                    dev_missing_count += 1
                print(f"  {status} {source_dir}{file_name}")
        
        # Count missing stable assets too
        stable_missing_count = 0
        for source_dir, files in syncer.stable_assets.items():
            for file_name in files:
                source_path = project_root / source_dir / file_name
                if not source_path.exists():
                    stable_missing_count += 1
        
        if stable_missing_count > 0 or dev_missing_count > 0:
            print(f"\n⚠️  Some files were missing - check paths for {stable_missing_count + dev_missing_count} missing files")
        
        # Simulate change detection for dry run
        print(f"\n🔄 Files that would be identified as changed:")
        if syncer.staging_dir.exists():
            # Check what would be different
            syncer.store_previous_staging_state()
            
            # Simulate copying to detect changes
            all_files = []
            for source_dir, files in syncer.stable_assets.items():
                for file_name in files:
                    source_path = project_root / source_dir / file_name
                    if source_path.exists():
                        if source_dir != "./":
                            safe_dir = source_dir.replace("/", "_").replace("\\", "_").rstrip("_")
                            dest_name = f"{safe_dir}_{file_name}"
                        else:
                            dest_name = file_name
                        all_files.append(f"{source_dir}{file_name} -> {dest_name}")
            
            for source_dir, files in syncer.development_assets.items():
                for file_name in files:
                    source_path = project_root / source_dir / file_name
                    if source_path.exists():
                        if source_dir != "./":
                            safe_dir = source_dir.replace("/", "_").replace("\\", "_").rstrip("_")
                            dest_name = f"{safe_dir}_{file_name}"
                        else:
                            dest_name = file_name
                        all_files.append(f"{source_dir}{file_name} -> {dest_name}")
            
            changed_files = syncer.detect_changes_before_copy()
            if changed_files:
                for _, dest_name in changed_files:
                    print(f"  📝 {dest_name}")
            else:
                print("  No files would be identified as changed")
        else:
            print("  All files would be new (no previous staging found)")
        
        print()
    else:
        syncer.sync()
    
    return 0


if __name__ == "__main__":
    exit(main())

# === End of scripts/maintenance/sync_project_assets.py ===
